import os
import time
from datetime import datetime

import cv2

from facerecog.database.db_manager import DatabaseManager
from facerecog.core.detector import Detector
from facerecog.core.face_detector import FaceDetector
from facerecog.core.face_recognizer import FaceRecognizer


def save_face_crop(face_crop, matched_name, track_id, output_dir="data/crops"):
    if face_crop is None or face_crop.size == 0:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    date_folder = datetime.now().strftime("%Y-%m-%d")
    save_dir = os.path.join(output_dir, date_folder)

    os.makedirs(save_dir, exist_ok=True)

    safe_name = matched_name.replace(" ", "_")
    filename = f"{safe_name}_track{track_id}_{timestamp}.jpg"
    full_path = os.path.join(save_dir, filename)

    cv2.imwrite(full_path, face_crop)
    return full_path


def log_final_track_result(db, face_recognizer, track_id):
    if not face_recognizer.should_log_identity(track_id):
        return

    final_result = face_recognizer.get_final_result(track_id)
    if final_result is None:
        return

    crop_path = save_face_crop(
        face_crop=final_result["crop"],
        matched_name=final_result["name"],
        track_id=track_id
    )

    db.log_attendance_event(
        matched_name=final_result["name"],
        distance=final_result["distance"],
        track_id=track_id,
        crop_path=crop_path
    )

    face_recognizer.mark_logged(track_id)


def main():
    db = DatabaseManager("database/vision_db.sqlite")

    settings = db.load_camera_settings(camera_id=1)
    if not settings:
        print("No camera settings found.")
        return

    video_source = settings.get("rtsp_url", "0")
    min_face_area = settings.get("min_face_area", 2500)
    area_update_ratio = settings.get("area_update_ratio", 1.2)
    match_threshold = settings.get("match_identity_threshold", 0.4)
    lock_threshold = settings.get("lock_identity_threshold", 0.2)
    max_unknown_attempts = settings.get("max_unknown_attempts", 5)
    frame_skip_interval = settings.get("frame_skip_inteqrval", 1)

    try:
        video_source = int(video_source)
    except ValueError:
        pass

    detector = Detector(model_name="yolov8n.pt")

    face_detector = FaceDetector(
        model_name="models/yolov8n-face.pt",
        margin_ratio=0.20
    )

    face_recognizer = FaceRecognizer(
        model_name="Facenet",
        db_path="employees_embeddings.json",
        match_threshold=match_threshold,
        lock_threshold=lock_threshold,
        max_unknown_attempts=max_unknown_attempts,
        max_workers=2
    )

    cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("Failed to open camera")
        return

    print("--- Face Recognition System Started ---")

    frame_index = 0

    while cap.isOpened():
        start_time = time.time()

        ret, frame = cap.read()
        if not ret:
            break

        frame_index += 1

        detections = []
        if frame_index % frame_skip_interval == 0:
            detections = detector.track(frame)

        # Handle disappeared tracks
        if frame_index % 30 == 0:
            stale_ids = face_recognizer.cleanup_stale_tracks(
                current_frame_index=frame_index,
                max_missing_frames=90
            )

            for track_id in stale_ids:
                log_final_track_result(db, face_recognizer, track_id)

            face_recognizer.purge_logged_stale_tracks(stale_ids)

        for det in detections:
            if det.get("label") != "person":
                continue

            track_id = det["track_id"]
            x1, y1, x2, y2 = map(int, det["bbox"])

            face_recognizer.update_last_seen(track_id, frame_index)

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)

            if x2 <= x1 or y2 <= y1:
                continue

            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size == 0:
                continue

            local_face_bbox = None

            if not face_recognizer.is_locked(track_id):
                face_result = face_detector.detect_largest_face(person_crop)

                if face_result is not None:
                    face_recognizer.register_face_seen(track_id)

                    local_face_bbox = face_result["bbox"]
                    face_area = face_result["area"]
                    face_crop = face_result["crop"]

                    if face_area >= min_face_area:
                        if face_recognizer.should_process_face(
                            track_id=track_id,
                            face_area=face_area,
                            growth_ratio=area_update_ratio,
                            current_frame=frame_index
                        ):
                            face_recognizer.submit_face(
                                track_id=track_id,
                                face_crop=face_crop,
                                face_area=face_area,
                                current_frame=frame_index   
                            )

            status = face_recognizer.get_status(track_id)
            display_name = face_recognizer.get_display_name(track_id)

            if status == "identified":
                color = (0, 255, 0)
            elif status == "unknown":
                color = (0, 0, 255)
            else:
                color = (255, 0, 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                display_name,
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

            if local_face_bbox is not None:
                face_detector.draw_face_box(
                    image=frame,
                    face_bbox=local_face_bbox,
                    offset_x=x1,
                    offset_y=y1
                )

            log_final_track_result(db, face_recognizer, track_id)

        # FPS
        elapsed = time.time() - start_time
        fps = 1 / elapsed if elapsed > 0 else 0

        cv2.putText(
            frame,
            f"FPS: {fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        cv2.imshow("Face Recognition System", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Final cleanup
    stale_ids = face_recognizer.cleanup_stale_tracks(
        current_frame_index=frame_index + 1000,
        max_missing_frames=0
    )

    for track_id in stale_ids:
        log_final_track_result(db, face_recognizer, track_id)

    face_recognizer.purge_logged_stale_tracks(stale_ids)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()