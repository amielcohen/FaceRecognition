import sqlite3
import os

def setup_database():
    # Create the data directory if it does not exist
    if not os.path.exists('database'):
        os.makedirs('database')
    
    # Connect to the database (it will be created if it does not exist)
    conn = sqlite3.connect('database/vision_db.sqlite')
    cursor = conn.cursor()

    # 1. Create table for camera and NVR settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS camera_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_name TEXT NOT NULL,
            rtsp_url TEXT NOT NULL,
            
            -- Detection settings (thresholds and sensitivity)
            min_face_area INTEGER DEFAULT 2500,
            lock_identity_threshold FLOAT DEFAULT 0.35,
            area_update_ratio FLOAT DEFAULT 1.2,
            
            -- NVR and video archive settings
            retention_hours INTEGER DEFAULT 24,
            segment_minutes INTEGER DEFAULT 60,
            record_res_width INTEGER DEFAULT 1280,
            record_fps INTEGER DEFAULT 15
        )
    ''')

    # 2. Create table for identities (authorized employees database)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Create table for attendance logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_id INTEGER,
            confidence_score FLOAT,
            entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            crop_path TEXT,
            FOREIGN KEY (identity_id) REFERENCES identities(id)
        )
    ''')

    # Insert default settings only if the table is empty
    cursor.execute("SELECT COUNT(*) FROM camera_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO camera_settings (
                camera_name, rtsp_url, min_face_area, 
                lock_identity_threshold, retention_hours
            ) VALUES (?, ?, ?, ?, ?)
        ''', ('Main_Entrance', '0', 2500, 0.2, 24))
        print("Default camera settings inserted.")

    conn.commit()
    conn.close()
    print("Database and tables are ready!")

if __name__ == "__main__":
    setup_database()