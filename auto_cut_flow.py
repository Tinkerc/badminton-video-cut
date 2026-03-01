#!/usr/bin/env python3
"""
auto_cut_flow.py - Optical Flow Detection Video Cutter

This script is now a thin wrapper around core.flow_detector.
Original functionality is preserved for backward compatibility.

Usage:
    python auto_cut_flow.py input.mp4 output.mp4

For more options, use the unified CLI:
    badminton-cut flow input.mp4 output.mp4
    badminton-cut flow --help
"""

import sys
import os
import argparse

# Import core modules
from core import OpticalFlowDetector, VideoExporter
from config import Config


# Default parameters (for backward compatibility when no config file)
DEFAULTS = {
    "sample_fps": 3,
    "threshold": 2.0,
    "min_duration": 4,
    "merge_gap": 4,
    "center_crop": True
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Optical Flow Detection Video Cutter"
    )
    
    parser.add_argument(
        "input",
        help="Input video file"
    )
    
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output video file (default: input_highlight.mp4)"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Configuration file"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=f"Flow threshold (default: {DEFAULTS['threshold']})"
    )
    
    parser.add_argument(
        "--sample-fps",
        type=int,
        default=None,
        help=f"Sample FPS (default: {DEFAULTS['sample_fps']})"
    )
    
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help=f"Minimum segment duration in seconds (default: {DEFAULTS['min_duration']})"
    )
    
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=None,
        help=f"Merge gap in seconds (default: {DEFAULTS['merge_gap']})"
    )
    
    parser.add_argument(
        "--no-center-crop",
        action="store_true",
        help="Disable center crop (analyze full frame)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't cut video"
    )
    
    parser.add_argument(
        "--export-segments",
        type=str,
        default=None,
        help="Export segments to file"
    )
    
    parser.add_argument(
        "--import-segments",
        type=str,
        default=None,
        help="Import segments from file (skip detection)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    return parser.parse_args()


def load_segments(path):
    """Load segments from file."""
    segments = []
    
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                segments.append((float(parts[0]), float(parts[1])))
    
    return sorted(segments)


def save_segments(path, segments):
    """Save segments to file."""
    with open(path, "w") as f:
        for start, end in sorted(segments):
            f.write(f"{start:.1f} {end:.1f}\n")


def print_summary(segments, duration):
    """Print detection summary."""
    print()
    print("=" * 60)
    print("Final Segments to be cut:")
    print("=" * 60)
    
    total_duration = 0
    for i, (s, e) in enumerate(segments):
        segment_duration = e - s
        total_duration += segment_duration
        print(f"Segment {i + 1:2d}: {s:7.1f}s -> {e:7.1f}s  (duration: {segment_duration:5.1f}s)")
    
    print()
    print(f"Total segments: {len(segments)}")
    print(f"Total output duration: {total_duration:.1f}s / {duration:.1f}s ({total_duration / duration * 100:.1f}%)")
    print(f"Time saved: {duration - total_duration:.1f}s ({(duration - total_duration) / duration * 100:.1f}%)")
    print("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load configuration
    config_path = None
    if args.config:
        config_path = Path(args.config)
    
    config = Config.load(config_path)
    
    # Apply command-line overrides
    if args.threshold is not None:
        config.optical_flow.threshold = args.threshold
    if args.sample_fps is not None:
        config.optical_flow.sample_fps = args.sample_fps
    if args.min_duration is not None:
        config.optical_flow.min_duration = args.min_duration
    if args.merge_gap is not None:
        config.optical_flow.merge_gap = args.merge_gap
    if args.no_center_crop:
        config.optical_flow.center_crop = False
    
    # Print parameters
    print("=" * 60)
    print("Optical Flow Video Cutter")
    print("=" * 60)
    print()
    print(f"Input video: {args.input}")
    print(f"Output file: {args.output if args.output else '(auto-generated)'}")
    print()
    print("Parameters:")
    print(f"  - SAMPLE_FPS: {config.optical_flow.sample_fps}")
    print(f"  - SCALE: {config.optical_flow.scale_width}x{config.optical_flow.scale_height}")
    print(f"  - THRESHOLD: {config.optical_flow.threshold}")
    print(f"  - MIN_DURATION: {config.optical_flow.min_duration}s")
    print(f"  - MERGE_GAP: {config.optical_flow.merge_gap}s")
    print(f"  - CENTER_CROP: {config.optical_flow.center_crop}")
    print()
    
    # Initialize detector
    detector = OpticalFlowDetector(config)
    
    # Import or detect segments
    if args.import_segments:
        print(f"Importing segments from: {args.import_segments}")
        segments = load_segments(args.import_segments)
    else:
        print("Detecting optical flow...")
        segments = detector.detect(args.input)
    
    # Export segments if requested
    if args.export_segments:
        print(f"Exporting segments to: {args.export_segments}")
        save_segments(args.export_segments, segments)
    
    # Print summary
    import cv2
    cap = cv2.VideoCapture(args.input)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps
    cap.release()
    
    print_summary(segments, duration)
    
    # Cut video or dry run
    if args.dry_run:
        print()
        print("[DRY RUN] Skipping actual video cutting.")
    else:
        if not args.output:
            base = os.path.splitext(os.path.basename(args.input))[0]
            args.output = f"{base}_highlight.mp4"
        
        print()
        print(f"Exporting to: {args.output}")
        
        exporter = VideoExporter(config)
        exporter.cut(args.input, segments, args.output)
        
        print()
        print(f"✓ Highlight video created: {args.output}")


if __name__ == "__main__":
    main()
