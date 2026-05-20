import os
import time
import threading
from datetime import datetime

import cv2
import requests

from facerecog.database.db_manager import DatabaseManager
from facerecog.core.detector import Detector
from facerecog.core.face_detector import FaceDetector
from facerecog.core.face_recognizer import FaceRecognizer
from facerecog.utils.face_quality import calculate_face_quality


# =========================================================
# Shared state between threads
# =========================================================

debug_stats = {
    "person_detected": 0,
    "no_face_in_person_crop": 0,
    "face_too_small": 0,
    "retry_blocked": 0,
    "embedding_submitted": 0,
    "embedding_failed": 0,
    "matched_below_threshold": 0,
    "matched_and_locked": 0,
    "unknown_after_match": 0,
}

# Latest raw frame from camera (written by camera thread, read by recognition thread)
_latest_raw_frame = None
_raw_frame_lock = threading.Lock()

# Latest annotated frame for streaming (written by display thread, read by api.py)
LATEST_FRAME_PATH = "data/latest_frame.jpg"

# Active detections shared between recognition thread and display thread
_active_detections = {}   # track_id -> {bbox, status, display_name, face_bbox}
_detections_lock = threading.Lock()

_stop_event = threading.Event()


# =========================================================
# Helpers
# =========================================================

def get_setting(settings, key, default, cast_type=float):
    try:
        value = settings.get(key, default)
        if value is None:
            return default
        return cast_type(value)
    except (TypeError, ValueError):
        print(f"[Settings] Failed to load {key}. Using default: {default}")
        return default


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


def write_latest_frame(frame):
    """Atomically write annotated frame to disk for the live stream endpoint."""
    try:
        os.makedirs("data", exist_ok=True)
        tmp_path = LATEST_FRAME_PATH.replace(".jpg", "_tmp.jpg")
        cv2.imwrite(tmp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        os.replace(tmp_path, LATEST_FRAME_PATH)
    except Exception as e:
        print(f"[Stream] Failed to write frame: {e}")


# =========================================================
# Thread 1: Camera Reader
# Reads frames from camera as fast as possible
# =========================================================

def camera_reader_thread(cap):
    global _latest_raw_frame

    print("[CameraThread] Started")

    while not _stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("[CameraThread] Failed to read frame")
            time.sleep(0.1)
            continue

        with _raw_frame_lock:
            _latest_raw_frame = frame

    print("[CameraThread] Stopped")


# =========================================================
# Thread 2: Recognition Worker
# Runs YOLO + DeepFace every frame_skip_interval frames
# Updates _active_detections with latest results
# =========================================================

def recognition_thread(detector, face_detector, face_recognizer, db, settings):
    global _active_detections

    frame_skip_interval = get_setting(settings, "frame_skip_interval", 3, int)
    min_face_area = get_setting(settings, "min_face_area", 1000, int)
    quality_submit_min = get_setting(settings, "quality_submit_min", 0.40, float)
    quality_submit_hard = get_setting(settings, "quality_submit_hard", 0.82, float)
    quality_gain_min = get_setting(settings, "quality_gain_min", 0.05, float)
    quality_retry_interval = get_setting(settings, "quality_retry_interval", 5, int)

    frame_index = 0

    print("[RecognitionThread] Started")

    while not _stop_event.is_set():
        with _raw_frame_lock:
            frame = _latest_raw_frame

        if frame is None:
            time.sleep(0.05)
            continue

        frame = frame.copy()
        frame_index += 1

        # Run YOLO every frame_skip_interval frames
        if frame_index % frame_skip_interval != 0:
            time.sleep(0.01)
            continue

        detections = detector.track(frame)

        # Cleanup stale tracks every 30 processed frames
        if frame_index % (30 * frame_skip_interval) == 0:
            stale_ids = face_recognizer.cleanup_stale_tracks(
                current_frame_index=frame_index,
                max_missing_frames=90
            )
            for stale_track_id in stale_ids:
                log_final_track_result(db, face_recognizer, stale_track_id)
            face_recognizer.purge_logged_stale_tracks(stale_ids)

        new_detections = {}

        for det in detections:
            if det.get("label") != "person":
                continue

            debug_stats["person_detected"] += 1

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
                    quality = calculate_face_quality(face_crop, face_area)

                    if face_area >= min_face_area:
                        if face_recognizer.should_process_face(
                            track_id=track_id,
                            face_area=face_area,
                            quality_score=quality["score"],
                            current_frame=frame_index
                        ):
                            debug_stats["embedding_submitted"] += 1
                            face_recognizer.submit_face(
                                track_id=track_id,
                                face_crop=face_crop,
                                face_area=face_area,
                                quality=quality,
                                current_frame=frame_index
                            )
                        else:
                            debug_stats["retry_blocked"] += 1
                    else:
                        debug_stats["face_too_small"] += 1
                else:
                    debug_stats["no_face_in_person_crop"] += 1

            log_final_track_result(db, face_recognizer, track_id)

            new_detections[track_id] = {
                "bbox": [x1, y1, x2, y2],
                "status": face_recognizer.get_status(track_id),
                "display_name": face_recognizer.get_display_name(track_id),
                "face_bbox": local_face_bbox,
            }

        with _detections_lock:
            _active_detections = new_detections

        if frame_index % 60 == 0:
            print("\n==== DEBUG STATS ====")
            for key, value in debug_stats.items():
                print(f"{key}: {value}")

    print("[RecognitionThread] Stopped")


# =========================================================
# Thread 3: Display Writer
# Reads latest raw frame, draws boxes, writes to disk at full speed
# =========================================================

def display_writer_thread(face_detector):
    frame_count = 0

    print("[DisplayThread] Started")

    while not _stop_event.is_set():
        with _raw_frame_lock:
            frame = _latest_raw_frame

        if frame is None:
            time.sleep(0.033)
            continue

        frame = frame.copy()

        with _detections_lock:
            detections = dict(_active_detections)

        for track_id, det in detections.items():
            x1, y1, x2, y2 = det["bbox"]
            status = det["status"]
            display_name = det["display_name"]
            face_bbox = det["face_bbox"]

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

            if face_bbox is not None:
                face_detector.draw_face_box(
                    image=frame,
                    face_bbox=face_bbox,
                    offset_x=x1,
                    offset_y=y1
                )

        write_latest_frame(frame)
        frame_count += 1

        time.sleep(0.033)  # target ~30fps display

    print("[DisplayThread] Stopped")


# =========================================================
# Main
# =========================================================

def main():
    db = DatabaseManager("database/vision_db.sqlite")

    settings = db.load_camera_settings(camera_id=1)
    if not settings:
        print("No camera settings found.")
        return

    match_threshold = get_setting(settings, "match_identity_threshold", 0.4, float)
    lock_threshold = get_setting(settings, "lock_identity_threshold", 0.35, float)
    max_unknown_attempts = get_setting(settings, "max_unknown_attempts", 5, int)
    quality_submit_min = get_setting(settings, "quality_submit_min", 0.40, float)
    quality_submit_hard = get_setting(settings, "quality_submit_hard", 0.82, float)
    quality_gain_min = get_setting(settings, "quality_gain_min", 0.05, float)
    quality_retry_interval = get_setting(settings, "quality_retry_interval", 5, int)

    detector = Detector(model_name="yolov8n.pt")

    face_detector = FaceDetector(
        model_name="models/yolov8n-face.pt",
        margin_ratio=0.35
    )

    face_recognizer = FaceRecognizer(
        model_name="Facenet",
        db_path="storage/employees_embeddings.json",
        match_threshold=match_threshold,
        lock_threshold=lock_threshold,
        max_unknown_attempts=max_unknown_attempts,
        max_workers=2,
        debug_stats=debug_stats,
        quality_submit_min=quality_submit_min,
        quality_submit_hard=quality_submit_hard,
        quality_gain_min=quality_gain_min,
        quality_retry_interval=quality_retry_interval
    )

    camera_source = os.getenv("CAMERA_SOURCE", "0")
    if camera_source.isdigit():
        camera_source = int(camera_source)

    print(f"[CAMERA] Using source: {camera_source}")

    cap = cv2.VideoCapture(camera_source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("requested width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("requested height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if not cap.isOpened():
        print("Failed to open camera")
        return

    print("--- Face Recognition System Started ---")

    try:
        requests.post("http://127.0.0.1:8000/system/mark-ready")
    except Exception:
        pass

    # Start all threads
    threads = [
        threading.Thread(target=camera_reader_thread, args=(cap,), daemon=True),
        threading.Thread(target=recognition_thread, args=(detector, face_detector, face_recognizer, db, settings), daemon=True),
        threading.Thread(target=display_writer_thread, args=(face_detector,), daemon=True),
    ]

    for t in threads:
        t.start()

    # Keep main thread alive until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Stopping...")
        _stop_event.set()

    for t in threads:
        t.join(timeout=5)

    # Final cleanup
    stale_ids = face_recognizer.cleanup_stale_tracks(
        current_frame_index=999999,
        max_missing_frames=0
    )
    for stale_track_id in stale_ids:
        log_final_track_result(db, face_recognizer, stale_track_id)

    face_recognizer.purge_logged_stale_tracks(stale_ids)
    cap.release()
    print("[Main] Done.")


if __name__ == "__main__":
    main()