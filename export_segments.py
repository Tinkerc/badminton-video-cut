#!/usr/bin/env python3
"""
Export video segments by selecting from saved sessions.

Usage:
    python export_segments.py

Lists all sessions in sessions/, lets you pick one to export.
"""

import subprocess
import sys
import os
from typing import List, Tuple


def list_sessions(session_dir: str = "sessions") -> List[Tuple[str, str, int]]:
    """List all session txt files. Returns [(basename, filepath, seg_count)]."""
    if not os.path.exists(session_dir):
        return []
    results = []
    for f in sorted(os.listdir(session_dir)):
        if f.endswith(".txt"):
            fpath = os.path.join(session_dir, f)
            count = 0
            with open(fpath, "r") as sf:
                for line in sf:
                    if line.strip():
                        count += 1
            if count > 0:
                name = f[:-4]  # remove .txt
                results.append((name, fpath, count))
    return results


def load_segments(filepath: str) -> List[Tuple[float, float]]:
    """Load segments from a txt file. Returns (segments, video_path_from_header)."""
    segments = []
    video_path = ""
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# VIDEO: "):
                video_path = line[len("# VIDEO: "):]
                continue
            if not line:
                continue
            parts = line.split()
            if len(parts) == 2:
                segments.append((float(parts[0]), float(parts[1])))
    return sorted(segments), video_path


def export(video_path: str, segments: List[Tuple[float, float]], output_path: str):
    """Export concatenated segments to output video."""
    if not segments:
        print("No segments to export.")
        return

    print(f"\nSegments: {len(segments)}")
    total = sum(e - s for s, e in segments)
    print(f"Total highlight duration: {total:.1f}s ({total/60:.1f}min)")
    print()

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

    # Concat inputs - interleaved [v0][a0][v1][a1]...
    concat_labels = "".join(
        [f"[v{i}][a{i}]" for i in range(len(segments))]
    )

    concat_filter = (
        ";".join(video_filters + audio_filters) +
        f";{concat_labels}"
        f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-filter_complex", concat_filter,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]

    subprocess.run(cmd)
    print("Export complete.")


def main():
    sessions = list_sessions()

    if not sessions:
        print("No sessions found in sessions/")
        sys.exit(1)

    print("=" * 50)
    print("Select session to export:")
    print("=" * 50)
    for i, (name, fpath, count) in enumerate(sessions):
        print(f"  {i+1}. [{count} segments] {name}")
    print("  Q - Quit")
    print()

    choice = input("Select [1]: ").strip()
    if choice.upper() == 'Q':
        sys.exit(0)

    try:
        idx = int(choice) - 1
    except ValueError:
        idx = 0

    if not (0 <= idx < len(sessions)):
        print(f"Invalid selection (1-{len(sessions)}).")
        sys.exit(1)

    name, fpath, count = sessions[idx]
    segments, video_path = load_segments(fpath)

    # Try to find video from saved path in header
    if not video_path or not os.path.exists(video_path):
        # Fallback: try common locations
        video_name = name
        for c in [
            os.path.join("./video", f"{video_name}.MOV"),
            os.path.join("./video", f"{video_name}.mov"),
            os.path.join("./video", f"{video_name}.mp4"),
            os.path.join(".", f"{video_name}.MOV"),
            os.path.join(".", f"{video_name}.mov"),
            os.path.join(".", f"{video_name}.mp4"),
        ]:
            if os.path.exists(c):
                video_path = c
                break

    # If video not found, prompt for path
    if not os.path.exists(video_path):
        print(f"Video not found at default location.")
        video_path = input(f"Enter video path for '{name}': ").strip()
        if not os.path.exists(video_path):
            print("File not found. Exiting.")
            sys.exit(1)

    # Auto-generate output path
    os.makedirs("./output", exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    existing = [f for f in os.listdir("./output") if f.startswith(base) and f.endswith(".mp4")]
    indices = []
    for f in existing:
        stem = f[len(base):]
        if stem.startswith("_") and stem.endswith(".mp4"):
            try:
                indices.append(int(stem[1:-4]))
            except ValueError:
                pass
    seq = (max(indices) + 1) if indices else 1
    output_path = f"./output/{base}_{seq}.mp4"

    print(f"\nVideo:     {video_path}")
    print(f"Session:   {name} ({count} segments)")
    print(f"Output:    {output_path}")

    confirm = input("\nExport? [Y/n]: ").strip().lower()
    if confirm == 'n':
        print("Cancelled.")
        sys.exit(0)

    export(video_path, segments, output_path)


if __name__ == "__main__":
    main()
