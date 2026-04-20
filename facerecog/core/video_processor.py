import cv2
import threading
import time
import os
from datetime import datetime

class VideoProcessor:
    def __init__(self, camera_settings):
        self.settings = camera_settings
        
        # Convert URL to integer if it's a local camera (0, 1), otherwise keep as string (file/RTSP)
        url = self.settings['rtsp_url']
        source = int(url) if str(url).isdigit() else url
        
        print(f"Attempting to open source: {source}")
        self.cap = cv2.VideoCapture(source)
        
        if not self.cap.isOpened():
            print(f"CRITICAL: Could not open source {source}")
        else:
            print(f"Success: Source {source} is open.")
            
        self.frame = None
        self.stopped = False
        self.out = None
        self.current_segment_start = None

        # Ensure directory for video recordings exists
        if not os.path.exists('data/recordings'):
            os.makedirs('data/recordings')

    def start(self):
        """Starts the background thread to read frames from the video source"""
        threading.Thread(target=self._update, args=(), daemon=True).start()
        return self

    def _update(self):
        """Internal thread loop to continuously grab frames"""
        while not self.stopped:
            ret, frame = self.cap.read()
            if not ret:
                # If it's a video file, loop back to the beginning
                if isinstance(self.cap.get(cv2.CAP_PROP_POS_FRAMES), float):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            
            self.frame = frame
            time.sleep(0.01) # Prevent CPU over-utilization

    def get_frame(self):
        """Returns the most recent frame grabbed from the source"""
        return self.frame

    def stop(self):
        """Safely stops the thread and releases hardware resources"""
        self.stopped = True
        if self.out:
            self.out.release()
        self.cap.release()
        cv2.destroyAllWindows()