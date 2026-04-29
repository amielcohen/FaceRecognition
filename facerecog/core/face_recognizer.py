import json
import time
from concurrent.futures import ThreadPoolExecutor

from deepface import DeepFace
from scipy.spatial import distance


class FaceRecognizer:
    def __init__(
        self,
        model_name="Facenet",
        db_path="employees_embeddings.json",
        match_threshold=0.4,
        lock_threshold=0.35,
        max_unknown_attempts=5,
        max_workers=2,
        debug_stats=None,
        quality_submit_min=0.40,
        quality_submit_hard=0.82,
        quality_gain_min=0.05,
        quality_retry_interval=5
    ):
        self.model_name = model_name
        self.match_threshold = match_threshold
        self.lock_threshold = lock_threshold
        self.max_unknown_attempts = max_unknown_attempts

        self.quality_submit_min = quality_submit_min
        self.quality_submit_hard = quality_submit_hard
        self.quality_gain_min = quality_gain_min
        self.quality_retry_interval = quality_retry_interval

        self.employee_db = self._load_db(db_path)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self.processing_ids = set()
        self.track_states = {}
        self.debug_stats = debug_stats

    def _load_db(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as error:
            print(f"Warning: Could not load DB from {path}: {error}")
            return {}

    def _create_default_state(self):
        return {
            "status": "scanning",
            "best_name": None,
            "best_dist": None,
            "best_area": 0,
            "best_quality": 0.0,
            "last_submitted_quality": 0.0,
            "attempts": 0,
            "last_face_crop": None,
            "last_seen_frame": 0,
            "logged": False,
            "ever_had_face": False,
            "last_attempt_frame": 0,
        }

    def get_display_name(self, track_id):
        state = self.track_states.get(track_id)

        if not state:
            return f"ID {track_id} (Scanning...)"

        if state["status"] == "identified":
            return state["best_name"]

        if state["status"] == "unknown":
            return "Unknown"

        if state["best_name"] is not None and state["best_dist"] is not None:
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

    def should_process_face(self, track_id, face_area, quality_score, current_frame):
        state = self.track_states.setdefault(track_id, self._create_default_state())

        if state["status"] in {"identified", "unknown"}:
            return False

        if track_id in self.processing_ids:
            return False

        if quality_score >= self.quality_submit_hard:
            return True

        if quality_score < self.quality_submit_min:
            return False

        if state["best_area"] == 0:
            return True

        if quality_score >= state["best_quality"] + self.quality_gain_min:
            return True

        if current_frame - state["last_attempt_frame"] >= self.quality_retry_interval:
            return True

        return False

    def submit_face(self, track_id, face_crop, face_area, quality, current_frame):
        if face_crop is None or face_crop.size == 0:
            return False

        state = self.track_states.setdefault(track_id, self._create_default_state())

        self.processing_ids.add(track_id)
        state["last_attempt_frame"] = current_frame
        state["last_submitted_quality"] = quality.get("score", 0.0)

        self.executor.submit(
            self._process_face_async,
            track_id,
            face_crop.copy(),
            face_area,
            quality
        )

        return True

    def match_face(self, new_embedding):
        best_match = "Unknown"
        min_dist = 1.0

        for name, embeddings in self.employee_db.items():
            for db_embedding in embeddings:
                dist = distance.cosine(new_embedding, db_embedding)

                if dist < min_dist:
                    min_dist = dist
                    best_match = name

        return best_match, min_dist

    def _process_face_async(self, track_id, face_crop, face_area, quality):
        try:
            print(
                f"[AI] Processing track {track_id} | "
                f"quality={quality.get('score', 0.0):.3f} | "
                f"sharpness={quality.get('sharpness', 0.0):.1f}"
            )

            start_time = time.time()

            results = DeepFace.represent(
                img_path=face_crop,
                model_name=self.model_name,
                enforce_detection=False,
                detector_backend="skip"
            )

            elapsed = time.time() - start_time
            print(f"[TIMING] DeepFace.represent took {elapsed:.3f}s")

            if not results:
                self._register_failed_attempt(track_id)
                return

            new_embedding = results[0]["embedding"]
            name, dist = self.match_face(new_embedding)

            if "amit" in self.employee_db:
                for i, db_embedding in enumerate(self.employee_db["amit"]):
                    d = distance.cosine(new_embedding, db_embedding)
                    print(f"[COMPARE] amit[{i}] = {d:.4f}")

            if "dotan" in self.employee_db:
                for i, db_embedding in enumerate(self.employee_db["dotan"]):
                    d = distance.cosine(new_embedding, db_embedding)
                    print(f"[COMPARE] dotan[{i}] = {d:.4f}")

            decision = "accepted" if dist < self.match_threshold else "rejected"
            print(
                f"[Match] Track {track_id} | candidate={name} | "
                f"distance={dist:.4f} | decision={decision}"
            )

            state = self.track_states.setdefault(track_id, self._create_default_state())
            quality_score = quality.get("score", 0.0)

            if face_area > state["best_area"]:
                state["best_area"] = face_area

            if quality_score > state["best_quality"]:
                state["best_quality"] = quality_score

            if state["best_dist"] is None or dist < state["best_dist"]:
                state["best_dist"] = dist
                state["best_name"] = name
                state["last_face_crop"] = face_crop.copy()

            if dist < self.lock_threshold:
                state["status"] = "identified"
                state["attempts"] = 0

                print(f"[LOCK] Track {track_id} locked as {name}")

                if self.debug_stats is not None:
                    self.debug_stats["matched_and_locked"] += 1

            elif dist < self.match_threshold:
                state["attempts"] = 0

                print(f"[Soft Match] Track {track_id} matched {name} at {dist:.4f}")

                if self.debug_stats is not None:
                    self.debug_stats["matched_below_threshold"] += 1

            else:
                if state["best_dist"] is not None and state["best_dist"] < self.match_threshold:
                    print(
                        f"[Ignore Fail] Track {track_id} already has valid match "
                        f"({state['best_dist']:.4f})"
                    )
                    return

                state["attempts"] += 1

                print(
                    f"[Attempt] {state['attempts']}/{self.max_unknown_attempts} "
                    f"(not marking Unknown while track is still visible)"
                )

                if self.debug_stats is not None:
                    self.debug_stats["unknown_after_match"] += 1

                # Do not mark as Unknown here.
                # Unknown is decided only in cleanup_stale_tracks when the track disappears.

        except Exception as error:
            print(f"[AI Error] {error}")

            if self.debug_stats is not None:
                self.debug_stats["embedding_failed"] += 1

            self._register_failed_attempt(track_id)

        finally:
            self.processing_ids.discard(track_id)

    def _register_failed_attempt(self, track_id):
        state = self.track_states.setdefault(track_id, self._create_default_state())

        if state["best_dist"] is not None and state["best_dist"] < self.match_threshold:
            return

        state["attempts"] += 1

        print(
            f"[Failed Attempt] Track {track_id} | "
            f"{state['attempts']}/{self.max_unknown_attempts} "
            f"(not marking Unknown while track is still visible)"
        )

        # Do not mark as Unknown here.
        # Unknown is decided only in cleanup_stale_tracks when the track disappears.

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

        decision_type = "unknown"

        if state["status"] == "identified":
            if state["best_dist"] is not None and state["best_dist"] < self.lock_threshold:
                decision_type = "locked"
            else:
                decision_type = "soft_match"

        return {
            "name": state["best_name"] if state["status"] == "identified" else "Unknown",
            "distance": state["best_dist"],
            "crop": state["last_face_crop"],
            "quality": state.get("best_quality", 0.0),
            "attempts": state.get("attempts", 0),
            "decision_type": decision_type,
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