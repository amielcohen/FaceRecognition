import cv2
from ultralytics import YOLO


class FaceDetector:
    def __init__(self, model_name: str = "yolov8n-face.pt", margin_ratio: float = 0.20):
        """
        Initialize the YOLO face detector.

        Args:
            model_name: Path to the face detection model.
            margin_ratio: Extra padding ratio added around the detected face box.
                          This helps preserve hairline, forehead, and face boundaries.
        """
        self.model = YOLO(model_name)
        self.margin_ratio = margin_ratio

    def detect_largest_face(self, person_crop):
        """
        Detect the largest face inside a person crop.

        Args:
            person_crop: Cropped image containing a single detected person.

        Returns:
            A dictionary with:
            - bbox: Expanded face bounding box [x1, y1, x2, y2] inside person_crop coordinates
            - area: Face area in pixels after expansion
            - crop: Expanded face crop image

            Returns None if no face is detected.
        """
        if person_crop is None or person_crop.size == 0:
            return None

        results = self.model.predict(source=person_crop, verbose=False)

        if not results or len(results) == 0:
            return None

        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return None

        boxes = result.boxes.xyxy.cpu().numpy().astype(int)

        best_box = None
        best_area = 0

        # Select the largest detected face.
        for box in boxes:
            x1, y1, x2, y2 = box.tolist()
            area = max(0, x2 - x1) * max(0, y2 - y1)

            if area > best_area:
                best_area = area
                best_box = [x1, y1, x2, y2]

        if best_box is None:
            return None

        expanded_box = self._expand_bbox(best_box, person_crop.shape, self.margin_ratio)
        ex1, ey1, ex2, ey2 = expanded_box

        face_crop = person_crop[ey1:ey2, ex1:ex2]

        if face_crop is None or face_crop.size == 0:
            return None

        expanded_area = (ex2 - ex1) * (ey2 - ey1)

        return {
            "bbox": expanded_box,
            "area": expanded_area,
            "crop": face_crop
        }

    def _expand_bbox(self, bbox, image_shape, margin_ratio: float):
        """
        Expand a bounding box by a margin ratio while keeping it inside image boundaries.

        Args:
            bbox: Original bounding box [x1, y1, x2, y2]
            image_shape: Shape of the source image
            margin_ratio: Expansion ratio relative to width and height

        Returns:
            Expanded and clipped bounding box [x1, y1, x2, y2]
        """
        x1, y1, x2, y2 = bbox
        img_h, img_w = image_shape[:2]

        width = x2 - x1
        height = y2 - y1

        margin_x = int(width * margin_ratio)
        margin_y = int(height * margin_ratio)

        ex1 = max(0, x1 - margin_x)
        ey1 = max(0, y1 - margin_y)
        ex2 = min(img_w, x2 + margin_x)
        ey2 = min(img_h, y2 + margin_y)

        return [ex1, ey1, ex2, ey2]

    def draw_face_box(self, image, face_bbox, offset_x=0, offset_y=0, color=(0, 255, 255), thickness=2):
        """
        Draw a face bounding box on the original image.

        Args:
            image: Original frame
            face_bbox: Face box in local crop coordinates [x1, y1, x2, y2]
            offset_x: X offset of the person crop in the original frame
            offset_y: Y offset of the person crop in the original frame
            color: Rectangle color
            thickness: Rectangle thickness
        """
        if face_bbox is None:
            return

        x1, y1, x2, y2 = face_bbox
        cv2.rectangle(
            image,
            (x1 + offset_x, y1 + offset_y),
            (x2 + offset_x, y2 + offset_y),
            color,
            thickness
        )