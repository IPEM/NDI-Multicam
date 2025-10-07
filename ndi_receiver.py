import cv2
import numpy as np
import threading
import queue
import time
from datetime import datetime
import os
import NDIlib as ndi

class NDIReceiver:
    def __init__(self, source_name):
        self.source_name = source_name
        self.frame_queue = queue.Queue(maxsize=5)
        self.running = False
        self.ndi_recv = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
    def connect(self):
        """Connect to NDI source"""
        if not ndi.initialize():
            return False
        
        # Find sources
        ndi_find = ndi.find_create_v2()
        if ndi_find is None:
            return False
        
        # Wait for sources
        print(f"Looking for NDI source: {self.source_name}")
        sources = []
        for _ in range(20):  # Try for 10 seconds
            sources = ndi.find_get_current_sources(ndi_find)
            for source in sources:
                if source.ndi_name == self.source_name:
                    print(f"Found: {self.source_name}")
                    break
            if any(s.ndi_name == self.source_name for s in sources):
                break
            time.sleep(0.5)
        
        # Find the source
        source = None
        for s in sources:
            if s.ndi_name == self.source_name:
                source = s
                break
        
        if source is None:
            print(f"Could not find NDI source: {self.source_name}")
            ndi.find_destroy(ndi_find)
            return False
        
        # Create receiver with low latency
        ndi_recv_create = ndi.RecvCreateV3()
        ndi_recv_create.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
        ndi_recv_create.bandwidth = ndi.RECV_BANDWIDTH_HIGHEST
        ndi_recv_create.allow_video_fields = False
        
        self.ndi_recv = ndi.recv_create_v3(ndi_recv_create)
        
        if self.ndi_recv is None:
            ndi.find_destroy(ndi_find)
            return False
        
        # Connect to source
        ndi.recv_connect(self.ndi_recv, source)
        ndi.find_destroy(ndi_find)
        
        return True
    
    def receive_loop(self):
        """Receive frames in separate thread"""
        while self.running:
            t, v, _, _ = ndi.recv_capture_v2(self.ndi_recv, 100)
            
            if t == ndi.FRAME_TYPE_VIDEO:
                # Convert NDI frame to numpy array
                frame = np.copy(v.data)
                ndi.recv_free_video_v2(self.ndi_recv, v)
                
                # Convert BGRA to BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                with self.frame_lock:
                    self.latest_frame = frame
    
    def get_latest_frame(self):
        """Get the latest received frame"""
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def start(self):
        """Start receiving"""
        if not self.connect():
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self.receive_loop)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def stop(self):
        """Stop receiving"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.ndi_recv:
            ndi.recv_destroy(self.ndi_recv)


class MultiCameraRecorder:
    def __init__(self, source_names):
        self.source_names = source_names
        self.receivers = {}
        self.writers = {}
        self.recording = False
        self.running = False
        self.output_dir = None
        
    def connect_sources(self):
        """Connect to all NDI sources"""
        print("\nConnecting to NDI sources...")
        
        for name in self.source_names:
            receiver = NDIReceiver(name)
            if receiver.start():
                self.receivers[name] = receiver
                print(f"✓ Connected to {name}")
            else:
                print(f"✗ Failed to connect to {name}")
        
        if not self.receivers:
            print("No sources connected!")
            return False
        
        print(f"\nConnected to {len(self.receivers)} sources")
        return True
    
    def start_recording(self):
        """Start recording all streams"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = f"recordings/{timestamp}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        for name, receiver in self.receivers.items():
            # Get frame to determine size
            frame = receiver.get_latest_frame()
            if frame is not None:
                h, w = frame.shape[:2]
                output_path = f"{self.output_dir}/{name}.mp4"
                writer = cv2.VideoWriter(output_path, fourcc, 60, (w, h))
                self.writers[name] = writer
        
        self.recording = True
        print(f"\n🔴 RECORDING to: {self.output_dir}")
    
    def stop_recording(self):
        """Stop recording"""
        self.recording = False
        
        for writer in self.writers.values():
            writer.release()
        
        self.writers.clear()
        print(f"\n⏹ Recording stopped: {self.output_dir}")
    
    def create_grid_display(self, frames):
        """Create grid display of all cameras"""
        if not frames:
            return None
        
        # Determine grid layout
        num_cams = len(frames)
        if num_cams == 1:
            rows, cols = 1, 1
        elif num_cams == 2:
            rows, cols = 1, 2
        elif num_cams <= 4:
            rows, cols = 2, 2
        else:
            rows, cols = 2, 3
        
        # Get first frame to determine size
        first_frame = list(frames.values())[0]
        if first_frame is None:
            return None
        
        h, w = first_frame.shape[:2]
        
        # Scale down for display
        display_w = w // 2
        display_h = h // 2
        
        # Create grid
        grid = np.zeros((display_h * rows, display_w * cols, 3), dtype=np.uint8)
        
        for idx, (name, frame) in enumerate(frames.items()):
            if frame is None:
                continue
            
            row = idx // cols
            col = idx % cols
            
            if row >= rows:
                break
            
            # Add recording indicator if recording
            if self.recording:
                # Red border
                cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 0, 255), 20)
                # Red background behind text
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 180), -1)
                frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            # Resize for grid
            resized = cv2.resize(frame, (display_w, display_h))
            
            # Place in grid
            y_start = row * display_h
            y_end = y_start + display_h
            x_start = col * display_w
            x_end = x_start + display_w
            
            grid[y_start:y_end, x_start:x_end] = resized
        
        # Add recording indicator to grid
        if self.recording:
            cv2.circle(grid, (40, 40), 20, (0, 0, 255), -1)
            cv2.putText(grid, "RECORDING", (70, 50),
                       cv2.FONT_HERSHEY_BOLD, 1.0, (0, 0, 255), 3)
        
        return grid
    
    def run(self):
        """Main display and recording loop"""
        self.running = True
        
        print("\nControls:")
        print("  'r' - Start/Stop recording")
        print("  'q' - Quit")
        print("  's' - Show statistics")
        
        frame_counts = {name: 0 for name in self.receivers.keys()}
        start_time = time.time()
        
        while self.running:
            # Get latest frame from each receiver
            frames = {}
            for name, receiver in self.receivers.items():
                frame = receiver.get_latest_frame()
                if frame is not None:
                    frames[name] = frame
                    frame_counts[name] += 1
                    
                    # Write frame if recording
                    if self.recording and name in self.writers:
                        self.writers[name].write(frame)
            
            # Create and display grid
            grid = self.create_grid_display(frames)
            
            if grid is not None:
                cv2.imshow('NDI Multi-Camera Receiver', grid)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('r'):
                if self.recording:
                    self.stop_recording()
                else:
                    self.start_recording()
            elif key == ord('s'):
                elapsed = time.time() - start_time
                print("\nStatistics:")
                for name, count in frame_counts.items():
                    fps = count / elapsed if elapsed > 0 else 0
                    print(f"  {name}: {count} frames, {fps:.1f} fps")
        
        self.stop()
    
    def stop(self):
        """Cleanup"""
        self.running = False
        
        if self.recording:
            self.stop_recording()
        
        for receiver in self.receivers.values():
            receiver.stop()
        
        cv2.destroyAllWindows()
        ndi.destroy()
        
        print("Receiver stopped")


def main():
    print("="*60)
    print("NDI MULTI-CAMERA RECEIVER")
    print("="*60)
    
    # Get source names
    print("\nEnter NDI source names (camera names from transmitters)")
    print("Enter one per line, empty line when done:")
    
    source_names = []
    while True:
        name = input(f"Source {len(source_names) + 1}: ").strip()
        if not name:
            break
        source_names.append(name)
    
    if not source_names:
        print("No sources specified!")
        return
    
    print(f"\nLooking for sources: {', '.join(source_names)}")
    
    # Create and run recorder
    try:
        recorder = MultiCameraRecorder(source_names)
        if recorder.connect_sources():
            time.sleep(1)  # Let receivers stabilize
            recorder.run()
        else:
            print("Failed to connect to sources")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
