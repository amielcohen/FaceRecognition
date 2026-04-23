import json
import threading
from concurrent.futures import ThreadPoolExecutor

from deepface import DeepFace
from scipy.spatial import distance


class FaceRecognizer:
    def __init__(
        self,
        model_name="Facenet",
        db_path="employees_embeddings.json",
        match_threshold=0.4,
        lock_threshold=0.2,
        max_unknown_attempts=5,
        max_workers=2
    ):
        self.model_name = model_name
        self.match_threshold = match_threshold
        self.lock_threshold = lock_threshold
        self.max_unknown_attempts = max_unknown_attempts

        self.employee_db = self._load_db(db_path)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self.processing_ids = set()
        self.track_states = {}
        self.lock = threading.Lock()

    def _load_db(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load DB from {path}: {e}")
            return {}

    def _create_default_state(self):
        return {
            "status": "scanning",
            "best_name": None,
            "best_dist": None,
            "best_area": 0,
            "attempts": 0,
            "last_face_crop": None,
            "last_seen_frame": 0,
            "logged": False,
            "ever_had_face": False,
            "ever_processed": False,
            "last_attempt_frame": 0
        }

    def get_display_name(self, track_id):
        state = self.track_states.get(track_id)
        if not state:
            return f"ID {track_id} (Scanning...)"

        status = state["status"]

        if status == "identified":
            return state["best_name"]

        if status == "unknown":
            return "Unknown"

        if state["best_name"] and state["best_dist"] is not None:
            return f"{state['best_name']} ({state['best_dist']:.3f})"

        return f"ID {track_id} (Scanning...)"

    def get_status(self, track_id):
        return self.track_states.get(track_id, {}).get("status", "scanning")

    def is_locked(self, track_id):
        return self.get_status(track_id) in {"identified", "unknown"}

    def update_last_seen(self, track_id, frame_index):
        state = self.track_states.setdefault(track_id, self._create_default_state())
        state["last_seen_frame"] = frame_index

    def register_face_seen(self, track_id):
        state = self.track_states.setdefault(track_id, self._create_default_state())
        state["ever_had_face"] = True

    def should_process_face(self, track_id, face_area, growth_ratio, current_frame, retry_interval=15):
        state = self.track_states.setdefault(track_id, self._create_default_state())

        if state["status"] in {"identified", "unknown"}:
            return False

        if track_id in self.processing_ids:
            return False

        if state["best_area"] == 0:
            return True

        if face_area > state["best_area"] * growth_ratio:
            return True

        if current_frame - state["last_attempt_frame"] >= retry_interval:
            return True

        return False

    def submit_face(self, track_id, face_crop, face_area, current_frame):
        if face_crop is None or face_crop.size == 0:
            return False

        state = self.track_states.setdefault(track_id, self._create_default_state())
        self.processing_ids.add(track_id)
        state["last_attempt_frame"] = current_frame

        self.executor.submit(
            self._process_face_async,
            track_id,
            face_crop.copy(),
            face_area
        )
        return True

    def match_face(self, new_embedding):
        best_match = "Unknown"
        min_dist = 1.0

        for name, embeddings in self.employee_db.items():
            for db_emb in embeddings:
                dist = distance.cosine(new_embedding, db_emb)
                if dist < min_dist:
                    min_dist = dist
                    best_match = name

        return best_match, min_dist

    def _process_face_async(self, track_id, face_crop, face_area):
        try:
            print(f"[AI] Processing track {track_id}...")

            results = DeepFace.represent(
                img_path=face_crop,
                model_name=self.model_name,
                enforce_detection=False,
                detector_backend="skip"
            )

            if not results:
                self._register_failed_attempt(track_id)
                return

            new_emb = results[0]["embedding"]
            name, dist = self.match_face(new_emb)

            print(f"[Match] Track {track_id} | best_match={name} | distance={dist:.4f}")

            state = self.track_states.setdefault(track_id, self._create_default_state())

            if face_area > state["best_area"]:
                state["best_area"] = face_area

            if state["best_dist"] is None or dist < state["best_dist"]:
                state["best_dist"] = dist
                state["best_name"] = name
                state["last_face_crop"] = face_crop.copy()

            if dist < self.lock_threshold:
                state["status"] = "identified"
                print(f"[LOCK] Track {track_id} locked as {name}")

            elif dist >= self.match_threshold:
                state["attempts"] += 1
                print(f"[Attempt] {state['attempts']}/{self.max_unknown_attempts}")

                if state["attempts"] >= self.max_unknown_attempts:
                    state["status"] = "unknown"
                    state["best_name"] = "Unknown"

        except Exception as e:
            print(f"[AI Error] {e}")
            self._register_failed_attempt(track_id)

        finally:
            self.processing_ids.discard(track_id)

    def _register_failed_attempt(self, track_id):
        state = self.track_states.setdefault(track_id, self._create_default_state())

        state["attempts"] += 1

        if state["attempts"] >= self.max_unknown_attempts:
            state["status"] = "unknown"
            state["best_name"] = "Unknown"

    def should_log_identity(self, track_id):
        state = self.track_states.get(track_id)
        if not state or state["logged"]:
            return False

        return state["status"] in {"identified", "unknown"}

    def mark_logged(self, track_id):
        if track_id in self.track_states:
            self.track_states[track_id]["logged"] = True

    def get_final_result(self, track_id):
        state = self.track_states.get(track_id)
        if not state:
            return None

        return {
            "name": state["best_name"] if state["status"] == "identified" else "Unknown",
            "distance": state["best_dist"],
            "crop": state["last_face_crop"]
        }

    def cleanup_stale_tracks(self, current_frame_index, max_missing_frames=90):
        stale_ids = []

        for track_id, state in self.track_states.items():
            if current_frame_index - state["last_seen_frame"] > max_missing_frames:
                if state["status"] == "scanning":
                    if state["best_dist"] is not None and state["best_dist"] < self.match_threshold:
                        state["status"] = "identified"
                    else:
                        state["status"] = "unknown"
                        state["best_name"] = "Unknown"

                stale_ids.append(track_id)

        return stale_ids

    def purge_logged_stale_tracks(self, stale_ids):
        for track_id in stale_ids:
            if track_id in self.track_states and self.track_states[track_id]["logged"]:
                self.track_states.pop(track_id, None)
                self.processing_ids.discard(track_id)