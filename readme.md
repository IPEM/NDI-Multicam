# NDI Multi-Camera Synchronization System

A distributed camera capture system using OSC timecode synchronization and NDI streaming over LAN.

## System Architecture

- **4 Transmitter Laptops**: Each runs `transmitter.py` with one webcam
- **1 Receiver Computer**: Runs `receiver.py` to capture and record all streams
- **OSC Timecode Source**: Broadcasts timecode at 120Hz to multicast group
- **NDI Network**: Low-latency video streaming over LAN

## Prerequisites Installation

### On ALL Computers (Transmitters + Receiver):

1. **Install Python 3.8+**
   - Download from: https://www.python.org/downloads/
   - ✓ Check "Add Python to PATH" during installation

2. **Install NDI Runtime**
   - Download NDI Tools from: https://ndi.tv/tools/
   - Install and restart computer

3. **Run Installation Script**
   ```batch
   install.bat
   ```

## Network Setup

### All computers must be on the same LAN:
- Use Gigabit Ethernet (recommended) or fast WiFi
- Disable firewalls or allow:
  - UDP port 6667 (OSC timecode)
  - UDP port 5353 (mDNS for NDI discovery)
  - TCP port 5960-5969 (NDI data)

### Configure Windows Firewall:
```
Control Panel → Windows Defender Firewall → Allow an app
→ Add Python to allowed apps for Private networks
```

## Usage

### Step 1: Start OSC Timecode Source
Your timecode generator should send OSC messages:
- **Address**: `/timecode`
- **Format**: `hh:mm:ss:frame:subframe` (e.g., "01:23:45:12:2")
- **Rate**: 120 Hz
- **Protocol**: UDP Multicast
- **Group**: 239.255.0.1
- **Port**: 6667

### Step 2: Start Transmitters (on each laptop)

```bash
python transmitter.py
```

When prompted:
1. Enter unique camera name (e.g., `CAM_A`, `CAM_B`, `CAM_C`, `CAM_D`)
2. Select webcam from detected list
3. Preview window will open showing camera feed with timecode overlay

**Transmitter shows**:
- Camera name (top left)
- Current timecode (below name)
- Preview window (press 'q' to quit)

### Step 3: Start Receiver (on recording computer)

```bash
python receiver.py
```

When prompted:
1. Enter each camera name from transmitters (one per line)
2. Press Enter on empty line when done
3. Wait for connections (up to 10 seconds per source)

**Receiver shows**:
- Grid view of all cameras (2x2 for 4 cameras)
- Red border and "RECORDING" indicator when active

**Controls**:
- `r` - Start/Stop recording
- `q` - Quit
- `s` - Show frame statistics

### Step 4: Record

1. Ensure all cameras are visible in receiver grid
2. Press `r` to start recording
3. Red borders appear around all camera feeds
4. Press `r` again to stop recording

**Recordings saved to**:
```
recordings/YYYYMMDD_HHMMSS/
    CAM_A.mp4
    CAM_B.mp4
    CAM_C.mp4
    CAM_D.mp4
```

## Camera Settings

Transmitters are configured for:
- **Resolution**: 1280x720 (720p)
- **Frame rate**: 60 fps
- **Format**: MJPEG
- **Buffer**: 1 frame (minimum latency)
- **Auto-exposure**: OFF (manual for consistent timing)
- **Auto-focus**: OFF (manual for consistent timing)

## Troubleshooting

### Transmitter issues:

**"No cameras detected"**
- Check USB connection
- Ensure camera is not used by another application
- Try different USB port

**Timecode shows "00:00:00:00:0"**
- Check OSC source is running
- Verify network connectivity
- Confirm multicast group 239.255.0.1 is reachable
- Check port 6667 is not blocked

### Receiver issues:

**"Could not find NDI source"**
- Ensure transmitter is running
- Check both computers are on same network
- Verify NDI Runtime is installed
- Check firewall settings
- Try pinging between computers

**Poor video quality/stuttering**
- Use wired Gigabit Ethernet instead of WiFi
- Reduce network traffic (close other applications)
- Check network switch supports jumbo frames
- Verify no bandwidth limitations

**Cameras out of sync**
- Check all transmitters receive same OSC timecode
- Verify network latency is low (<10ms)
- Use wired connections for all computers
- Ensure all computers have similar performance

### General issues:

**High CPU usage**
- Reduce preview window size
- Close unnecessary applications
- Use hardware-accelerated video decoding if available

**Recording files are corrupted**
- Ensure enough disk space
- Use fast SSD for recordings
- Stop recording properly (press 'r', not 'q')

## Technical Specifications

### Latency:
- **Camera capture**: ~16ms (60fps)
- **OSC timecode**: <10ms (120Hz updates)
- **NDI transmission**: ~30-60ms (network dependent)
- **Total system latency**: ~50-100ms typical

### Bandwidth per camera (720p60):
- **MJPEG compressed**: ~50-80 Mbps
- **4 cameras total**: ~200-320 Mbps
- **Recommended**: Gigabit Ethernet (1000 Mbps)

### Synchronization:
- Timecode updates at 120Hz (8.3ms intervals)
- Subframe precision: 0-3 (within frame quarter)
- Expected sync accuracy: <1 frame (16.7ms at 60fps)

## Advanced Configuration

### Adjust exposure in transmitter.py:
```python
# Line ~50, change exposure value (-13 to -1)
self.cap1.set(cv2.CAP_PROP_EXPOSURE, -5)  # Lower = darker, faster
```

### Adjust timecode offset in transmitter.py:
```python
# Line ~15, if timecode consistently leads/lags
self.measured_offset = 0.033  # Add 33ms offset
```

### Change multicast group (all files):
```python
# transmitter.py line ~35
group = socket.inet_aton("239.255.0.1")  # Change to your group

# Must match your OSC sender configuration
```

### Change resolution/framerate in transmitter.py:
```python
# Lines ~46-48
self.width = 1920    # 1920 for 1080p, 1280 for 720p
self.height = 1080   # 1080 for 1080p, 720 for 720p
self.fps = 30        # 30, 60, or camera maximum
```

### Recording format in receiver.py:
```python
# Line ~110, change codec
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # mp4v, XVID, H264, etc.
```

## OSC Timecode Implementation Example

If you need to create your own OSC timecode sender:

### Python example:
```python
from pythonosc import udp_client
import time

client = udp_client.SimpleUDPClient("239.255.0.1", 6667)

frame = 0
while True:
    hh = frame // (30 * 60 * 60)
    mm = (frame // (30 * 60)) % 60
    ss = (frame // 30) % 60
    ff = frame % 30
    sf = (frame % 4)  # Subframe 0-3
    
    timecode = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}:{sf}"
    client.send_message("/timecode", timecode)
    
    frame += 1
    time.sleep(1/120)  # 120 Hz
```

### TouchDesigner example:
1. Create `OSC Out CHOP`
2. Set Network Address: `239.255.0.1:6667`
3. Set OSC Address: `/timecode`
4. Connect timecode string input
5. Set rate to 120 samples/second

## Performance Optimization

### For Transmitter Laptops:
1. **Disable power saving**:
   - Control Panel → Power Options → High Performance
   - Disable USB selective suspend
   - Disable sleep/hibernation

2. **Close background apps**:
   - Disable Windows Update during capture
   - Close antivirus real-time scanning
   - Disable OneDrive sync

3. **USB optimization**:
   - Use USB 3.0 ports
   - Don't use USB hubs
   - Update camera firmware

### For Receiver Computer:
1. **Use dedicated network interface** for NDI
2. **Fast storage**: SSD for recordings (500+ MB/s write)
3. **RAM**: 16GB+ recommended
4. **CPU**: Quad-core or better
5. **Disable preview** if recording is priority (comment out cv2.imshow)

## Network Configuration Best Practices

### Recommended Hardware:
- **Switch**: Gigabit, unmanaged or managed
- **Cables**: Cat6 or better
- **NICs**: Gigabit Ethernet on all computers

### Switch Configuration (if managed):
```
Enable: Jumbo Frames (MTU 9000)
Enable: IGMP Snooping (for multicast)
Disable: Flow Control
Priority: Set QoS high for ports with NDI traffic
```

### Windows Network Settings:
```
Network Adapter Properties:
- Disable "Large Send Offload"
- Enable "Receive Side Scaling"
- Set "Receive Buffers" to maximum
- Set "Transmit Buffers" to maximum
```

## Monitoring & Diagnostics

### Check NDI sources on network:
```bash
# Install NDI Tools, then run:
NDI Studio Monitor
# Shows all available NDI sources
```

### Test OSC timecode reception:
```python
# Run this on transmitter laptop
from pythonosc import dispatcher, osc_server
import socket

def handler(addr, *args):
    print(f"Received: {args}")

disp = dispatcher.Dispatcher()
disp.map("/timecode", handler)

server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", 6667), disp)

sock = server.socket
group = socket.inet_aton("239.255.0.1")
mreq = group + socket.inet_aton("0.0.0.0")
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

print("Listening for OSC on port 6667...")
server.serve_forever()
```

### Monitor network bandwidth:
- Windows: Task Manager → Performance → Ethernet
- Target: <80% utilization for stable streaming

## File Structure

```
project/
├── install.bat           # Prerequisites installer
├── transmitter.py        # Run on each camera laptop
├── receiver.py           # Run on recording computer
├── README.md            # This file
└── recordings/          # Created automatically
    └── YYYYMMDD_HHMMSS/
        ├── CAM_A.mp4
        ├── CAM_B.mp4
        ├── CAM_C.mp4
        └── CAM_D.mp4
```

## Known Limitations

1. **No hardware sync**: Cameras free-run, synced via timecode overlay only
2. **Network dependent**: Latency varies with network conditions
3. **CPU intensive**: 720p60 encoding/decoding requires good CPU
4. **No audio**: Video only (add audio sync in post-production)
5. **Windows only**: DirectShow backend is Windows-specific

## Alternative Configurations

### For 2 cameras only:
- Change grid layout in receiver.py (1x2 instead of 2x2)
- Reduces bandwidth requirements

### For 1080p instead of 720p:
- Change resolution in transmitter.py
- Requires more bandwidth (~100-150 Mbps per camera)
- May need better hardware

### For 30fps instead of 60fps:
- Change fps in transmitter.py
- Reduces bandwidth by ~40%
- Less smooth motion

## Support & Contact

For issues or questions:
1. Check this README thoroughly
2. Verify all prerequisites are installed
3. Test network connectivity between computers
4. Check NDI Tools documentation: https://ndi.tv/
5. Review python-osc documentation: https://pypi.org/project/python-osc/

## License

This system uses:
- OpenCV (Apache 2.0)
- python-osc (Public Domain)
- NDI SDK (NewTek NDI License - free for use)

Ensure compliance with NDI SDK license terms for commercial use.