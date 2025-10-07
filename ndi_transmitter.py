import cv2
import numpy as np
import threading
import queue
import time
from pythonosc import dispatcher, osc_server
import NDIlib as ndi
import socket

class TimecodeReceiver:
    def __init__(self, port=6667):
        self.port = port
        self.latest_timecode = "00:00:00:00:0"
        self.timecode_lock = threading.Lock()
        self.running = False
        self.measured_offset = 0.0  # Can be adjusted if needed
        
    def timecode_handler(self, address, *args):
        """Handle incoming OSC timecode messages"""
        if args:
            with self.timecode_lock:
                self.latest_timecode = str(args[0])
    
    def get_timecode(self):
        """Get the latest timecode"""
        with self.timecode_lock:
            return self.latest_timecode
    
    def start(self):
        """Start listening for OSC timecode"""
        self.running = True
        
        disp = dispatcher.Dispatcher()
        disp.map("/timecode", self.timecode_handler)
        
        # Create server that listens on multicast
        self.server = osc_server.ThreadingOSCUDPServer(
            ("0.0.0.0", self.port), disp
        )
        
        # Enable multicast reception
        sock = self.server.socket
        group = socket.inet_aton("239.255.0.1")  # Multicast group
        mreq = group + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"Listening for OSC timecode on port {self.port} (multicast 239.255.0.1)")
    
    def stop(self):
        """Stop the OSC server"""
        self.running = False
        if hasattr(self, 'server'):
            self.server.shutdown()


class NDITransmitter:
    def __init__(self, camera_name, camera_id=0):
        self.camera_name = camera_name
        self.camera_id = camera_id
        self.width = 1280
        self.height = 720
        self.fps = 60
        
        # Initialize camera
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        self._setup_camera()
        
        # Initialize NDI
        if not ndi.initialize():
            raise RuntimeError("Failed to initialize NDI")
        
        # Create NDI sender with low latency settings
        ndi_send_create = ndi.SendCreate()
        ndi_send_create.ndi_name = camera_name
        ndi_send_create.clock_video = False  # Don't use NDI clock
        ndi_send_create.clock_audio = False
        
        self.ndi_send = ndi.send_create(ndi_send_create)
        
        if self.ndi_send is None:
            raise RuntimeError("Failed to create NDI sender")
        
        # Timecode receiver
        self.timecode_receiver = TimecodeReceiver()
        
        # Control
        self.running = False
        
        print(f"NDI Sender '{camera_name}' initialized")
    
    def _setup_camera(self):
        """Configure camera settings"""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Disable auto settings for consistent timing
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        print(f"Camera configured: {actual_w}x{actual_h} @ {actual_fps}fps")
    
    def add_overlay(self, frame, timecode):
        """Add camera name and timecode overlay to frame"""
        # Create semi-transparent overlay at top
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (self.width, 80), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
        
        # Add camera name
        cv2.putText(frame, self.camera_name, (10, 35),
                   cv2.FONT_HERSHEY_BOLD, 1.2, (0, 255, 255), 3)
        
        # Add timecode
        cv2.putText(frame, f"TC: {timecode}", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return frame
    
    def run(self):
        """Main transmission loop"""
        self.running = True
        self.timecode_receiver.start()
        
        print(f"\nTransmitting '{self.camera_name}' on NDI network...")
        print("Press 'q' in preview window to quit\n")
        
        frame_count = 0
        start_time = time.time()
        
        while self.running:
            ret, frame = self.cap.read()
            
            if not ret:
                print("Failed to read frame from camera")
                continue
            
            # Get current timecode
            timecode = self.timecode_receiver.get_timecode()
            
            # Add overlay
            frame = self.add_overlay(frame, timecode)
            
            # Convert to NDI format (BGRA)
            frame_bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            
            # Create NDI video frame
            video_frame = ndi.VideoFrameV2()
            video_frame.data = frame_bgra
            video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRA
            video_frame.xres = self.width
            video_frame.yres = self.height
            video_frame.frame_rate_N = self.fps * 1000
            video_frame.frame_rate_D = 1000
            video_frame.timecode = ndi.send_timecode_synthesize  # Auto timecode
            
            # Send frame with async mode for lowest latency
            ndi.send_send_video_v2(self.ndi_send, video_frame)
            
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
        
        if self.ndi_send:
            ndi.send_destroy(self.ndi_send)
        
        ndi.destroy()
        cv2.destroyAllWindows()
        
        print("Transmitter stopped")


def list_cameras():
    """List available cameras"""
    print("Detecting cameras...")
    cameras = []
    
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                cameras.append(i)
            cap.release()
    
    return cameras


def main():
    print("="*60)
    print("NDI CAMERA TRANSMITTER")
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
    
    print(f"\nAvailable cameras: {cameras}")
    
    if len(cameras) == 1:
        camera_id = cameras[0]
        print(f"Using camera {camera_id}")
    else:
        while True:
            try:
                camera_id = int(input(f"Select camera ID {cameras}: ").strip())
                if camera_id in cameras:
                    break
                print("Invalid camera ID")
            except ValueError:
                print("Please enter a number")
    
    # Create and run transmitter
    try:
        transmitter = NDITransmitter(camera_name, camera_id)
        transmitter.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
