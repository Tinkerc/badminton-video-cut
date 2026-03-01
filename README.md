# Badminton Video Cut

A collection of tools for automatically cutting and marking badminton rally highlights from videos.

## Overview

This project provides multiple approaches to extract badminton rally segments from long videos:

| Tool | Method | Best For |
|------|--------|----------|
| `mark_rallies.py` | Manual keyboard marking | Precision, short videos |
| `auto_cut.py` | Motion + Audio detection | Automated cutting |
| `auto_cut_player.py` | Player trajectory (YOLO) | Single-player videos |
| `auto_cut_flow.py` | Optical flow detection | Motion-heavy videos |
| **`AudioExtractor`** | **Audio extraction** | **Audio analysis, format conversion** |

---

## Quick Start

### Manual Marking (Recommended for Short Videos)

```bash
python mark_rallies.py input.mp4 output.mp4
```

**Keyboard Controls:**
- `Space` - Toggle rally start/end
- `←/→` - Jump ±5 seconds
- `↑/↓` - Jump ±30 seconds
- `W/X` - Speed up/down (0.5x - 4x)
- `Q` - Quit and export

**Typical workflow:**
1. Watch at 2x speed
2. Press `Space` to start rally
3. Press `→ →` to skip dead time
4. Press `Space` to end rally
5. Press `Q` to export

**Output:** `segments.txt` and `output.mp4`

---

## Tools Reference

### mark_rallies.py

**Phase-H Efficient MVP** - Manual marking tool with keyboard control.

```bash
python mark_rallies.py input.mp4 [output.mp4]
```

- Target: Mark 45min video in 3-5 minutes
- Playback: 0.5x - 4x speed
- Jump: ±5s, ±30s
- Auto-export via FFmpeg

### auto_cut.py

**Motion + Audio Detection** - Dual-threshold automated cutting.

```bash
python auto_cut.py input.mp4 output.mp4
```

**Parameters (editable in code):**
- `SAMPLE_FPS = 2` - Frames sampled per second
- `MOTION_THRESHOLD = 8` - Motion sensitivity
- `AUDIO_THRESHOLD = 0.04` - Audio energy threshold
- `MIN_DURATION = 3` - Minimum segment length (seconds)
- `MERGE_GAP = 4` - Merge gap (seconds)

### auto_cut_player.py

**Player Trajectory Detection** - YOLO-based player tracking.

```bash
python auto_cut_player.py input.mp4 output.mp4
```

**Requirements:**
- `ultralytics` (YOLOv8)
- Downloads `yolov8s.pt` on first run

**Parameters:**
- `SAMPLE_FPS = 3` - Detection sampling rate
- `WINDOW_SECONDS = 1.5` - Sliding window size
- `THRESHOLD_RATIO = 0.4` - Adaptive threshold ratio
- `USE_VELOCITY_STD = True` - Use velocity std scoring

### auto_cut_flow.py

**Optical Flow Detection** - Motion field analysis.

```bash
python auto_cut_flow.py input.mp4 output.mp4
```

Uses Farneback optical flow to detect motion patterns.

---

## Core Modules (v2)

Phase 1 refactored the core functionality into reusable Python modules.

### AudioExtractor

Extract audio from video files with auto-detection and batch processing.

#### Features

- **Auto-detect codec**: AAC, Opus, MP3, etc.
- **Copy mode**: 10-30× faster (no re-encoding)
- **Transcode mode**: Convert to WAV/MP3/AAC
- **Batch processing**: Process entire folders

#### Installation

```bash
pip install -r requirements.txt
```

#### Quick Examples

```python
from core import AudioExtractor

# Initialize
extractor = AudioExtractor()

# Extract audio (auto-detect, copy mode - fastest)
audio_path = extractor.extract_audio("video.mp4", use_copy=True)

# Extract audio (transcode to WAV)
audio_path = extractor.extract_audio("video.mp4", "audio.wav", audio_format="wav")

# Detect audio stream info
info = extractor.detect_audio_stream("video.mp4")
print(f"Codec: {info.codec_name}, {info.sample_rate}Hz, {info.channels}ch")
```

#### Python API Reference

##### Initialize

```python
from core import AudioExtractor

# Default (uses system ffmpeg)
extractor = AudioExtractor()

# Custom FFmpeg paths
extractor = AudioExtractor(
    ffmpeg_path="/usr/bin/ffmpeg",
    ffprobe_path="/usr/bin/ffprobe"
)
```

##### Extract Audio (Copy Mode - Fastest)

```python
# Auto-detect codec and copy stream (no re-encoding)
audio_path = extractor.extract_audio(
    video_path="video.mp4",
    use_copy=True
)
# Output: video.wav (or original codec extension)
```

**When to use:** When you just need the audio for analysis or playback. Fastest option.

##### Extract Audio (Transcode Mode)

```python
# Transcode to WAV (for analysis)
audio_path = extractor.extract_audio(
    video_path="video.mp4",
    output_path="audio.wav",
    audio_format="wav",
    sample_rate=16000,  # Hz
    channels=1          # Mono
)

# Transcode to MP3 (for distribution)
audio_path = extractor.extract_audio(
    video_path="video.mp4",
    output_path="audio.mp3",
    audio_format="mp3",
    audio_bitrate="192k"
)

# Transcode to AAC
audio_path = extractor.extract_audio(
    video_path="video.mp4",
    output_path="audio.aac",
    audio_format="aac",
    audio_bitrate="192k"
)
```

**When to use:** When you need a specific format or compatibility.

##### Detect Audio Stream

```python
info = extractor.detect_audio_stream("video.mp4")

if info:
    print(f"Codec: {info.codec_name}")
    print(f"Sample rate: {info.sample_rate} Hz")
    print(f"Channels: {info.channels}")
    print(f"Bitrate: {info.bit_rate // 1000} kbps" if info.bit_rate else "")
    print(f"Duration: {info.duration:.1f}s" if info.duration else "")
else:
    print("No audio stream found")
```

##### Batch Extract

```python
from pathlib import Path

# Extract all videos in folder
output_files = extractor.batch_extract(
    input_folder=Path("./videos/"),
    output_folder=Path("./audio/"),
    use_copy=True  # Fast copy mode
)

print(f"Extracted {len(output_files)} files:")
for f in output_files:
    print(f"  - {f}")
```

##### Extract for Analysis

```python
# Optimized for audio analysis (auto-selects best mode)
audio_path, is_copy = extractor.extract_for_analysis(
    video_path=Path("video.mp4"),
    temp_dir=Path("./temp/")
)

print(f"Audio: {audio_path}")
print(f"Used copy mode: {is_copy}")
```

#### Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_path` | Path | Required | Input video file |
| `output_path` | Path | Auto | Output audio file (auto-generated if None) |
| `audio_format` | str | "wav" | Target format: "wav", "mp3", "aac" |
| `use_copy` | bool | False | Copy stream without re-encoding (fastest) |
| `sample_rate` | int | 16000 | Sample rate for WAV (Hz) |
| `channels` | int | 1 | Audio channels (1=mono, 2=stereo) |
| `audio_bitrate` | str | "192k" | Bitrate for MP3/AAC |

#### Format Selection Guide

| Format | Codec | Best For | Size |
|--------|-------|----------|------|
| **WAV** | pcm_s16le | Audio analysis, editing | Large |
| **MP3** | libmp3lame | Distribution, playback | Small |
| **AAC** | aac | Distribution, Apple devices | Small |
| **Copy** | Original | Fastest extraction | Original |

#### Error Handling

```python
from core import AudioExtractor, AudioExtractionError

extractor = AudioExtractor()

try:
    extractor.extract_audio("video.mp4", use_copy=True)
except FileNotFoundError:
    print("Video file not found")
except AudioExtractionError as e:
    print(f"Extraction failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

#### Complete Example: Rally Audio Analysis

```python
from core import AudioExtractor
import librosa
import numpy as np

# Extract audio for analysis
extractor = AudioExtractor()
audio_path, is_copy = extractor.extract_for_analysis("match.mp4")

# Load and analyze
y, sr = librosa.load(str(audio_path), sr=16000)

# Calculate RMS energy
energy = librosa.feature.rms(y=y)[0]

# Find high-energy segments (potential rallies)
threshold = np.mean(energy) + 2 * np.std(energy)
rally_indices = np.where(energy > threshold)[0]

print(f"Found {len(rally_indices)} high-energy samples")
print(f"Audio duration: {len(y) / sr:.1f}s")
```

---

### MotionAudioDetector

Detect rallies using motion and audio cues.

```python
from core import MotionAudioDetector
from config import Config

# Load configuration
config = Config.load()
detector = MotionAudioDetector(config)

# Detect rallies
segments = detector.detect("video.mp4")
print(f"Found {len(segments)} segments: {segments}")

# With progress callback
def progress(percent, message):
    print(f"{percent}%: {message}")

segments = detector.detect("video.mp4", progress_callback=progress)
```

See `docs/plan/phase1-summary.md` for full API reference.

---

### OpticalFlowDetector

Detect rallies using optical flow analysis.

```python
from core import OpticalFlowDetector
from config import Config

config = Config.load()
detector = OpticalFlowDetector(config)

segments = detector.detect("video.mp4")
print(f"Found {len(segments)} segments")
```

---

### VideoExporter

High-performance video export with frame-level precision.

```python
from core import VideoExporter
from config import Config

config = Config.load()
exporter = VideoExporter(config)

# Export segments
segments = [(10.5, 42.0), (48.3, 75.8)]
exporter.cut("video.mp4", segments, "output.mp4")

# With statistics
stats = exporter.export_with_segments(
    "video.mp4",
    segments,
    "output.mp4",
    segments_file="segments.txt"
)
print(f"Compression: {stats['compression_ratio']*100:.1f}%")
```

---

## Configuration

### Using Config Files

Create `config.yaml` in your project root:

```yaml
# config.yaml

# Motion detection settings
motion:
  sample_fps: 2
  threshold: 8
  audio_threshold: 0.04
  min_duration: 3
  merge_gap: 4

# Optical flow settings
optical_flow:
  sample_fps: 3
  threshold: 2.0
  min_duration: 4
  center_crop: true

# Export settings
export:
  codec: "libx264"
  preset: "veryfast"
  crf: 18
  audio_bitrate: "192k"
```

Load in Python:

```python
from config import Config

config = Config.load("config.yaml")
detector = MotionAudioDetector(config)
```

### Configuration Priority

1. Explicit config file (`Config.load("my_config.yaml")`)
2. Project config (`./config.yaml`)
3. User config (`~/.badminton-cut/config.yaml`)
4. Default config

### Environment Variable Overrides

```bash
export BADMINTON_CUT_MOTION_THRESHOLD=10
export BADMINTON_CUT_EXPORT_CRF=20
```

---

## Dependencies

### Python Packages

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
opencv-python>=4.5.0    # Video processing
numpy>=1.20.0           # Numerical operations
librosa>=0.9.0          # Audio analysis
PyYAML>=6.0             # Configuration
# ultralytics>=8.0.0    # YOLO (optional, for player detection)
```

### System Requirements

- **FFmpeg** (required for all video operations)

```bash
# macOS
brew install ffmpeg

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

Verify installation:

```bash
ffmpeg -version
ffprobe -version
```

---

## Output Format

All tools generate:
1. **segments.txt** - Timestamp pairs (start end)
2. **output.mp4** - Concatenated highlight clips

Example `segments.txt`:
```
12.3 42.8
55.1 73.0
80.1 103.7
```

---

## Development Plans

See `docs/plan/` for implementation phases:

- ✅ **Phase 1**: Core module refactoring (audio_extractor, motion_detector, flow_detector, video_exporter)
- 🔄 **Phase 2**: Unified CLI, batch processor
- 📋 **Phase 3-4**: Advanced features, GPU acceleration

---

## License

MIT
