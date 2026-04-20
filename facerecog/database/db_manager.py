import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path=None):
        # If no path is provided, locate it relative to the project root
        if db_path is None:
            # Find the root directory (three levels up from this file)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, 'database', 'vision_db.sqlite')
        else:
            self.db_path = db_path
            
        print(f"Connecting to database at: {self.db_path}")

    def _get_connection(self):
        """Internal method to establish a connection with the SQLite database"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found at {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        # Allows accessing columns by name instead of index (e.g., row['name'])
        conn.row_factory = sqlite3.Row
        return conn

    def load_camera_settings(self, camera_id=1):
        """Fetches camera and stream configuration from the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM camera_settings WHERE id = ?", (camera_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except sqlite3.Error as e:
            print(f"Error loading settings: {e}")
        return None

    def log_attendance(self, identity_id, score, crop_path):
        """Records a successful recognition event in the attendance log"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO attendance_logs (identity_id, confidence_score, crop_path)
                    VALUES (?, ?, ?)
                ''', (identity_id, score, crop_path))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Error logging attendance: {e}")

    def get_known_faces(self):
        """Retrieves all registered identities and their image paths"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, image_path FROM identities")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching identities: {e}")
        return []