# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Badminton Video Cut is a collection of tools for automatically extracting badminton rally highlights from long videos. The project provides multiple detection approaches:

- **Manual marking** (`mark_rallies.py`) - Keyboard-controlled video player for precision
- **Motion + Audio** (`auto_cut.py`) - Dual-threshold automated detection
- **Optical Flow** (`auto_cut_flow.py`) - Motion field analysis
- **Player Detection** (`auto_cut_player.py`) - YOLO-based trajectory tracking

A modular v2 architecture (`core/`, `config/`, `utils/`) is being developed to consolidate functionality.

## Common Development Commands

### Running Detection Tools

```bash
# Manual marking (keyboard-controlled)
python mark_rallies.py input.mp4 output.mp4

# Motion + Audio detection
python auto_cut.py input.mp4 output.mp4

# Optical flow detection
python auto_cut_flow.py input.mp4 output.mp4

# Player detection (requires ultralytics)
python auto_cut_player.py input.mp4 output.mp4
```

### Using the Modular v2 API

```python
from core.motion_detector import MotionAudioDetector
from core.flow_detector import OpticalFlowDetector
from core.video_exporter import VideoExporter
from config.config_loader import Config

# Load configuration
config = Config.load()  # Loads default_config.yaml

# Detect segments
detector = MotionAudioDetector(config)
segments = detector.detect("video.mp4")

# Export video
exporter = VideoExporter(config)
exporter.cut("video.mp4", segments, "highlights.mp4")
```

### Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Optional: YOLO player detection
pip install ultralytics

# System requirements
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Linux
```

### Configuration

Configuration priority (highest to lowest):
1. Explicit path: `Config.load("custom.yaml")`
2. Project config: `./config.yaml`
3. User config: `~/.badminton-cut/config.yaml`
4. Default config: `config/default_config.yaml`

Environment variables override: `BADMINTON_CUT_<SECTION>_<KEY>=value`

Example: `BADMINTON_CUT_MOTION_THRESHOLD=10`

## Architecture

### Legacy Scripts (Root Level)

- `mark_rallies.py` - OpenCV-based player with keyboard controls (R, D/A, F/S, W/X, Q)
- `auto_cut.py` - Motion + Audio dual-threshold detection (refactored into `core/motion_detector.py`)
- `auto_cut_flow.py` - Farneback optical flow (refactored into `core/flow_detector.py`)
- `auto_cut_player.py` - YOLOv8 player trajectory detection
- `detect_keys.py` - Keyframe detection utility

### Modular v2 Architecture

```
core/
├── audio_extractor.py    # FFmpeg-based audio extraction
├── motion_detector.py    # Motion + Audio detection (refactored auto_cut.py)
├── flow_detector.py      # Optical flow detection (refactored auto_cut_flow.py)
└── video_exporter.py     # FFmpeg filter_complex export engine

config/
├── config_loader.py      # YAML config with dataclasses
└── default_config.yaml   # Default parameters

utils/
└── (utilities module)
```

### Detection Pipeline

All detectors follow the same interface:

1. **Input**: Video file path
2. **Processing**: Sample frames → Extract features → Apply thresholds → Build segments → Merge gaps
3. **Output**: List of `(start, end)` tuples in seconds

### Feature Data Flow

```
video.mp4
    ↓
[motion_detector] → frame differencing + librosa audio
[flow_detector]   → Farneback optical flow
[player_detector] → YOLO person tracking
    ↓
segments = [(start, end), ...]
    ↓
[video_exporter] → FFmpeg filter_complex concat
    ↓
highlights.mp4
```

### Configuration Structure

Key configuration sections:

- `motion.sample_fps` - Frame sampling rate (default: 2)
- `motion.threshold` - Motion intensity threshold (default: 8.0)
- `motion.audio_threshold` - Audio energy threshold (default: 0.04)
- `motion.min_duration` - Minimum segment length in seconds (default: 3.0)
- `motion.merge_gap` - Merge segments closer than this (default: 4.0)
- `export.crf` - Quality (0-51, lower is better, 18-23 recommended)
- `export.preset` - Encoding speed (ultrafast to veryslow)

### Segments Format

`segments.txt` format (one segment per line):
```
12.3 42.8
55.1 73.0
80.1 103.7
```

Load/save utilities:
- `VideoExporter.load_segments(path)` - Load from file
- `VideoExporter._save_segments(path, segments)` - Save to file

## Key Implementation Details

### Motion Detection Algorithm

1. Sample frames at `sample_fps` (default: 2 fps)
2. Calculate frame difference: `cv2.absdiff(prev_gray, gray).mean()`
3. Extract audio with librosa: `librosa.feature.rms()`
4. Dual-threshold: BOTH motion AND audio must exceed thresholds
5. Apply `min_duration` filter and `merge_gap` smoothing

### Video Export

Uses FFmpeg `filter_complex` for single-pass processing:
```
[0:v]trim=start=X:end=Y,setpts=PTS-STARTPTS[v0] → per-segment trim
[0:a]atrim=start=X:end=Y,asetpts=PTS-STARTPTS[a0] → per-segment audio trim
[v0][v1]...[a0][a1]...concat=n=2:v=1:a=1[outv][outa] → concat
```

Alternative: `cut_with_copy()` for stream copy mode (faster, no re-encoding).

### Manual Marker Controls

- `R` - Toggle rally start/end
- `D/A` - Jump ±5 seconds
- `F/S` - Jump ±30 seconds
- `W/X` - Speed up/down (0.5x - 4x)
- `U` - Undo last segment
- `Q` - Quit and export

Auto-backs 1 second when starting a segment to avoid missing the first shot.
