# Mark Rallies.py - Feature List

## Analogy

Think of this like a **sports DVR with a smart highlight button**. You're watching a badminton match at 2x speed, and when you see an exciting rally start, you press Space. The system automatically backs up 1 second to catch the serve, records the rally, and when you press Space again to end it, it skips ahead 5 seconds to the next serve.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        mark_rallies.py                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌───────────────┐      ┌─────────────┐  │
│  │  VideoPlayer │ ───▶ │ Overlay UI    │ ◀─── │ Recorder    │  │
│  │              │      │ (Time/Speed)  │      │ State Mgmt  │  │
│  │ - jump()     │      └───────────────┘      └─────────────┘  │
│  │ - speed()    │              ▲                      ▲         │
│  │ - frame()    │              │                      │         │
│  └──────────────┘              │                      │         │
│         ▲                       │                      │         │
│         │              ┌────────┴────────┐            │         │
│         └──────────────│ KeyboardCtrl    │────────────┘         │
│                        │                │                       │
│                        │ Space=Toggled  │                       │
│                        │ Arrows=Jump    │                       │
│                        │ W/X=Speed      │                       │
│                        │ U=Undo         │                       │
│                        │ Q=Quit&Export  │                       │
│                        └────────────────┘                       │
│                                   │                              │
│                                   ▼                              │
│                        ┌──────────────────┐                     │
│                        │ FFmpegExporter   │                     │
│                        │ - Trim segments  │                     │
│                        │ - Concat clips   │                     │
│                        │ - Encode output  │                     │
│                        └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Feature List

| # | Feature | Description |
|---|---------|-------------|
| **1** | **Video Playback Engine** | OpenCV-based player with frame-level control |
| **2** | **Variable Playback Speed** | 0.5x to 4x speed (default 2x) |
| **3** | **Jump Navigation** | Forward/backward by 5s or 30s |
| **4** | **Toggle Recording** | Space bar starts/stops rally capture |
| **5** | **Auto-Back Start** | Automatically backs up 1s when starting recording |
| **6** | **Auto-Skip End** | Automatically jumps 5s forward when ending recording |
| **7** | **Auto-Pause Idle** | Pauses after 10s of no keypress (when not recording) |
| **8** | **Auto-Pause Backup** | Backs up 3s when auto-pausing |
| **9** | **Auto-Save** | Saves segments to file after each segment |
| **10** | **Auto-Close** | Finalizes open segment on exit |
| **11** | **Min Segment Filter** | Ignores segments under 2 seconds |
| **12** | **Undo Function** | Removes last recorded segment |
| **13** | **Real-time Overlay** | Shows time, speed, recording status, segment count |
| **14** | **Recording Indicator** | Red REC ● with elapsed time |
| **15** | **FFmpeg Export** | Single-pass concatenation of all segments |
| **16** | **Fast Encoding** | Uses veryfast preset with CRF 18 |
| **17** | **Audio Preservation** | Processes audio alongside video |
| **18** | **Optimized Output** | Adds faststart flag for web playback |
| **19** | **Session Summary** | Shows total duration and reduction % |
| **20** | **Persistent Storage** | Segments saved to `segments.txt` |

---

## Key Constants (Configurable)

```python
IDLE_SECONDS = 10          # Auto-pause after idle time
BACK_SECONDS = 3           # Backup when auto-pausing
START_BACK_SECONDS = 1.0   # Auto-back when starting rally
MIN_SEGMENT_SECONDS = 2.0  # Minimum segment to save
```

---

## Gotcha ⚠️

**Arrow key codes differ by platform!** The code uses macOS/OpenCV key codes (0-3), but on Linux these would be different. If porting, test `cv2.waitKey()` returns first.

---

## Keyboard Controls Reference

| Key | Action |
|-----|--------|
| `Space` | Toggle rally recording (start/end) |
| `→` Right Arrow | Jump forward 5 seconds |
| `←` Left Arrow | Jump backward 5 seconds |
| `↑` Up Arrow | Jump forward 30 seconds |
| `↓` Down Arrow | Jump backward 30 seconds |
| `W` | Increase playback speed |
| `X` | Decrease playback speed |
| `U` | Undo last segment |
| `Q` / `ESC` | Quit and export video |
