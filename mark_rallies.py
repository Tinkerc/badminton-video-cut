#!/usr/bin/env python3
"""
Phase-H Efficient MVP - Manual Rally Marker
Keyboard-controlled video player for marking badminton rally segments.

Usage:
    python mark_rallies.py input.mp4 [output.mp4]

Keyboard Controls:
    Space      - Toggle rally recording (start/end segment)

    Right Arrow  →  - Jump forward 5 seconds
    Left Arrow   ←  - Jump backward 5 seconds

    Up Arrow     ↑  - Jump forward 30 seconds
    Down Arrow   ↓  - Jump backward 30 seconds

    W - Increase playback speed
    X - Decrease playback speed

    U - Undo last segment
    Q - Quit and export video
"""

import cv2
import subprocess
import sys
import os
import time
from typing import List, Tuple

# Auto-pause settings
IDLE_SECONDS = 10  # Seconds of no keypress before auto-pause
BACK_SECONDS = 3  # Seconds to back up when auto-paused

# Segment settings
START_BACK_SECONDS = 1.0  # Auto-back 1s when starting recording
MIN_SEGMENT_SECONDS = 2.0  # Minimum segment duration to save


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
        """Read next frame based on playback speed."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(self.current_frame))
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = int(self.current_frame + self.playback_speed)
        return ret, frame

    def release(self):
        """Release video capture."""
        self.cap.release()


class SegmentRecorder:
    """Records rally segments using toggle state."""

    def __init__(self, segments_file: str = "segments.txt"):
        self.segments: List[Tuple[float, float]] = []
        self.recording = False
        self.start_time: float = 0.0
        self.segments_file = segments_file

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

    def _auto_save(self):
        """Auto-save segments to file."""
        self.save_segments(self.segments_file)

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording

    def get_segments(self) -> List[Tuple[float, float]]:
        """Get all recorded segments (sorted)."""
        return sorted(self.segments)

    def get_count(self) -> int:
        """Get number of recorded segments."""
        return len(self.segments)

    def save_segments(self, filepath: str):
        """Save segments to file (sorted)."""
        sorted_segments = sorted(self.segments)
        with open(filepath, "w") as f:
            for start, end in sorted_segments:
                f.write(f"{start:.1f} {end:.1f}\n")


class KeyboardController:
    """Handles keyboard input for video control."""

    KEY_MAP = {
        # Space - Toggle rally recording
        32: 'toggle',

        # Arrow keys (macOS/OpenCV)
        0: 'forward_30',    # Up Arrow
        1: 'backward_30',   # Down Arrow
        2: 'backward_5',    # Left Arrow
        3: 'forward_5',     # Right Arrow

        # Speed control
        ord('w'): 'speed_up',
        ord('W'): 'speed_up',
        ord('x'): 'speed_down',
        ord('X'): 'speed_down',

        # Undo
        ord('u'): 'undo',
        ord('U'): 'undo',

        # Quit
        ord('q'): 'quit',
        ord('Q'): 'quit',
        27: 'quit',  # ESC key
    }

    @staticmethod
    def get_action(key: int) -> str:
        """Map key code to action."""
        return KeyboardController.KEY_MAP.get(key, None)


class FFmpegExporter:
    """
    Phase-H v2 High-performance exporter

    Features:
    - Zero stutter cuts
    - 2x faster export
    - Single-pass encoding
    - No temp clip files
    - Frame-level precision
    """

    @staticmethod
    def export(video_path: str, segments: List[Tuple[float, float]], output_path: str):
        """Export concatenated segments to output video."""
        if not segments:
            print("No segments to export.")
            return

        print()
        print("Building FFmpeg filter...")

        # Sort segments
        segments = sorted(segments)

        # Build trim filters
        video_filters = []
        audio_filters = []

        for i, (start, end) in enumerate(segments):
            video_filters.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )

            audio_filters.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},"
                f"asetpts=PTS-STARTPTS[a{i}]"
            )

        # Concat inputs
        v_labels = "".join([f"[v{i}]" for i in range(len(segments))])
        a_labels = "".join([f"[a{i}]" for i in range(len(segments))])

        concat_filter = (
            ";".join(video_filters + audio_filters) +
            f";{v_labels}{a_labels}"
            f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
        )

        print("Exporting video...")
        print(f"Segments: {len(segments)}")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-filter_complex", concat_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            # Fast high-quality encoding
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            # Playback optimization
            "-movflags", "+faststart",
            output_path
        ]

        subprocess.run(cmd)

        print()
        print("Export complete.")


def draw_overlay(frame, player: VideoPlayer, recorder: SegmentRecorder):
    """Draw status overlay on frame."""
    h, w = frame.shape[:2]

    # Semi-transparent background for text
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, 130), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    # Time
    current_time = player.get_current_time()
    cv2.putText(frame, f"Time: {current_time:.1f}s / {player.duration:.1f}s",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Speed
    cv2.putText(frame, f"Speed: {player.playback_speed:.1f}x",
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Recording status
    if recorder.is_recording():
        cv2.putText(frame, "REC ●",
                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        elapsed = current_time - recorder.start_time
        cv2.putText(frame, f"  +{elapsed:.1f}s",
                    (110, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Segment count
    cv2.putText(frame, f"Segments: {recorder.get_count()}",
                (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

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
    print("  Q - Quit and export video")
    print()
    print("Typical workflow:")
    print("  1. Watch video at 2x speed")
    print("  2. Press Space to start rally (auto-back 1s)")
    print("  3. Press →→ to skip dead time")
    print("  4. Press Space to end rally (auto +5s)")
    print("  5. Press Q to export")
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
    print("=" * 60)
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python mark_rallies.py input.mp4 [output.mp4]")
        sys.exit(1)

    video_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = f"{base_name}_highlight.mp4"

    print_help()
    print(f"Input:  {video_path}")
    print(f"Output: {output_path}")
    print()

    # Initialize components
    player = VideoPlayer(video_path)
    segments_file = "segments.txt"
    recorder = SegmentRecorder(segments_file)

    print(f"Video loaded: {player.width}x{player.height} @ {player.fps:.1f}fps")
    print(f"Duration: {player.duration:.1f} seconds")
    print()

    # Create window FIRST (before waitKey)
    window_name = "Phase-H Rally Marker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Read and display first frame
    ret, frame = player.read_frame()
    if ret:
        frame = draw_overlay(frame, player, recorder)
        cv2.imshow(window_name, frame)

    print("Press any key in the video window to start...")
    cv2.waitKey(0)

    # Auto-pause state
    last_key_time = time.time()
    paused = False
    pause_message = ""

    # Main playback loop
    while True:
        ret, frame = player.read_frame()

        if not ret:
            # End of video, loop back or wait
            player.current_frame = 0
            continue

        # Draw overlay
        frame = draw_overlay(frame, player, recorder)

        # Display auto-pause message if paused
        if paused:
            cv2.putText(frame, "AUTO PAUSE - Press any key",
                        (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        # Display frame
        cv2.imshow(window_name, frame)

        # Handle paused state
        if paused:
            key = cv2.waitKey(0) & 0xFF
            paused = False
            last_key_time = time.time()
            continue

        # Calculate delay based on playback speed
        delay = int(1000 / player.fps / player.playback_speed)
        delay = max(1, delay)

        key = cv2.waitKey(delay) & 0xFF

        # Auto-pause detection (only when NOT recording)
        if not recorder.is_recording():
            idle_time = time.time() - last_key_time
            if idle_time > IDLE_SECONDS:
                print(f"[{player.get_current_time():.1f}s] AUTO PAUSE (idle {idle_time:.1f}s)")
                player.jump_seconds(-BACK_SECONDS)
                print(f"[{player.get_current_time():.1f}s] Auto back {BACK_SECONDS}s")
                paused = True
                last_key_time = time.time()
                continue

        if key == 255:  # No key pressed
            continue

        # Update last key press time on any key press
        last_key_time = time.time()

        action = KeyboardController.get_action(key)

        if action == 'toggle':
            is_start = not recorder.is_recording()
            recorder.toggle(player.get_current_time(), player)
            status = "START" if recorder.is_recording() else "END"
            if is_start:
                print(f"[{player.get_current_time():.1f}s] Rally {status}")

            # Auto-jump 5s forward when ending a rally
            if not is_start:
                player.jump_seconds(5)
                print(f"[{player.get_current_time():.1f}s] Auto +5s")

        elif action == 'undo':
            removed = recorder.undo_last()
            if removed:
                print(f"UNDO: ({removed[0]:.1f}s, {removed[1]:.1f}s)")
                recorder._auto_save()
            else:
                print("UNDO: No segments to undo")

        elif action == 'forward_5':
            player.jump_seconds(5)
            print(f"[{player.get_current_time():.1f}s] +5s")

        elif action == 'backward_5':
            player.jump_seconds(-5)
            print(f"[{player.get_current_time():.1f}s] -5s")

        elif action == 'forward_30':
            player.jump_seconds(30)
            print(f"[{player.get_current_time():.1f}s] +30s")

        elif action == 'backward_30':
            player.jump_seconds(-30)
            print(f"[{player.get_current_time():.1f}s] -30s")

        elif action == 'speed_up':
            player.set_speed(player.playback_speed * 1.5)
            print(f"Speed: {player.playback_speed:.1f}x")

        elif action == 'speed_down':
            player.set_speed(player.playback_speed / 1.5)
            print(f"Speed: {player.playback_speed:.1f}x")

        elif action == 'quit':
            print()
            print("=" * 60)
            print("Exiting...")
            # Finalize - auto-close any open recording
            recorder.finalize(player.get_current_time())
            break

    # Cleanup
    player.release()
    cv2.destroyAllWindows()

    # Save segments (already auto-saved, just showing summary)
    segments = recorder.get_segments()

    print(f"Recorded {len(segments)} segments:")
    total_duration = 0
    for i, (s, e) in enumerate(segments):
        duration = e - s
        total_duration += duration
        print(f"  {i+1}. {s:.1f}s -> {e:.1f}s  ({duration:.1f}s)")

    print()
    print(f"Total highlight duration: {total_duration:.1f}s")
    print(f"Original duration: {player.duration:.1f}s")
    print(f"Reduction: {(1 - total_duration/player.duration)*100:.1f}%")
    print()

    if segments:
        print(f"Segments already auto-saved to: {recorder.segments_file}")

        # Export video
        print(f"Exporting to: {output_path}")
        FFmpegExporter.export(video_path, segments, output_path)
        print("Export complete!")
    else:
        print("No segments recorded, skipping export.")


if __name__ == "__main__":
    main()
