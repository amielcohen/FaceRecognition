from ultralytics import YOLO


class Detector:
    def __init__(self, model_name: str = "yolov8n.pt"):
        """
        Initialize the YOLO model for person detection and tracking.
        """
        self.model = YOLO(model_name)

    def track(self, frame):
        """
        Run person tracking on a single frame.

        Returns:
            A list of dictionaries, each containing:
            - bbox: [x1, y1, x2, y2]
            - track_id: integer tracking ID
            - conf: detection confidence
            - label: object label ("person")
        """
        results = self.model.track(
            source=frame,
            persist=True,
            classes=[0],  # COCO class 0 = person
            verbose=False
        )

        detections = []

        if not results or len(results) == 0:
            return detections

        result = results[0]

        if result.boxes is None or result.boxes.id is None:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy().astype(int)
        track_ids = result.boxes.id.cpu().numpy().astype(int)
        confidences = result.boxes.conf.cpu().numpy()

        for box, track_id, conf in zip(boxes, track_ids, confidences):
            x1, y1, x2, y2 = box.tolist()

            detections.append({
                "bbox": [x1, y1, x2, y2],
                "track_id": int(track_id),
                "conf": float(conf),
                "label": "person"
            })

        return detections