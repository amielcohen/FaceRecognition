from ultralytics import YOLO
import cv2
import numpy as np

class PersonDetector:
    def __init__(self, model_name='yolov8n.pt'):
        """
        Initialize the YOLO model.
        Using yolov8n (Nano) as it is the fastest version, ideal for real-time processing.
        Note: The weights file will be downloaded automatically on the first run.
        """
        self.model = YOLO(model_name)
        
    def detect(self, frame):
        """
        Perform object detection and tracking on a single frame.
        """
        # Run tracking on the frame.
        # persist=True: maintains state between frames.
        # classes=[0]: filters results to detect 'person' class only.
        results = self.model.track(frame, persist=True, classes=[0], verbose=False)
        
        detections = []
        
        # Check if boxes were detected and if they have associated tracking IDs
        if results[0].boxes and results[0].boxes.id is not None:
            # Extract coordinates, IDs, and confidence scores
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()

            for box, track_id, conf in zip(boxes, ids, confs):
                detections.append({
                    'bbox': box,        # Coordinates [x1, y1, x2, y2]
                    'track_id': track_id,
                    'conf': conf
                })
                
        return detections