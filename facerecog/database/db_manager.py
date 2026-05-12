import os
import sqlite3


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _get_connection(self):
        """
        Create a SQLite connection with row access by column name.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self):
        """
        Create the database directory and initialize all required tables.
        """
        db_dir = os.path.dirname(self.db_path)

        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main system configuration table.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS camera_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    camera_name TEXT NOT NULL,

                    rtsp_url TEXT NOT NULL DEFAULT '0',

                    preset TEXT NOT NULL DEFAULT 'balanced',

                    min_face_area INTEGER NOT NULL DEFAULT 2500,

                    area_update_ratio REAL NOT NULL DEFAULT 1.2,

                    match_identity_threshold REAL NOT NULL DEFAULT 0.4,

                    lock_identity_threshold REAL NOT NULL DEFAULT 0.2,

                    max_unknown_attempts INTEGER NOT NULL DEFAULT 5,

                    frame_skip_interval INTEGER NOT NULL DEFAULT 1,

                    retention_hours INTEGER NOT NULL DEFAULT 24,

                    segment_minutes INTEGER NOT NULL DEFAULT 60,

                    record_res_width INTEGER NOT NULL DEFAULT 1280,

                    record_fps INTEGER NOT NULL DEFAULT 15
                )
            """)

            # Employee identity table.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL UNIQUE,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Recognition / attendance event log table.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    identity_id INTEGER,

                    matched_name TEXT,

                    distance REAL,

                    track_id INTEGER,

                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    crop_path TEXT,

                    FOREIGN KEY (identity_id)
                    REFERENCES identities(id)
                )
            """)

            # Insert a default camera row only if the table is empty.
            cursor.execute(
                "SELECT COUNT(*) AS count FROM camera_settings"
            )

            count = cursor.fetchone()["count"]

            if count == 0:
                cursor.execute("""
                    INSERT INTO camera_settings (
                        camera_name,
                        rtsp_url,
                        preset,
                        min_face_area,
                        area_update_ratio,
                        match_identity_threshold,
                        lock_identity_threshold,
                        max_unknown_attempts,
                        frame_skip_interval,
                        retention_hours,
                        segment_minutes,
                        record_res_width,
                        record_fps
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "Main Camera",
                    "0",
                    "balanced",
                    2500,
                    1.2,
                    0.4,
                    0.2,
                    5,
                    1,
                    24,
                    60,
                    1280,
                    15
                ))

            conn.commit()

    def load_camera_settings(self, camera_id: int = 1):
        """
        Load the settings row for a specific camera.
        Returns a dictionary or None if not found.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM camera_settings WHERE id = ?",
                    (camera_id,)
                )

                row = cursor.fetchone()

                return dict(row) if row else None

        except sqlite3.Error as e:
            print(f"Error loading camera settings: {e}")

            return None

    def update_camera_settings(
        self,
        camera_id: int,
        **kwargs
    ) -> bool:
        """
        Update one or more camera setting fields dynamically.
        """

        allowed_fields = {
            "camera_name",
            "rtsp_url",
            "preset",
            "min_face_area",
            "area_update_ratio",
            "match_identity_threshold",
            "lock_identity_threshold",
            "max_unknown_attempts",
            "frame_skip_interval",
            "retention_hours",
            "segment_minutes",
            "record_res_width",
            "record_fps",
        }

        update_fields = {
            key: value
            for key, value in kwargs.items()
            if key in allowed_fields
        }

        if not update_fields:
            return False

        set_clause = ", ".join([
            f"{key} = ?"
            for key in update_fields.keys()
        ])

        values = list(update_fields.values())

        values.append(camera_id)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    f"""
                    UPDATE camera_settings
                    SET {set_clause}
                    WHERE id = ?
                    """,
                    values
                )

                conn.commit()

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            print(f"Error updating camera settings: {e}")

            return False

    def ensure_identity(self, name: str):
        """
        Ensure an identity row exists for the given name.
        Returns the identity ID.
        """

        if not name or name == "Unknown":
            return None

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id FROM identities WHERE name = ?",
                    (name,)
                )

                row = cursor.fetchone()

                if row:
                    return row["id"]

                cursor.execute(
                    "INSERT INTO identities (name) VALUES (?)",
                    (name,)
                )

                conn.commit()

                return cursor.lastrowid

        except sqlite3.Error as e:
            print(
                f"Error ensuring identity '{name}': {e}"
            )

            return None

    def get_identity_id_by_name(self, name: str):
        """
        Return the identity ID for a given employee name.
        """

        if not name or name == "Unknown":
            return None

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id FROM identities WHERE name = ?",
                    (name,)
                )

                row = cursor.fetchone()

                return row["id"] if row else None

        except sqlite3.Error as e:
            print(
                f"Error getting identity ID for '{name}': {e}"
            )

            return None

    def log_attendance_event(
        self,
        matched_name: str,
        distance: float,
        track_id: int,
        crop_path: str = None
    ) -> bool:
        """
        Save a recognition result into the attendance log table.
        """

        identity_id = self.ensure_identity(
            matched_name
        )

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO attendance_logs (
                        identity_id,
                        matched_name,
                        distance,
                        track_id,
                        crop_path
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    identity_id,
                    matched_name,
                    distance,
                    track_id,
                    crop_path
                ))

                conn.commit()

                return True

        except sqlite3.Error as e:
            print(
                f"Error logging attendance event: {e}"
            )

            return False