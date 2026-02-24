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

---

## Quick Start

### Manual Marking (Recommended for Short Videos)

```bash
python mark_rallies.py input.mp4 output.mp4
```

**Keyboard Controls:**
- `R` - Toggle rally start/end
- `D/A` - Jump ±5 seconds
- `F/S` - Jump ±30 seconds
- `W/X` - Speed up/down (0.5x - 4x)
- `Q` - Quit and export

**Typical workflow:**
1. Watch at 2x speed
2. Press `R` to start rally
3. Press `D D` to skip dead time
4. Press `R` to end rally
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

## Dependencies

```bash
pip install opencv-python numpy librosa ultralytics
```

**System requirements:**
- FFmpeg (for video cutting)

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
- Phase 1-4: Automated detection algorithms
- Phase H: Manual marking MVP (implemented)

---

## License

MIT