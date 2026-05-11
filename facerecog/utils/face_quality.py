import cv2
import numpy as np


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, min_value=0.0, max_value=1.0):
    return max(min_value, min(value, max_value))


def calculate_face_quality(face_crop, face_area):
    """
    Calculates a relative quality score for a detected face.

    The score is not a guarantee of correct identity.
    It is only used to decide whether this frame is worth sending
    to the recognition model.
    """

    if face_crop is None or face_crop.size == 0:
        return {
            "score": 0.0,
            "sharpness": 0.0,
            "area": 0,
            "brightness": 0.0,
            "contrast": 0.0,
            "width": 0,
            "height": 0,
        }

    height, width = face_crop.shape[:2]
    crop_area = height * width

    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))

    area_value = max(_safe_float(face_area), float(crop_area))

    # Less aggressive normalization, so large faces do not instantly become perfect.
    area_score = _clamp(area_value / 30000.0)

    # Your previous values were often 1000-8000, so 120 was too low.
    sharpness_score = _clamp(sharpness / 8000.0)

    # Prefer normal lighting. Too dark or too bright is worse.
    brightness_score = 1.0 - abs(brightness - 125.0) / 125.0
    brightness_score = _clamp(brightness_score)

    # Very low contrast usually means a flat/unclear crop.
    contrast_score = _clamp(contrast / 80.0)

    # Penalize very small crops even if area was reported as large.
    size_score = min(width, height) / 180.0
    size_score = _clamp(size_score)

    score = (
        0.35 * area_score +
        0.30 * sharpness_score +
        0.15 * brightness_score +
        0.10 * contrast_score +
        0.10 * size_score
    )

    return {
        "score": float(_clamp(score)),
        "sharpness": float(sharpness),
        "area": int(area_value),
        "brightness": float(brightness),
        "contrast": float(contrast),
        "width": int(width),
        "height": int(height),
    }