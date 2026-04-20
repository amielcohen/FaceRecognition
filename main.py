import cv2
import sys
import os

# Add root directory to sys.path to resolve internal imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from facerecog.database.db_manager import DatabaseManager
from facerecog.core.video_processor import VideoProcessor
from facerecog.core.detector import PersonDetector

def main():
    # 1. Initialize database connection (Path updated for package structure)
    db_path = os.path.join('facerecog', 'database', 'vision_db.sqlite')
    db = DatabaseManager(db_path)
    
    # Load camera settings from the database
    settings = db.load_camera_settings(camera_id=1)
    if not settings:
        print("Error: Could not load settings from database.")
        return

    # --- For local testing with video file, uncomment the line below ---
    # settings['rtsp_url'] = "amitWalk360.mp4" 

    # 2. Initialize system components
    vp = VideoProcessor(settings)
    detector = PersonDetector() # Initialize YOLO model
    
    # Start video capture thread
    vp.start()
    
    print(f"Starting system: {settings['camera_name']}")
    print("!!! CLICK ON THE VIDEO WINDOW AND PRESS 'Q' TO QUIT !!!")

    try:
        while True:
            # 3. Retrieve the latest frame from the video thread
            frame = vp.get_frame()
            
            if frame is not None:
                # 4. Perform person detection (YOLOv8)
                detections = detector.detect(frame)
                
                # 5. Draw detection results on the frame
                for det in detections:
                    x1, y1, x2, y2 = det['bbox']
                    track_id = det['track_id']
                    
                    # Draw green bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Display track ID above the box
                    cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # 6. Display the processed frame
                cv2.imshow(settings['camera_name'], frame)
            
            # Exit loop if 'q' is pressed (window must be in focus)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nSystem interrupted by user.")
    
    finally:
        # 7. Clean cleanup of resources
        print("Cleaning up and closing...")
        vp.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()