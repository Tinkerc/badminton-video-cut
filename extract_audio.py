#!/usr/bin/env python3
"""
Simple audio extraction from video files.

Usage:
    # Extract to WAV (default)
    python extract_audio.py video.mp4

    # Specify output path
    python extract_audio.py video.mp4 audio.wav

    # Extract to MP3
    python extract_audio.py video.mp4 audio.mp3

    # Fast copy mode (no re-encoding)
    python extract_audio.py video.mp4 --copy

    # Batch process folder
    python extract_audio.py --batch ./videos/
"""

import subprocess
import sys
from pathlib import Path


def check_audio_stream(video_path: Path) -> bool:
    """Check if video has an audio stream using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(video_path)],
            capture_output=True,
            text=True
        )
        return "audio" in result.stdout
    except FileNotFoundError:
        # ffprobe not available, assume audio exists
        return True


def extract_audio(
    video_path: str | Path,
    output_path: str | Path = None,
    audio_format: str = "wav",
    use_copy: bool = False,
    sample_rate: int = 16000,
    channels: int = 1
) -> Path:
    """
    Extract audio from video file.

    Args:
        video_path: Input video file
        output_path: Output audio file (default: video_name.wav)
        audio_format: Output format (wav/mp3/aac)
        use_copy: Copy mode (fast, no re-encoding)
        sample_rate: Sample rate for WAV (Hz)
        channels: Audio channels (1=mono, 2=stereo)

    Returns:
        Path to output file
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Check for audio stream
    if not check_audio_stream(video_path):
        raise ValueError(f"No audio stream found in {video_path}")

    # Determine output path
    if output_path is None:
        if use_copy:
            # Keep original extension for copy mode
            output_path = video_path.with_suffix(".audio")
        else:
            output_path = video_path.with_suffix(f".{audio_format}")
    else:
        output_path = Path(output_path)
        # Infer format from output file extension if not explicitly set
        if not use_copy and audio_format == "wav":
            ext = output_path.suffix.lstrip('.').lower()
            if ext in ("mp3", "aac", "wav"):
                audio_format = ext

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-sn"]  # -sn = no subtitles

    # Add -map BEFORE codec options (important!)
    cmd.extend(["-map", "0:a:0"])

    if use_copy:
        cmd.extend(["-acodec", "copy"])
    else:
        # Set codec based on format
        codecs = {"wav": "pcm_s16le", "mp3": "libmp3lame", "aac": "aac"}
        codec = codecs.get(audio_format, "pcm_s16le")
        cmd.extend(["-acodec", codec])

        if audio_format == "wav":
            cmd.extend(["-ar", str(sample_rate), "-ac", str(channels)])
        elif audio_format in ("mp3", "aac"):
            cmd.extend(["-b:a", "192k"])

    cmd.append(str(output_path))

    # Run FFmpeg
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stderr = result.stderr
        # Print last few lines of error (most useful part)
        error_lines = stderr.strip().split('\n')[-5:]
        print(f"FFmpeg error:\n" + "\n".join(error_lines), file=sys.stderr)
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")

    return output_path


def batch_extract(input_folder: str | Path, output_folder: str | Path = None, **kwargs):
    """Batch extract audio from all videos in folder."""
    input_folder = Path(input_folder)

    if output_folder is None:
        output_folder = input_folder / "audio"
    else:
        output_folder = Path(output_folder)

    output_folder.mkdir(exist_ok=True)

    patterns = [".mp4", ".webm", ".mkv", ".mov", ".avi"]
    count = 0

    for pattern in patterns:
        for video in input_folder.glob(f"*{pattern}"):
            output = output_folder / f"{video.stem}.wav"
            try:
                extract_audio(video, output, **kwargs)
                print(f"✓ {video.name} -> {output.name}")
                count += 1
            except Exception as e:
                print(f"✗ {video.name}: {e}")

    print(f"\nDone: {count} files processed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract audio from video files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input", nargs="?", help="Input video file or folder (with --batch)")
    parser.add_argument("output", nargs="?", help="Output audio file")
    parser.add_argument("--format", choices=["wav", "mp3", "aac"], default="wav",
                        help="Output format (default: wav)")
    parser.add_argument("--copy", action="store_true",
                        help="Copy mode (no re-encoding, fastest)")
    parser.add_argument("--sample-rate", type=int, default=16000,
                        help="Sample rate for WAV (default: 16000)")
    parser.add_argument("--channels", type=int, default=1, choices=[1, 2],
                        help="Audio channels: 1=mono, 2=stereo (default: 1)")
    parser.add_argument("--batch", action="store_true",
                        help="Batch mode: process all videos in folder")

    args = parser.parse_args()

    if args.batch:
        if not args.input:
            print("Error: --batch requires input folder", file=sys.stderr)
            sys.exit(1)
        batch_extract(
            args.input,
            args.output,
            audio_format=args.format,
            use_copy=args.copy,
            sample_rate=args.sample_rate,
            channels=args.channels
        )
    else:
        if not args.input:
            parser.print_help()
            sys.exit(1)
        result = extract_audio(
            args.input,
            args.output,
            audio_format=args.format,
            use_copy=args.copy,
            sample_rate=args.sample_rate,
            channels=args.channels
        )
        print(f"Extracted: {result}")
