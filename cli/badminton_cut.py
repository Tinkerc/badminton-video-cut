#!/usr/bin/env python3
"""
cli/badminton_cut.py

Unified command-line interface for badminton video cutting tools.

Usage:
    badminton-cut auto input.mp4 output.mp4     # Motion + audio detection
    badminton-cut flow input.mp4 output.mp4     # Optical flow detection
    badminton-cut mark input.mp4 output.mp4     # Manual marking
    badminton-cut config export --out cfg.yaml  # Export config

Examples:
    # Single file processing
    badminton-cut auto match.mp4 highlights.mp4
    
    # Batch processing
    badminton-cut auto --input-folder ./videos/ --output-folder ./highlights/
    
    # Custom parameters
    badminton-cut auto match.mp4 highlights.mp4 --motion-threshold 10 --min-duration 5
    
    # Dry run (analysis only)
    badminton-cut auto match.mp4 --dry-run
    
    # Export/import segments
    badminton-cut auto match.mp4 --export-segments segments.txt
    badminton-cut auto match.mp4 --import-segments segments.txt
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    
    parser = argparse.ArgumentParser(
        prog="badminton-cut",
        description="Badminton Rally Highlight Cutter - Automatically extract rally highlights from badminton videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
=================================================================
Examples:

  # Process a single video with motion+audio detection
  badminton-cut auto match.mp4 highlights.mp4

  # Process all videos in a folder
  badminton-cut auto --input-folder ./videos/ --output-folder ./highlights/

  # Use optical flow detection (better for motion-heavy videos)
  badminton-cut flow training.mp4 output.mp4

  # Manual marking (most accurate)
  badminton-cut mark match.mp4 highlights.mp4

  # Custom parameters
  badminton-cut auto match.mp4 out.mp4 --motion-threshold 10 --min-duration 5

  # Analysis only (don't cut video)
  badminton-cut auto match.mp4 --dry-run

  # Export configuration template
  badminton-cut config export --output my_config.yaml

=================================================================
        """
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # =========================================================================
    # AUTO command (Motion + Audio detection)
    # =========================================================================
    auto_parser = subparsers.add_parser(
        "auto",
        help="Auto-detect rallies using motion + audio analysis",
        description="Detect badminton rallies using combined motion and audio analysis"
    )
    
    _add_common_input_args(auto_parser)
    _add_common_output_args(auto_parser)
    _add_motion_args(auto_parser)
    _add_common_processing_args(auto_parser)
    
    # =========================================================================
    # FLOW command (Optical flow detection)
    # =========================================================================
    flow_parser = subparsers.add_parser(
        "flow",
        help="Auto-detect rallies using optical flow analysis",
        description="Detect badminton rallies using optical flow (Farneback algorithm)"
    )

    _add_common_input_args(flow_parser)
    _add_common_output_args(flow_parser)
    _add_flow_args(flow_parser)
    _add_common_processing_args(flow_parser)

    # =========================================================================
    # PLAYER command (Player trajectory detection)
    # =========================================================================
    player_parser = subparsers.add_parser(
        "player",
        help="Auto-detect rallies using player trajectory (YOLO)",
        description="Detect badminton rallies using YOLO player detection"
    )

    _add_common_input_args(player_parser)
    _add_common_output_args(player_parser)
    _add_player_args(player_parser)
    _add_common_processing_args(player_parser)

    # =========================================================================
    # MARK command (Manual marking)
    # =========================================================================
    mark_parser = subparsers.add_parser(
        "mark",
        help="Manual rally marking with keyboard control",
        description="Manually mark rallies using keyboard controls"
    )
    
    mark_parser.add_argument(
        "input_file",
        type=Path,
        help="Input video file"
    )
    mark_parser.add_argument(
        "output_file",
        type=Path,
        nargs="?",
        default=None,
        help="Output video file (default: input_highlight.mp4)"
    )
    
    # =========================================================================
    # CONFIG command
    # =========================================================================
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management",
        description="Export or show configuration"
    )
    
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    # config export
    export_parser = config_subparsers.add_parser(
        "export",
        help="Export default configuration template"
    )
    export_parser.add_argument(
        "--output", "-o",
        type=Path,
        default="config.yaml",
        help="Output file path (default: config.yaml)"
    )
    
    # config show
    config_subparsers.add_parser(
        "show",
        help="Show current configuration"
    )
    
    return parser


def _add_common_input_args(parser):
    """Add common input arguments."""
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        help="Input video file"
    )
    input_group.add_argument(
        "--input-folder", "-i",
        type=Path,
        help="Input folder for batch processing"
    )


def _add_common_output_args(parser):
    """Add common output arguments."""
    parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        default=None,
        help="Output video file"
    )
    parser.add_argument(
        "--output-folder", "-o",
        type=Path,
        default=None,
        help="Output folder for batch processing"
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Custom configuration file"
    )


def _add_motion_args(parser):
    """Add motion detection arguments."""
    parser.add_argument(
        "--motion-threshold",
        type=float,
        default=None,
        help="Motion threshold (higher = less sensitive)"
    )
    parser.add_argument(
        "--audio-threshold",
        type=float,
        default=None,
        help="Audio energy threshold"
    )
    parser.add_argument(
        "--sample-fps",
        type=int,
        default=None,
        help="Frames sampled per second"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Minimum segment duration (seconds)"
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=None,
        help="Merge segments closer than this (seconds)"
    )


def _add_flow_args(parser):
    """Add optical flow arguments."""
    parser.add_argument(
        "--flow-threshold",
        type=float,
        default=None,
        help="Optical flow score threshold"
    )
    parser.add_argument(
        "--sample-fps",
        type=int,
        default=None,
        help="Frames sampled per second"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Minimum segment duration (seconds)"
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=None,
        help="Merge gap (seconds)"
    )
    parser.add_argument(
        "--no-center-crop",
        action="store_true",
        help="Disable center crop (analyze full frame)"
    )


def _add_player_args(parser):
    """Add player detection arguments."""
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="YOLO model (default: yolov8s.pt)"
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=None,
        help="Sliding window size (seconds)"
    )
    parser.add_argument(
        "--threshold-ratio",
        type=float,
        default=None,
        help="Adaptive threshold ratio (0-1)"
    )
    parser.add_argument(
        "--sample-fps",
        type=int,
        default=None,
        help="Frames sampled per second"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Minimum segment duration (seconds)"
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=None,
        help="Merge gap (seconds)"
    )
    parser.add_argument(
        "--no-velocity-std",
        action="store_true",
        help="Use distance instead of velocity std scoring"
    )


def _add_common_processing_args(parser):
    """Add common processing arguments."""
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't cut video"
    )
    parser.add_argument(
        "--export-segments",
        type=Path,
        default=None,
        help="Export segments to file"
    )
    parser.add_argument(
        "--import-segments",
        type=Path,
        default=None,
        help="Import segments from file (skip detection)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume failed batch (skip already processed videos)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    # Set logging level
    if hasattr(args, 'verbose') and args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Route to appropriate handler
    if args.command == "config":
        _handle_config(args)
    elif args.command == "auto":
        _handle_auto(args)
    elif args.command == "flow":
        _handle_flow(args)
    elif args.command == "mark":
        _handle_mark(args)
    else:
        parser.print_help()
        sys.exit(1)


def _handle_config(args):
    """Handle config command."""
    from config import Config
    import yaml
    
    if args.config_command == "export":
        # Export default configuration
        config = Config.load()
        config.save(args.output)
        print(f"Configuration exported to: {args.output}")
        
    elif args.config_command == "show":
        # Show current configuration
        config = Config.load()
        print(yaml.dump(config.to_dict(), default_flow_style=False))
    
    else:
        print("Usage: badminton-cut config {export|show}")
        sys.exit(1)


def _handle_auto(args):
    """Handle auto command (motion + audio detection)."""
    from config import Config
    from core import MotionAudioDetector, VideoExporter
    from utils.batch_processor import BatchProcessor
    
    # Load configuration
    config = Config.load(args.config)
    
    # Apply command-line overrides
    _apply_motion_overrides(config, args)
    
    # Check for batch mode
    if args.input_folder:
        _handle_batch_auto(args, config)
    else:
        _handle_single_auto(args, config)


def _handle_single_auto(args, config):
    """Handle single file auto processing."""
    from core import MotionAudioDetector, VideoExporter
    
    detector = MotionAudioDetector(config)
    exporter = VideoExporter(config)
    
    # Import or detect segments
    if args.import_segments:
        logger.info(f"Importing segments from: {args.import_segments}")
        segments = _load_segments(args.import_segments)
    else:
        logger.info(f"Detecting rallies in: {args.input_file}")
        segments = detector.detect(args.input_file)
    
    # Export segments if requested
    if args.export_segments:
        logger.info(f"Exporting segments to: {args.export_segments}")
        _save_segments(args.export_segments, segments)
    
    # Cut video or dry run
    if args.dry_run:
        _print_detection_summary(args.input_file, segments)
    else:
        if not args.output_file:
            args.output_file = args.input_file.with_name(
                f"{args.input_file.stem}_highlight{args.input_file.suffix}"
            )
        
        logger.info(f"Exporting to: {args.output_file}")
        exporter.cut(args.input_file, segments, args.output_file)
        print(f"\n✓ Highlight video created: {args.output_file}")


def _handle_batch_auto(args, config):
    """Handle batch auto processing."""
    from utils.batch_processor import BatchProcessor

    processor = BatchProcessor(config)

    processor.process_folder(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        detector_type="motion_audio",
        dry_run=args.dry_run,
        export_segments=args.export_segments,
        resume=args.resume
    )


def _handle_flow(args):
    """Handle flow command (optical flow detection)."""
    from config import Config
    from core import OpticalFlowDetector, VideoExporter
    from utils.batch_processor import BatchProcessor
    
    # Load configuration
    config = Config.load(args.config)
    
    # Apply command-line overrides
    _apply_flow_overrides(config, args)
    
    # Check for batch mode
    if args.input_folder:
        _handle_batch_flow(args, config)
    else:
        _handle_single_flow(args, config)


def _handle_single_flow(args, config):
    """Handle single file flow processing."""
    from core import OpticalFlowDetector, VideoExporter

    detector = OpticalFlowDetector(config)
    exporter = VideoExporter(config)

    # Import or detect segments
    if args.import_segments:
        logger.info(f"Importing segments from: {args.import_segments}")
        segments = _load_segments(args.import_segments)
    else:
        logger.info(f"Detecting rallies (optical flow) in: {args.input_file}")
        segments = detector.detect(args.input_file)

    # Export segments if requested
    if args.export_segments:
        logger.info(f"Exporting segments to: {args.export_segments}")
        _save_segments(args.export_segments, segments)

    # Cut video or dry run
    if args.dry_run:
        _print_detection_summary(args.input_file, segments)
    else:
        if not args.output_file:
            args.output_file = args.input_file.with_name(
                f"{args.input_file.stem}_highlight{args.input_file.suffix}"
            )

        logger.info(f"Exporting to: {args.output_file}")
        exporter.cut(args.input_file, segments, args.output_file)
        print(f"\n✓ Highlight video created: {args.output_file}")


def _handle_batch_flow(args, config):
    """Handle batch flow processing."""
    from utils.batch_processor import BatchProcessor

    processor = BatchProcessor(config)

    processor.process_folder(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        detector_type="optical_flow",
        dry_run=args.dry_run,
        export_segments=args.export_segments,
        resume=args.resume
    )


def _handle_player(args):
    """Handle player command (player trajectory detection)."""
    from config import Config
    from core import PlayerDetector, VideoExporter
    
    # Check ultralytics installation
    try:
        import ultralytics  # noqa
    except ImportError:
        print("Error: ultralytics not installed.")
        print("Install with: pip install ultralytics")
        sys.exit(1)

    # Load configuration
    config = Config.load(args.config)

    # Apply command-line overrides
    _apply_player_overrides(config, args)

    # Check for batch mode
    if args.input_folder:
        _handle_batch_player(args, config)
    else:
        _handle_single_player(args, config)


def _handle_single_player(args, config):
    """Handle single file player processing."""
    from core import PlayerDetector, VideoExporter

    detector = PlayerDetector(config)
    exporter = VideoExporter(config)

    # Import or detect segments
    if args.import_segments:
        logger.info(f"Importing segments from: {args.import_segments}")
        segments = _load_segments(args.import_segments)
    else:
        logger.info(f"Detecting rallies (player trajectory) in: {args.input_file}")
        segments = detector.detect(args.input_file)

    # Export segments if requested
    if args.export_segments:
        logger.info(f"Exporting segments to: {args.export_segments}")
        _save_segments(args.export_segments, segments)

    # Cut video or dry run
    if args.dry_run:
        _print_detection_summary(args.input_file, segments)
    else:
        if not args.output_file:
            args.output_file = args.input_file.with_name(
                f"{args.input_file.stem}_highlight{args.input_file.suffix}"
            )

        logger.info(f"Exporting to: {args.output_file}")
        exporter.cut(args.input_file, segments, args.output_file)
        print(f"\n✓ Highlight video created: {args.output_file}")


def _handle_batch_player(args, config):
    """Handle batch player processing."""
    from utils.batch_processor import BatchProcessor

    processor = BatchProcessor(config)

    processor.process_folder(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        detector_type="player",
        dry_run=args.dry_run,
        export_segments=args.export_segments,
        resume=args.resume
    )

def _handle_mark(args):
    """Handle mark command (manual marking)."""
    # For now, delegate to the existing mark_rallies.py
    # In future, we can refactor it to use core modules
    import subprocess
    
    cmd = [sys.executable, "mark_rallies.py", str(args.input_file)]
    
    if args.output_file:
        cmd.append(str(args.output_file))
    
    logger.info(f"Running manual marking: {' '.join(cmd)}")
    subprocess.run(cmd)


def _apply_motion_overrides(config, args):
    """Apply command-line overrides to motion config."""
    if args.motion_threshold is not None:
        config.motion.threshold = args.motion_threshold
        logger.debug(f"Override motion threshold: {args.motion_threshold}")
    
    if args.audio_threshold is not None:
        config.motion.audio_threshold = args.audio_threshold
        logger.debug(f"Override audio threshold: {args.audio_threshold}")
    
    if args.sample_fps is not None:
        config.motion.sample_fps = args.sample_fps
        logger.debug(f"Override sample FPS: {args.sample_fps}")
    
    if args.min_duration is not None:
        config.motion.min_duration = args.min_duration
        logger.debug(f"Override min duration: {args.min_duration}")
    
    if args.merge_gap is not None:
        config.motion.merge_gap = args.merge_gap
        logger.debug(f"Override merge gap: {args.merge_gap}")


def _apply_flow_overrides(config, args):
    """Apply command-line overrides to optical flow config."""
    if args.flow_threshold is not None:
        config.optical_flow.threshold = args.flow_threshold
        logger.debug(f"Override flow threshold: {args.flow_threshold}")
    
    if args.sample_fps is not None:
        config.optical_flow.sample_fps = args.sample_fps
        logger.debug(f"Override sample FPS: {args.sample_fps}")
    
    if args.min_duration is not None:
        config.optical_flow.min_duration = args.min_duration
        logger.debug(f"Override min duration: {args.min_duration}")
    
    if args.merge_gap is not None:
        config.optical_flow.merge_gap = args.merge_gap
        logger.debug(f"Override merge gap: {args.merge_gap}")
    
    if args.no_center_crop:
        config.optical_flow.center_crop = False
        logger.debug("Disable center crop")


def _apply_player_overrides(config, args):
    """Apply command-line overrides to player config."""
    if args.model is not None:
        config.player.model = args.model
        logger.debug(f"Override model: {args.model}")

    if args.window_seconds is not None:
        config.player.window_seconds = args.window_seconds
        logger.debug(f"Override window seconds: {args.window_seconds}")

    if args.threshold_ratio is not None:
        config.player.threshold_ratio = args.threshold_ratio
        logger.debug(f"Override threshold ratio: {args.threshold_ratio}")

    if args.sample_fps is not None:
        config.player.sample_fps = args.sample_fps
        logger.debug(f"Override sample FPS: {args.sample_fps}")

    if args.min_duration is not None:
        config.player.min_duration = args.min_duration
        logger.debug(f"Override min duration: {args.min_duration}")

    if args.merge_gap is not None:
        config.player.merge_gap = args.merge_gap
        logger.debug(f"Override merge gap: {args.merge_gap}")

    if args.no_velocity_std:
        config.player.use_velocity_std = False
        logger.debug("Disable velocity std scoring")


def _print_detection_summary(video_path: Path, segments: List[Tuple[float, float]]):
    """Print detection summary for dry run."""
    import cv2
    
    # Get video duration
    cap = cv2.VideoCapture(str(video_path))
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps
    cap.release()
    
    # Calculate statistics
    total_highlight = sum(e - s for s, e in segments)
    
    print("\n" + "=" * 60)
    print("DETECTION SUMMARY (Dry Run)")
    print("=" * 60)
    print(f"Input: {video_path}")
    print(f"Duration: {duration:.1f}s")
    print(f"Segments found: {len(segments)}")
    print()
    
    if segments:
        print("Segments:")
        for i, (s, e) in enumerate(segments):
            print(f"  {i+1}. {s:6.1f}s - {e:6.1f}s  ({e-s:5.1f}s)")
        
        print()
        print(f"Total highlight: {total_highlight:.1f}s ({total_highlight/duration*100:.1f}%)")
        print(f"Time saved: {duration - total_highlight:.1f}s ({(duration-total_highlight)/duration*100:.1f}%)")
    else:
        print("No segments detected. Try adjusting thresholds.")
    
    print("=" * 60)


def _load_segments(path: Path) -> List[Tuple[float, float]]:
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


def _save_segments(path: Path, segments: List[Tuple[float, float]]):
    """Save segments to file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        for start, end in sorted(segments):
            f.write(f"{start:.1f} {end:.1f}\n")
    
    logger.info(f"Segments saved to: {path}")


if __name__ == "__main__":
    main()
