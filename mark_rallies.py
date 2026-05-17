#!/usr/bin/env python3
"""
Phase-H Efficient MVP - Manual Rally Marker
Keyboard-controlled video player for marking badminton rally segments.

Usage:
    python mark_rallies.py input.mp4 [output.mp4]

Keyboard Controls:
    Mode 1: BROWSE (default)
    Space      - Toggle rally recording (start/end segment)

    Right Arrow  →  - Jump forward 5 seconds
    Left Arrow   ←  - Jump backward 5 seconds

    Up Arrow     ↑  - Jump forward 30 seconds
    Down Arrow   ↓  - Jump backward 30 seconds

    W - Increase playback speed
    X - Decrease playback speed

    U - Undo last segment (or cancel recording)

    R - Enter segment list mode

    F - Jump back to last segment end time (FIX mode)

    P - Pause / Play toggle

    Q - Quit (no export)

    Mode 2: SEGMENT LIST
    Up Arrow   ↑  - Select previous segment
    Down Arrow ↓  - Select next segment
    Space      - Preview selected segment
    U          - Delete selected segment
    R          - Back to BROWSE mode

    Mode 3: PREVIEW
    Space      - Stop preview, back to list
    ← / →      - Adjust segment start -0.5s / +0.5s
    ↑ / ↓      - Adjust segment end -0.5s / +0.5s
"""

import cv2
import sys
import os
import subprocess
import time
from typing import List, Tuple

# Auto-pause settings
IDLE_SECONDS = 10  # Seconds of no keypress before auto-pause
BACK_SECONDS = 3  # Seconds to back up when auto-paused

# Segment settings
START_BACK_SECONDS = 1.0  # Auto-back 1s when starting recording
MIN_SEGMENT_SECONDS = 2.0  # Minimum segment duration to save


def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}h {m}m {s:02d}s"
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s:02d}s"
    return f"{seconds:.1f}s"


def _build_export_cmd(video_path: str, segments: List[Tuple[float, float]],
                      output_path: str, crf: int = 18, preset: str = "veryfast") -> list:
    """Build FFmpeg filter_complex command for segment export."""
    video_filters = []
    audio_filters = []
    for i, (start, end) in enumerate(segments):
        video_filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
        audio_filters.append(
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_labels = "".join([f"[v{i}][a{i}]" for i in range(len(segments))])
    filter_complex = (
        ";".join(video_filters + audio_filters) +
        f";{concat_labels}concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )
    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]


def _export_segments(video_path: str, segments: List[Tuple[float, float]],
                     output_path: str, crf: int = 18, preset: str = "veryfast") -> bool:
    """Export segments to video file using FFmpeg filter_complex.
    Returns True on success, False on failure."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    print(f"\nExporting {len(segments)} segments...")
    cmd = _build_export_cmd(video_path, segments, output_path, crf, preset)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nExport failed (exit code {result.returncode})")
        stderr_preview = result.stderr[-500:] if result.stderr else "(no stderr)"
        print(f"FFmpeg error: {stderr_preview}")
        print("Session file preserved. Retry with: python export_segments.py")
        return False
    if not os.path.exists(output_path):
        print("\nExport failed: output file not created.")
        print("Session file preserved. Retry with: python export_segments.py")
        return False
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nExport complete: {output_path} ({size_mb:.1f} MB)")
    return True


def _apply_padding(segments: List[Tuple[float, float]],
                   start_pad: float = 0.0, end_pad: float = 0.0) -> List[Tuple[float, float]]:
    """Apply start/end padding and merge overlapping segments."""
    if not segments:
        return []
    padded = sorted([(max(0, s - start_pad), e + end_pad) for s, e in segments])
    merged = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


class VideoPlayer:
    """OpenCV-based video player with playback control."""

    def __init__(self, video_path: str):
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.duration = self.total_frames / self.fps
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.playback_speed = 2.0
        self.current_frame = 0

    def get_current_time(self) -> float:
        """Get current playback time in seconds."""
        return self.current_frame / self.fps

    def jump_seconds(self, seconds: float):
        """Jump forward or backward by specified seconds."""
        new_frame = int(self.current_frame + seconds * self.fps)
        self.current_frame = max(0, min(new_frame, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)

    def set_speed(self, speed: float):
        """Set playback speed."""
        self.playback_speed = max(0.5, min(speed, 4.0))

    def read_frame(self):
        """Read next frame."""
        ret, frame = self.cap.read()
        if ret:
            self.current_frame += 1
        return ret, frame

    def release(self):
        """Release video capture."""
        self.cap.release()


class SegmentRecorder:
    """Records rally segments using toggle state."""

    def __init__(self, video_path: str = "", session_dir: str = "sessions"):
        self.segments: List[Tuple[float, float]] = []
        self.recording = False
        self.start_time: float = 0.0
        self.video_path = video_path
        self.session_dir = session_dir
        self.last_end_time: float = 0.0  # For F fix mode
        os.makedirs(session_dir, exist_ok=True)

    def _segments_file(self) -> str:
        """Get per-video segments file path."""
        base = os.path.splitext(os.path.basename(self.video_path))[0]
        return os.path.join(self.session_dir, f"{base}.txt")

    def toggle(self, current_time: float, player):
        """Toggle recording state."""
        if not self.recording:
            # Start recording with auto-back 1s
            self.recording = True
            self.start_time = max(current_time - START_BACK_SECONDS, 0)
            print(f"[{current_time:.1f}s] Auto-back {START_BACK_SECONDS}s to [{self.start_time:.1f}s]")
        else:
            # End recording and save segment
            self.recording = False
            duration = current_time - self.start_time
            if duration >= MIN_SEGMENT_SECONDS:
                self.segments.append((self.start_time, current_time))
                print(f"[{current_time:.1f}s] Saved segment ({duration:.1f}s)")
                self._auto_save()  # Auto-save after each segment
            else:
                print(f"[{current_time:.1f}s] IGNORED short segment ({duration:.1f}s < {MIN_SEGMENT_SECONDS}s)")

    def finalize(self, current_time: float):
        """Finalize recording - auto-close if still recording."""
        if self.recording:
            duration = current_time - self.start_time
            if duration >= MIN_SEGMENT_SECONDS:
                self.segments.append((self.start_time, current_time))
                print(f"[{current_time:.1f}s] AUTO CLOSED last segment ({duration:.1f}s)")
            else:
                print(f"[{current_time:.1f}s] IGNORED short segment ({duration:.1f}s < {MIN_SEGMENT_SECONDS}s)")
            self.recording = False

    def undo_last(self):
        """Remove last segment."""
        if self.segments:
            removed = self.segments.pop()
            return removed
        return None

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording

    def cancel_recording(self):
        """Cancel current in-progress recording without saving segment."""
        self.recording = False

    def load_segments(self):
        """Load segments from per-video txt file."""
        fpath = self._segments_file()
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) == 2:
                        self.segments.append((float(parts[0]), float(parts[1])))
            print(f"Loaded {len(self.segments)} segments from {fpath}")

    def _auto_save(self):
        """Auto-save segments to txt file with video path header."""
        fpath = self._segments_file()
        with open(fpath, "w") as f:
            f.write(f"# VIDEO: {os.path.abspath(self.video_path)}\n")
            for s, e in sorted(self.segments):
                f.write(f"{s:.1f} {e:.1f}\n")

    def save_segments(self, filepath: str):
        """Save segments (filepath ignored, uses per-video file)."""
        self._auto_save()

    def delete_at_index(self, index: int):
        """Delete segment at sorted index."""
        sorted_segs = sorted(self.segments)
        if 0 <= index < len(sorted_segs):
            removed = sorted_segs[index]
            self.segments.remove(removed)
            return removed
        return None

    def update_at_index(self, index: int, new_segment: Tuple[float, float]):
        """Update segment at sorted index in-place."""
        sorted_segs = sorted(self.segments)
        if 0 <= index < len(sorted_segs):
            sorted_segs[index] = new_segment
            self.segments = sorted_segs
            return True
        return False

    def get_at_index(self, index: int):
        """Get segment at sorted index."""
        sorted_segs = sorted(self.segments)
        if 0 <= index < len(sorted_segs):
            return sorted_segs[index]
        return None

    def get_segments(self) -> List[Tuple[float, float]]:
        """Get all recorded segments (sorted)."""
        return sorted(self.segments)

    def get_count(self) -> int:
        """Get number of recorded segments."""
        return len(self.segments)


class KeyboardController:
    """Handles keyboard input for video control."""

    KEY_MAP = {
        # Space - Toggle rally recording
        32: 'toggle',

        # Arrow keys (macOS/OpenCV)
        0: 'up',        # Up Arrow
        1: 'down',      # Down Arrow
        2: 'left',      # Left Arrow
        3: 'right',     # Right Arrow

        # Speed control
        ord('w'): 'speed_up',
        ord('W'): 'speed_up',
        ord('x'): 'speed_down',
        ord('X'): 'speed_down',

        # Undo / Delete
        ord('u'): 'undo',
        ord('U'): 'undo',

        # Fix mode (back to last segment end)
        ord('f'): 'fix',
        ord('F'): 'fix',

        # Preview / List mode
        ord('r'): 'toggle_list',
        ord('R'): 'toggle_list',

        # Pause / Play toggle
        ord('p'): 'pause',
        ord('P'): 'pause',

        # Quit
        ord('q'): 'quit',
        ord('Q'): 'quit',
        27: 'quit',  # ESC key

        # Review navigation
        13: 'confirm',           # Enter — next segment
        8: 'back',               # Backspace (macOS)
        127: 'back',             # Backspace (alternate)

        # Export / Save from list mode
        ord('e'): 'export',
        ord('E'): 'export',
        ord('s'): 'save',
        ord('S'): 'save',
    }

    @staticmethod
    def get_action(key: int) -> str:
        """Map key code to action."""
        return KeyboardController.KEY_MAP.get(key, None)


def draw_overlay(frame, player: VideoPlayer, recorder: SegmentRecorder,
                 mode: str = "BROWSE", selected_index: int = -1, preview_seg: tuple = None):
    """Draw status overlay on frame."""
    h, w = frame.shape[:2]

    # Mode-specific overlay height
    if mode == "LIST":
        overlay_bottom = min(350, h - 10)
    else:
        overlay_bottom = 130

    # Semi-transparent background for text
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, overlay_bottom), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    # Time
    current_time = player.get_current_time()
    cv2.putText(frame, f"Time: {current_time:.1f}s / {player.duration:.1f}s",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Speed
    cv2.putText(frame, f"Speed: {player.playback_speed:.1f}x",
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Mode indicator
    if mode == "PREVIEW":
        cv2.putText(frame, f"PREVIEW: +/- adjust start | +/- adjust end | Space=done | P=pause",
                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    elif mode == "LIST":
        cv2.putText(frame, "LIST: Enter/Up/Down | Space=preview | E=export | S=save | U=delete",
                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    else:
        # Segment count (browse mode)
        cv2.putText(frame, f"Segments: {recorder.get_count()}",
                    (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    # List mode: draw segment list
    if mode == "LIST":
        segments = recorder.get_segments()
        y_start = 150
        line_h = 18
        color = (0, 255, 255)
        cv2.putText(frame, f"  [{selected_index + 1}/{len(segments)}] (Space=Preview, U=Delete, R=Browse)",
                    (15, y_start - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 1)
        # Show up to 12 segments centered on selection
        visible = 12
        half = visible // 2
        start_idx = max(0, min(selected_index - half, len(segments) - visible))
        end_idx = min(start_idx + visible, len(segments))
        for i in range(start_idx, end_idx):
            s, e = segments[i]
            color = (0, 255, 0) if i == selected_index else (200, 200, 200)
            prefix = ">> " if i == selected_index else "   "
            text = f"  {prefix}{i+1}. {s:.1f}s - {e:.1f}s  ({e-s:.1f}s)"
            cv2.putText(frame, text, (15, y_start + (i - start_idx) * line_h),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # Preview mode: show current segment info
    if mode == "PREVIEW" and preview_seg:
        s, e = preview_seg
        cv2.putText(frame, f"PREVIEW: {s:.1f}s - {e:.1f}s  ({e-s:.1f}s)",
                    (20, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"  [{selected_index + 1}/{recorder.get_count()}]",
                    (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, "  Space=Back, Left/Right=Start-0.5/+0.5, Up/Down=End-0.5/+0.5",
                    (20, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        # Progress bar
        progress = (current_time - s) / (e - s) if e > s else 0
        bar_w = 300
        cv2.rectangle(frame, (20, 225), (20 + bar_w, 232), (100, 100, 100), -1)
        cv2.rectangle(frame, (20, 225), (20 + int(bar_w * progress), 232), (0, 255, 0), -1)

    return frame


def print_help():
    """Print keyboard controls help."""
    print("=" * 60)
    print("Phase-H Efficient MVP - Manual Rally Marker")
    print("=" * 60)
    print()
    print("Keyboard Controls:")
    print("  Space      - Toggle rally recording (start/end)")
    print()
    print("  Right Arrow  →  - Jump forward 5 seconds")
    print("  Left Arrow   ←  - Jump backward 5 seconds")
    print()
    print("  Up Arrow     ↑  - Jump forward 30 seconds")
    print("  Down Arrow   ↓  - Jump backward 30 seconds")
    print()
    print("  W - Increase playback speed (0.5x - 4x)")
    print("  X - Decrease playback speed")
    print("  U - Undo last segment")
    print("  Q - Quit")
    print()
    print("Typical workflow:")
    print("  1. Watch video at 2x speed")
    print("  2. Press Space to start rally (auto-back 1s)")
    print("  3. Press →→ to skip dead time")
    print("  4. Press Space to end rally (auto +5s)")
    print("  5. Use export_segments.py to export")
    print()
    print("Features:")
    print(f"  Auto-start: Back {START_BACK_SECONDS}s when pressing Space")
    print(f"  Auto-end: Skip +5s after ending rally")
    print(f"  Auto-pause: After {IDLE_SECONDS}s idle (not recording)")
    print(f"  Auto-close: Finalize open segment on exit")
    print(f"  Auto-save: Saved after each segment")
    print(f"  Min segment: {MIN_SEGMENT_SECONDS}s (shorter ignored)")
    print(f"  Undo: Press U to remove last segment")
    print()
    print("  Review mode (LIST):")
    print("    Enter     - Next segment")
    print("    Backspace - Previous segment")
    print("    E         - Export")
    print("    S         - Save")
    print()
    print("=" * 60)
    print()


def _load_session_segments(fpath: str) -> Tuple[List[Tuple[float, float]], str]:
    """Load segments and video path from session file."""
    segments = []
    video_path = ""
    with open(fpath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# VIDEO:"):
                video_path = line[len("# VIDEO:"):].strip()
                continue
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) == 2:
                segments.append((float(parts[0]), float(parts[1])))
    return sorted(segments), video_path


def _parse_session_info(fpath: str) -> dict:
    """Parse session file for metadata.
    Returns dict: name, fpath, seg_count, highlight_duration, video_path, video_exists."""
    name = os.path.splitext(os.path.basename(fpath))[0]
    segments, video_path = _load_session_segments(fpath)
    highlight = sum(e - s for s, e in segments)
    return {
        "name": name,
        "fpath": fpath,
        "seg_count": len(segments),
        "highlight_duration": highlight,
        "video_path": video_path,
        "video_exists": bool(video_path) and os.path.exists(video_path),
    }


def _find_next_output_index(output_dir: str, base_name: str) -> int:
    """Find next available sequence number for output file."""
    os.makedirs(output_dir, exist_ok=True)
    existing = [f for f in os.listdir(output_dir) if f.startswith(base_name) and f.endswith(".mp4")]
    indices = []
    for f in existing:
        # Extract _N.mp4 suffix
        stem = f[len(base_name):]
        if stem.startswith("_") and stem.endswith(".mp4"):
            num_part = stem[1:-4]  # remove _ and .mp4
            try:
                indices.append(int(num_part))
            except ValueError:
                pass
    return (max(indices) + 1) if indices else 1


def _list_sessions(session_dir: str = "sessions") -> List[dict]:
    """List existing sessions with metadata. Returns list of info dicts."""
    if not os.path.exists(session_dir):
        return []
    results = []
    for f in sorted(os.listdir(session_dir)):
        if f.endswith(".txt"):
            fpath = os.path.join(session_dir, f)
            info = _parse_session_info(fpath)
            if info["seg_count"] > 0:
                results.append(info)
    return results


def _export_session_standalone(sessions: list):
    """Export a session without entering the video player."""
    print("\nWhich session to export?")
    for i, s in enumerate(sessions):
        print(f"  {i+1}. [{s['seg_count']} segments] {s['name']}")
    choice = input("\nSelect [1]: ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
    except ValueError:
        idx = 0

    if not (0 <= idx < len(sessions)):
        print("Invalid selection.")
        return

    s = sessions[idx]
    if not s["video_exists"]:
        print(f"Video not found: {s.get('video_path', 'N/A')}")
        new_path = input("Enter video path: ").strip()
        if new_path and os.path.exists(new_path):
            video_path = os.path.abspath(new_path)
        else:
            print("File not found.")
            return
    else:
        video_path = s["video_path"]

    segments, _ = _load_session_segments(s["fpath"])
    if not segments:
        print("No segments to export.")
        return

    base_name = s["name"]
    output_dir = "./output"
    seq = _find_next_output_index(output_dir, base_name)
    output_path = os.path.join(output_dir, f"{base_name}_{seq}.mp4")

    print(f"\nVideo:    {video_path}")
    print(f"Segments: {len(segments)} ({_format_duration(sum(e - s for s, e in segments))})")
    print(f"Output:   {output_path}")

    confirm = input("\nExport? [Y/n] ").strip().lower()
    if confirm != 'n':
        padded = _apply_padding(segments, start_pad=0.8, end_pad=1.2)
        print(f"After padding: {len(padded)} segments ({_format_duration(sum(e - s for s, e in padded))})")
        _export_segments(video_path, padded, output_path)


def _select_session():
    """Show session list and let user pick existing or create new."""
    sessions = _list_sessions()

    print("=" * 60)
    print("Badminton Video Cut")
    print("=" * 60)

    if sessions:
        print()
        for i, s in enumerate(sessions):
            dur = _format_duration(s["highlight_duration"])
            status = "video found" if s["video_exists"] else "video missing"
            print(f"  {i+1}. [{s['seg_count']} segments] {s['name']}  highlight {dur}  {status}")

        print(f"\n  N - New video")
        print("  E - Export existing session")
        print("  Q - Quit")
        choice = input("\nSelect [1]: ").strip()

        if choice.upper() == 'Q':
            sys.exit(0)

        if choice.upper() == 'N':
            return _new_session()

        if choice.upper() == 'E':
            _export_session_standalone(sessions)
            sys.exit(0)

        try:
            idx = int(choice) - 1 if choice else 0
        except ValueError:
            idx = 0

        if 0 <= idx < len(sessions):
            s = sessions[idx]
            if s["video_exists"]:
                print(f"\nResuming: {s['name']} ({s['seg_count']} segments)")
                return s["video_path"]
            elif s["video_path"]:
                print(f"Video not found: {s['video_path']}")
                new_path = input("Enter correct video path: ").strip()
                if new_path and os.path.exists(new_path):
                    return os.path.abspath(new_path)
                print("File not found. Exiting.")
                sys.exit(1)
            else:
                print("No video path in session file.")
                new_path = input("Enter video path: ").strip()
                if new_path and os.path.exists(new_path):
                    return os.path.abspath(new_path)
                print("File not found. Exiting.")
                sys.exit(1)

        print("Invalid choice, exiting.")
        sys.exit(1)
    else:
        print("\nNo sessions found.")
        return _new_session()


def _new_session():
    """Create a new session by prompting for video path."""
    print("\nEnter video path:")
    video_path = input("  Video path: ").strip()
    if not video_path or not os.path.exists(video_path):
        print("File not found. Exiting.")
        sys.exit(1)

    return os.path.abspath(video_path)


def main():
    # Session selection
    video_path = _select_session()

    # Auto-generate output path with sequence number
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = "./output"
    seq = _find_next_output_index(output_dir, base_name)
    output_path = os.path.join(output_dir, f"{base_name}_{seq}.mp4")

    print_help()
    print(f"Input:  {video_path}")
    print(f"Output: {output_path}")
    print()

    # Initialize components
    recorder = SegmentRecorder(video_path)
    recorder.load_segments()
    player = VideoPlayer(video_path)

    print(f"Video loaded: {player.width}x{player.height} @ {player.fps:.1f}fps")
    print(f"Duration: {player.duration:.1f} seconds")
    print()

    # Mode selection menu (before creating window)
    has_segments = recorder.get_count() > 0
    print("Select mode:")
    print("  1 - BROWSE   (watch video, mark new segments)")
    print("  2 - LIST     (review/edit segment list)")
    if has_segments:
        print("  3 - PREVIEW  (preview segment #1)")
    print("  Q - Quit")
    choice = input("> ").strip().upper()
    if choice == 'Q' or choice == '':
        print("Bye.")
        sys.exit(0)

    # Mode state
    mode = "BROWSE"  # BROWSE | LIST | PREVIEW
    selected_index = 0
    preview_seg = None

    if choice == '2' and has_segments:
        mode = "LIST"
        print(f"Entering LIST mode ({recorder.get_count()} segments)")
    elif choice == '3' and has_segments:
        mode = "LIST"
        selected_index = 0
        seg = recorder.get_at_index(0)
        preview_seg = seg
        player.jump_seconds(seg[0] - 1)  # Start 1s before
        print(f"[Preview] Segment #1: {seg[0]:.1f}s - {seg[1]:.1f}s")
        mode = "PREVIEW"
    else:
        print("Entering BROWSE mode")

    # Loop state
    last_key_time = time.time()
    paused = False
    pending_key = None

    window_name = "Phase-H Rally Marker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Main loop
    while True:
        if mode == "LIST":
            # LIST mode: show selected segment's frame with overlay, read keys
            segments = recorder.get_segments()
            if segments:
                seg = recorder.get_at_index(selected_index)
                if seg:
                    target_frame = int(seg[0] * player.fps)
                    player.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    player.current_frame = target_frame
                    ret, frame = player.cap.read()
                    if ret:
                        frame = draw_overlay(frame, player, recorder, mode, selected_index, preview_seg)
                        cv2.imshow(window_name, frame)

            key = cv2.waitKey(100) & 0xFF
            if key == 255:
                continue
            last_key_time = time.time()
            action = KeyboardController.get_action(key)

            if action == 'quit':
                print("Exiting...")
                recorder.finalize(player.get_current_time())
                break

            if action == 'toggle_list':  # R = back to browse
                mode = "BROWSE"
                paused = False
                print("Back to BROWSE mode")
                continue

            if not segments:
                continue

            # Navigation
            if action in ('up', 'back'):  # Up or Backspace — previous
                selected_index = max(0, selected_index - 1)
            elif action in ('down', 'confirm'):  # Down or Enter — next
                selected_index = min(len(segments) - 1, selected_index + 1)
            elif action == 'toggle':  # Space = preview selected
                seg = recorder.get_at_index(selected_index)
                if seg:
                    preview_seg = seg
                    player.jump_seconds(seg[0] - 1)
                    print(f"[Preview] Segment #{selected_index+1}: {seg[0]:.1f}s - {seg[1]:.1f}s")
                    mode = "PREVIEW"
                else:
                    print("No segments to preview.")
            elif action == 'undo':  # U = delete selected
                removed = recorder.delete_at_index(selected_index)
                if removed:
                    print(f"DELETED: {removed[0]:.1f}s - {removed[1]:.1f}s")
                    recorder._auto_save()
                    selected_index = min(selected_index, max(0, len(recorder.get_segments()) - 1))
                else:
                    print("No segments to delete.")
            elif action == 'export':  # E = export from list mode
                recorder._auto_save()
                segs = recorder.get_segments()
                if segs:
                    total_dur = sum(e - s for s, e in segs)
                    print(f"\n{len(segs)} segments, {_format_duration(total_dur)}")
                    confirm = input("Export? [Y/n] ").strip().lower()
                    if confirm != 'n':
                        _export_segments(video_path, segs, output_path)
            elif action == 'save':  # S = explicit save
                recorder._auto_save()
                print(f"Saved {recorder.get_count()} segments")
            continue

        # BROWSE / FIX / PREVIEW: video playback
        ret, frame = player.read_frame()

        if not ret:
            if mode == "PREVIEW":
                next_idx = selected_index + 1
                if next_idx < recorder.get_count():
                    selected_index = next_idx
                    seg = recorder.get_at_index(selected_index)
                    preview_seg = seg
                    player.jump_seconds(seg[0] - 1)
                    print(f"[Preview -> #{selected_index+1}] {seg[0]:.1f}s - {seg[1]:.1f}s")
                else:
                    print("[Review complete - last segment]")
                    mode = "LIST"
                recorder._auto_save()
                continue
            # Video ended: finalize recording, pause at start
            recorder.finalize(player.get_current_time())
            print(f"[END] Video ended ({player.duration:.1f}s). Press Q to exit.")
            player.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            player.current_frame = 0
            paused = True
            continue

        # Draw overlay
        frame = draw_overlay(frame, player, recorder, mode, selected_index, preview_seg)

        # Display auto-pause message if paused
        if paused:
            cv2.putText(frame, "AUTO PAUSE - Press any key",
                        (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        cv2.imshow(window_name, frame)

        # Read key: use pending key from unpause, or wait for new key
        if pending_key is not None:
            key = pending_key
            pending_key = None
        elif paused:
            key = cv2.waitKey(0) & 0xFF
            paused = False
            last_key_time = time.time()
            if key == 255:
                continue
        else:
            delay = int(1000 / player.fps / player.playback_speed)
            delay = max(1, delay)
            key = cv2.waitKey(delay) & 0xFF

        if key == 255:
            # Auto-pause (only in BROWSE mode, not recording)
            if mode == "BROWSE" and not recorder.is_recording():
                idle_time = time.time() - last_key_time
                if idle_time > IDLE_SECONDS:
                    print(f"[{player.get_current_time():.1f}s] AUTO PAUSE (idle {idle_time:.1f}s)")
                    player.jump_seconds(-BACK_SECONDS)
                    paused = True
                    continue
            # Preview mode: check if we've passed segment end
            if mode == "PREVIEW" and preview_seg:
                if player.get_current_time() >= preview_seg[1]:
                    next_idx = selected_index + 1
                    if next_idx < recorder.get_count():
                        selected_index = next_idx
                        seg = recorder.get_at_index(selected_index)
                        preview_seg = seg
                        player.jump_seconds(seg[0] - 1)
                        print(f"[Preview -> #{selected_index+1}] {seg[0]:.1f}s - {seg[1]:.1f}s")
                    else:
                        print("[Review complete - last segment]")
                        mode = "LIST"
                    recorder._auto_save()
                    continue
            continue

        last_key_time = time.time()
        action = KeyboardController.get_action(key)

        # ===== GLOBAL ACTIONS (all modes) =====

        if action == 'pause':  # P = pause/play toggle
            paused = not paused
            continue

        if action == 'quit':
            print("Exiting...")
            recorder.finalize(player.get_current_time())
            break

        # ===== MODE-SPECIFIC KEY HANDLING =====

        if mode == "BROWSE":
            if action == 'toggle':
                is_start = not recorder.is_recording()
                recorder.toggle(player.get_current_time(), player)
                status = "START" if recorder.is_recording() else "END"
                if is_start:
                    print(f"[{player.get_current_time():.1f}s] Rally {status}")
                if not is_start and recorder.segments:
                    recorder.last_end_time = recorder.segments[-1][1]
                    player.jump_seconds(5)
                    print(f"[{player.get_current_time():.1f}s] Auto +5s")

            elif action == 'fix':
                # Go back to last segment's end time and pause
                if recorder.last_end_time > 0:
                    player.jump_seconds(recorder.last_end_time - player.get_current_time())
                    paused = True
                    print(f"[FIX] Back to {recorder.last_end_time:.1f}s (paused)")
                else:
                    print("No segment ended to fix")

            elif action == 'undo':
                if recorder.is_recording():
                    recorder.cancel_recording()
                    print(f"UNDO: Recording cancelled at {player.get_current_time():.1f}s")
                else:
                    removed = recorder.undo_last()
                    if removed:
                        print(f"UNDO: ({removed[0]:.1f}s, {removed[1]:.1f}s)")
                        recorder._auto_save()
                    else:
                        print("UNDO: No segments to undo")

            elif action == 'right':
                player.jump_seconds(5)
                print(f"[{player.get_current_time():.1f}s] +5s")
            elif action == 'left':
                player.jump_seconds(-5)
                print(f"[{player.get_current_time():.1f}s] -5s")
            elif action == 'up':
                player.jump_seconds(30)
                print(f"[{player.get_current_time():.1f}s] +30s")
            elif action == 'down':
                player.jump_seconds(-30)
                print(f"[{player.get_current_time():.1f}s] -30s")

            elif action == 'speed_up':
                player.set_speed(player.playback_speed * 1.5)
                print(f"Speed: {player.playback_speed:.1f}x")
            elif action == 'speed_down':
                player.set_speed(player.playback_speed / 1.5)
                print(f"Speed: {player.playback_speed:.1f}x")

            elif action == 'toggle_list':
                mode = "LIST"
                selected_index = 0
                print("=== SEGMENT LIST ===")
                for i, (s, e) in enumerate(recorder.get_segments()):
                    print(f"  {i+1}. {s:.1f}s - {e:.1f}s  ({e-s:.1f}s)")
                print(f"Total: {recorder.get_count()} segments")

        elif mode == "PREVIEW":
            if action == 'toggle':  # Space = back to list
                mode = "LIST"
                print("Back to LIST mode")

            elif action == 'left':  # Adjust start -0.5s
                seg = recorder.get_at_index(selected_index)
                if seg:
                    new_start = max(0, seg[0] - 0.5)
                    recorder.update_at_index(selected_index, (new_start, seg[1]))
                    recorder._auto_save()
                    player.jump_seconds(new_start - preview_seg[0])
                    preview_seg = (new_start, seg[1])
                    print(f"Start: {new_start:.1f}s")

            elif action == 'right':  # Adjust start +0.5s
                seg = recorder.get_at_index(selected_index)
                if seg:
                    new_start = seg[0] + 0.5
                    recorder.update_at_index(selected_index, (new_start, seg[1]))
                    recorder._auto_save()
                    player.jump_seconds(new_start - preview_seg[0])
                    preview_seg = (new_start, seg[1])
                    print(f"Start: {new_start:.1f}s")

            elif action == 'up':  # Adjust end -0.5s
                seg = recorder.get_at_index(selected_index)
                if seg:
                    new_end = max(seg[0] + MIN_SEGMENT_SECONDS, seg[1] - 0.5)
                    recorder.update_at_index(selected_index, (seg[0], new_end))
                    recorder._auto_save()
                    preview_seg = (seg[0], new_end)
                    print(f"End: {new_end:.1f}s")

            elif action == 'down':  # Adjust end +0.5s
                seg = recorder.get_at_index(selected_index)
                if seg:
                    new_end = seg[1] + 0.5
                    recorder.update_at_index(selected_index, (seg[0], new_end))
                    recorder._auto_save()
                    preview_seg = (seg[0], new_end)
                    print(f"End: {new_end:.1f}s")

    # Cleanup
    player.release()
    cv2.destroyAllWindows()

    segments = recorder.get_segments()
    print(f"\nRecorded {len(segments)} segments")

    if segments:
        total_duration = sum(e - s for s, e in segments)
        print(f"Total highlight duration: {_format_duration(total_duration)}")
        print(f"Original duration: {_format_duration(player.duration)}")
        if player.duration > 0:
            reduction = (1 - total_duration / player.duration) * 100
            print(f"Reduction: {reduction:.1f}%")
        print()
        print(f"Segments saved to: {recorder._segments_file()}")
        print(f"Output video: {output_path}")
        print()
        print("Export settings:")
        print(f"  Start padding: 0.8s")
        print(f"  End padding:   1.2s")
        print(f"  CRF: 18")
        print(f"  Preset: veryfast")
        print()
        confirm = input("Export now? [Y/n] ").strip().lower()
        if confirm != 'n':
            padded = _apply_padding(segments, start_pad=0.8, end_pad=1.2)
            _export_segments(video_path, padded, output_path)
    else:
        print("No segments recorded.")


if __name__ == "__main__":
    main()
