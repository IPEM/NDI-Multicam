import cv2
import numpy as np
import threading
import queue
import time
from pythonosc import dispatcher, osc_server
import socket

class TimecodeReceiver:
    def __init__(self, port=6575):
        self.port = port
        self.latest_timecode = "00:00:00:00:0"
        self.timecode_lock = threading.Lock()
        self.running = False
        self.measured_offset = 0.0  # Can be adjusted if needed
        
    def timecode_handler(self, address, *args):
        """Handle incoming OSC timecode messages"""
        if args:
            with self.timecode_lock:
                self.latest_timecode = str(args[0:5])
    
    def get_timecode(self):
        """Get the latest timecode"""
        with self.timecode_lock:
            return self.latest_timecode
    
    def start(self):
        """Start listening for OSC timecode"""
        self.running = True
        
        disp = dispatcher.Dispatcher()
        disp.map("/asil/clock", self.timecode_handler)
        
        # sock = self.server.socket
        ip = socket.gethostbyname(socket.gethostname())
        
        # Create server that listens on multicast
        self.server = osc_server.ThreadingOSCUDPServer(
            (ip, self.port), disp
        )
        
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"Listening for OSC timecode on port {self.port} (multicast 239.255.0.1)")
        print(f"OSC address: /asil/clock")
    
    def stop(self):
        """Stop the OSC server"""
        self.running = False
        if hasattr(self, 'server'):
            self.server.shutdown()

			
			
			
class LocalSaver:
    def __init__(self, camera_name, camera_id=0):
        self.camera_name = camera_name
        self.camera_id = camera_id
        self.width = 1280
        self.height = 720
        self.fps = 30
        
        # Initialize camera
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        self._setup_camera()
        
        # Timecode receiver
        self.timecode_receiver = TimecodeReceiver()
        
        # Control
        self.running = False
        
        print(f"'{camera_name}' initialized")
    
    def _setup_camera(self):
        """Configure camera settings"""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Disable auto settings for consistent timing
        # self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        # self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        # self.cap.set(cv2.CAP_PROP_EXPOSURE, -1)  # Try values between -13 to -1
		
        
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        print(f"Camera configured: {actual_w}x{actual_h} @ {actual_fps}fps")
    
    def add_overlay(self, frame, timecode, actual_fps):
        """Add camera name and timecode overlay to frame"""
        # Create semi-transparent overlay at top
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (self.width, 80), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
        
        # Add camera name
        cv2.putText(frame, self.camera_name, (10, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
				   
        # Add fps name
        cv2.putText(frame, f"FPS: {actual_fps}", (600, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        
        # Add timecode
        cv2.putText(frame, f"TC: {timecode}", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        print(f"Timecode: {timecode}")
        return frame
    
    def run(self):
        """Main transmission loop"""
        self.running = True
        self.timecode_receiver.start()
        
        print(f"\showing '{self.camera_name}' ")
        print("Press 'q' in preview window to quit\n")
        
        frame_count = 0
        start_time = time.time()
        actual_fps = 0
		
        while self.running:
            ret, frame = self.cap.read()
            
            if not ret:
                print("Failed to read frame from camera")
                continue
            
            # Get current timecode
            timecode = self.timecode_receiver.get_timecode()
            
            # Add overlay
            frame = self.add_overlay(frame, timecode, actual_fps)

            frame_count += 1
            
            # Show preview (scaled down)
            preview = cv2.resize(frame, (640, 360))
            cv2.imshow(f'Preview - {self.camera_name}', preview)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print stats every 60 frames
            if frame_count % 60 == 0:
                elapsed = time.time() - start_time
                actual_fps = frame_count / elapsed
                print(f"Frames: {frame_count}, FPS: {actual_fps:.1f}, TC: {timecode}")
        
        self.stop()
    
    def stop(self):
        """Cleanup resources"""
        self.running = False
        self.timecode_receiver.stop()
        
        if self.cap:
            self.cap.release()
        
        cv2.destroyAllWindows()
        
        print("Transmitter stopped")

			
			
			
def list_cameras():
    """List available cameras with details"""
    print("Detecting cameras...")
    cameras = []
    
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                cameras.append({
                    'id': i,
                    'width': width,
                    'height': height,
                    'fps': fps
                })
            cap.release()
    
    return cameras


def main():
    print("="*60)
    print("NDI CAMERA SAVER")
    print("="*60)
    
    # Get camera name
    camera_name = input("\nEnter unique camera name (e.g., CAM_A, CAM_B): ").strip()
    
    if not camera_name:
        print("Camera name cannot be empty!")
        return
    
    # List and select camera
    cameras = list_cameras()
    
    if not cameras:
        print("No cameras detected!")
        return
    
    print(f"\n{'='*60}")
    print("Available cameras:")
    print(f"{'='*60}")
    for cam in cameras:
        print(f"  [{cam['id']}] Camera {cam['id']} - {cam['width']}x{cam['height']} @ {cam['fps']}fps")
    print(f"{'='*60}")
    
    if len(cameras) == 1:
        camera_id = cameras[0]['id']
        print(f"\nUsing camera {camera_id}")
    else:
        while True:
            try:
                cam_ids = [c['id'] for c in cameras]
                camera_id = int(input(f"\nSelect camera ID {cam_ids}: ").strip())
                if camera_id in cam_ids:
                    break
                print("Invalid camera ID")
            except ValueError:
                print("Please enter a number")
    
    # Show selected camera info
    selected = next(c for c in cameras if c['id'] == camera_id)
    print(f"\nSelected: Camera {camera_id}")
    print(f"  Name: {camera_name}")
    print(f"  Current resolution: {selected['width']}x{selected['height']}")
    print(f"  Current FPS: {selected['fps']}")
    print(f"  Will configure to: 1280x720 @ 30fps")
    
    # Create and run transmitter
    try:
        transmitter = LocalSaver(camera_name, camera_id)
        transmitter.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
