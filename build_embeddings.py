import json
from pathlib import Path

import cv2
from deepface import DeepFace

from facerecog.core.face_detector import FaceDetector


BASE_DIR = Path(__file__).resolve().parent

EMPLOYEES_ROOT = BASE_DIR / "employees_data"
STORAGE_DIR = BASE_DIR / "storage"
OUTPUT_JSON = STORAGE_DIR / "employees_embeddings.json"
FACE_MODEL_PATH = BASE_DIR / "models" / "yolov8n-face.pt"


def get_embedding(face_crop, model_name="Facenet"):
    """
    Extract embedding from an already cropped face image.
    """
    try:
        results = DeepFace.represent(
            img_path=face_crop,
            model_name=model_name,
            enforce_detection=False,
            detector_backend="skip"
        )
        return results[0]["embedding"]
    except Exception as e:
        print(f"[Embedding Error] {e}")
        return None


def build_database():
    """
    Build embeddings database from employee image folders.

    Each employee should have a folder:
    employees_data/
        Amiel/
            img1.jpg
            img2.jpg
        David/
            img1.jpg
    """
    if not EMPLOYEES_ROOT.exists():
        print(f"Directory '{EMPLOYEES_ROOT}' does not exist.")
        return

    face_detector = FaceDetector(
        model_name=str(FACE_MODEL_PATH),
        margin_ratio=0.35
    )

    database = {}
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    print("=== Building Face Embeddings Database ===\n")

    for employee_dir in EMPLOYEES_ROOT.iterdir():
        if not employee_dir.is_dir():
            continue

        employee_name = employee_dir.name
        print(f"[Employee] {employee_name}")

        embeddings = []
        total_images = 0
        success_count = 0

        for img_path in employee_dir.iterdir():
            if img_path.suffix.lower() not in valid_extensions:
                continue

            total_images += 1

            image = cv2.imread(str(img_path))
            if image is None:
                print(f"  [Skip] Could not read {img_path.name}")
                continue

            face_result = face_detector.detect_largest_face(image)

            if face_result is None:
                print(f"  [Skip] No face detected in {img_path.name}")
                continue

            face_crop = face_result["crop"]
            emb = get_embedding(face_crop)

            if emb is not None:
                embeddings.append(emb)
                success_count += 1
                print(f"  [OK] {img_path.name}")
            else:
                print(f"  [Fail] Embedding failed for {img_path.name}")

        if embeddings:
            database[employee_name] = embeddings
            print(f"  → {success_count}/{total_images} images used\n")
        else:
            print("  → No valid embeddings created!\n")
            
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(database, f)

    print(f"\n=== Done! Saved to {OUTPUT_JSON} ===")


if __name__ == "__main__":
    build_database()