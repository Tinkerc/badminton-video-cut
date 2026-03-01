"""
utils/batch_processor.py

Batch processing utilities for badminton video cutting.

Features:
- Process multiple videos in a folder
- Parallel processing support
- Progress tracking with tqdm
- Error handling and reporting

Usage:
    from utils.batch_processor import BatchProcessor
    from config import Config
    
    config = Config.load()
    processor = BatchProcessor(config)
    
    processor.process_folder(
        input_folder=Path("./videos/"),
        output_folder=Path("./highlights/"),
        detector_type="motion_audio"
    )
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    tqdm = None

from config.config_loader import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of processing a single video."""
    input_file: Path
    output_file: Optional[Path]
    segments_file: Optional[Path]
    segments: List[Tuple[float, float]]
    success: bool
    error: Optional[str]
    duration: float
    highlight_duration: float


class BatchProcessor:
    """
    Batch processor for multiple videos.
    
    Features:
    - Parallel processing with configurable workers
    - Progress tracking
    - Error reporting
    - JSON summary export
    
    Example:
        >>> config = Config.load()
        >>> processor = BatchProcessor(config)
        >>> results = processor.process_folder(
        ...     input_folder=Path("./videos/"),
        ...     output_folder=Path("./highlights/")
        ... )
        >>> print(f"Processed {len(results)} videos")
    """
    
    def __init__(self, config: Optional[Config] = None, max_workers: int = None):
        """
        Initialize batch processor.
        
        Args:
            config: Configuration object
            max_workers: Maximum parallel workers (default: from config or 4)
        """
        if config is None:
            config = Config.load()
        
        self.config = config
        
        if max_workers is None:
            max_workers = config.batch.max_workers
        
        self.max_workers = max_workers
        
        logger.info(f"BatchProcessor initialized with {max_workers} workers")
    
    def process_folder(
        self,
        input_folder: Path,
        output_folder: Optional[Path] = None,
        detector_type: str = "motion_audio",
        dry_run: bool = False,
        export_segments: Optional[Path] = None,
        patterns: Optional[List[str]] = None,
        resume: bool = False
    ) -> List[ProcessResult]:
        """
        Process all videos in a folder.

        Args:
            input_folder: Folder containing input videos
            output_folder: Folder for output highlights (default: input_folder/highlights)
            detector_type: Detection method ("motion_audio", "optical_flow", or "player")
            dry_run: Analyze only, don't export videos
            export_segments: Folder to export segment files
            patterns: File patterns to match (default: from config)
            resume: Resume failed batch (skip already processed videos)
        
        Returns:
            List of ProcessResult objects
        """
        input_folder = Path(input_folder)

        if not input_folder.exists():
            raise FileNotFoundError(f"Input folder not found: {input_folder}")

        if output_folder is None:
            output_folder = input_folder / "highlights"

        output_folder = Path(output_folder)

        if patterns is None:
            patterns = self.config.batch.video_patterns

        # Find all video files
        video_files = []
        for pattern in patterns:
            video_files.extend(input_folder.glob(f"*{pattern}"))

        video_files = sorted(set(video_files))

        if not video_files:
            logger.warning(f"No video files found in {input_folder}")
            return []

        # Resume mode: filter out already processed videos
        if resume and not dry_run:
            original_count = len(video_files)
            video_files = self._filter_pending_videos(video_files, output_folder)
            if len(video_files) < original_count:
                logger.info(f"Resume mode: {original_count - len(video_files)} videos already processed, "
                           f"{len(video_files)} pending")

        logger.info(f"Found {len(video_files)} video files")
        logger.info(f"Output folder: {output_folder}")
        logger.info(f"Detector type: {detector_type}")
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Resume mode: {resume}")

        # Create output folders
        if not dry_run:
            output_folder.mkdir(parents=True, exist_ok=True)

        if export_segments:
            export_segments = Path(export_segments)
            export_segments.mkdir(parents=True, exist_ok=True)

        # Process videos
        results = []

        if self.max_workers > 1:
            # Parallel processing
            results = self._process_parallel(
                video_files=video_files,
                output_folder=output_folder,
                detector_type=detector_type,
                dry_run=dry_run,
                export_segments_folder=export_segments
            )
        else:
            # Sequential processing
            results = self._process_sequential(
                video_files=video_files,
                output_folder=output_folder,
                detector_type=detector_type,
                dry_run=dry_run,
                export_segments_folder=export_segments
            )
        
        # Summary
        self._print_summary(results)
        
        # Export summary JSON
        summary_file = output_folder / "batch_summary.json"
        self._export_summary(results, summary_file)
        
        return results
    
    def _process_parallel(
        self,
        video_files: List[Path],
        output_folder: Path,
        detector_type: str,
        dry_run: bool,
        export_segments_folder: Optional[Path]
    ) -> List[ProcessResult]:
        """Process videos in parallel."""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(
                    self._process_single,
                    video_file,
                    output_folder,
                    detector_type,
                    dry_run,
                    export_segments_folder
                ): video_file
                for video_file in video_files
            }

            # Collect results as they complete with progress bar
            iterable = as_completed(future_to_file)
            if HAS_TQDM:
                iterable = tqdm(iterable, total=len(video_files), desc="Processing")

            for future in iterable:
                video_file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    status = "✓" if result.success else "✗"
                    if not HAS_TQDM:
                        logger.info(f"{status} {video_file.name}")

                except Exception as e:
                    logger.error(f"✗ {video_file.name}: {e}")
                    results.append(ProcessResult(
                        input_file=video_file,
                        output_file=None,
                        segments_file=None,
                        segments=[],
                        success=False,
                        error=str(e),
                        duration=0,
                        highlight_duration=0
                    ))

        return sorted(results, key=lambda r: r.input_file.name)
    
    def _process_sequential(
        self,
        video_files: List[Path],
        output_folder: Path,
        detector_type: str,
        dry_run: bool,
        export_segments_folder: Optional[Path]
    ) -> List[ProcessResult]:
        """Process videos sequentially."""
        results = []

        # Use tqdm for progress if available
        iterable = video_files
        if HAS_TQDM:
            iterable = tqdm(video_files, desc="Processing")

        for video_file in iterable:
            result = self._process_single(
                video_file,
                output_folder,
                detector_type,
                dry_run,
                export_segments_folder
            )

            results.append(result)

            status = "✓" if result.success else "✗"
            if not HAS_TQDM:
                logger.info(f"{status} {video_file.name}")

        return results
    
    def _process_single(
        self,
        video_file: Path,
        output_folder: Path,
        detector_type: str,
        dry_run: bool,
        export_segments_folder: Optional[Path]
    ) -> ProcessResult:
        """Process a single video file."""
        from core import MotionAudioDetector, OpticalFlowDetector, PlayerDetector, VideoExporter

        start_time = datetime.now()

        try:
            # Select detector
            if detector_type == "motion_audio":
                detector = MotionAudioDetector(self.config)
            elif detector_type == "optical_flow":
                detector = OpticalFlowDetector(self.config)
            elif detector_type == "player":
                detector = PlayerDetector(self.config)
            else:
                raise ValueError(f"Unknown detector type: {detector_type}")

            # Detect segments
            segments = detector.detect(video_file)
            
            # Determine output path
            output_file = output_folder / f"{video_file.stem}_highlight.mp4"
            
            segments_file = None
            if export_segments_folder:
                segments_file = export_segments_folder / f"{video_file.stem}_segments.txt"
                self._save_segments(segments_file, segments)
            
            # Export video
            if not dry_run and segments:
                exporter = VideoExporter(self.config)
                exporter.cut(video_file, segments, output_file)
            
            # Calculate durations
            import cv2
            cap = cv2.VideoCapture(str(video_file))
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            
            highlight_duration = sum(e - s for s, e in segments)
            
            return ProcessResult(
                input_file=video_file,
                output_file=output_file if not dry_run and segments else None,
                segments_file=segments_file,
                segments=segments,
                success=True,
                error=None,
                duration=duration,
                highlight_duration=highlight_duration
            )
            
        except Exception as e:
            logger.error(f"Error processing {video_file.name}: {e}")
            
            return ProcessResult(
                input_file=video_file,
                output_file=None,
                segments_file=None,
                segments=[],
                success=False,
                error=str(e),
                duration=0,
                highlight_duration=0
            )
    
    def _save_segments(self, path: Path, segments: List[Tuple[float, float]]):
        """Save segments to file."""
        with open(path, "w") as f:
            for start, end in sorted(segments):
                f.write(f"{start:.1f} {end:.1f}\n")
    
    def _print_summary(self, results: List[ProcessResult]):
        """Print processing summary."""
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        total_duration = sum(r.duration for r in results if r.success)
        total_highlight = sum(r.highlight_duration for r in results if r.success)
        
        print("\n" + "=" * 60)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 60)
        print(f"Total videos: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print()
        
        if successful > 0:
            print(f"Total input duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
            print(f"Total highlight duration: {total_highlight:.1f}s ({total_highlight/60:.1f} min)")
            print(f"Compression: {total_highlight/total_duration*100:.1f}%")
            print(f"Time saved: {total_duration - total_highlight:.1f}s")
        
        if failed > 0:
            print()
            print("Failed videos:")
            for r in results:
                if not r.success:
                    print(f"  - {r.input_file.name}: {r.error}")
        
        print("=" * 60)

    def _filter_pending_videos(
        self,
        video_files: List[Path],
        output_folder: Path
    ) -> List[Path]:
        """
        Filter out videos that have already been processed.
        
        A video is considered processed if its highlight file exists.
        
        Args:
            video_files: List of input video files
            output_folder: Output folder for highlights
            
        Returns:
            List of pending (not yet processed) video files
        """
        pending = []
        
        for video_file in video_files:
            output_file = output_folder / f"{video_file.stem}_highlight.mp4"
            
            if not output_file.exists():
                pending.append(video_file)
        
        return pending

    def _export_summary(self, results: List[ProcessResult], output_path: Path):
        """Export summary to JSON file."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "results": [
                {
                    "input_file": str(r.input_file),
                    "output_file": str(r.output_file) if r.output_file else None,
                    "segments_file": str(r.segments_file) if r.segments_file else None,
                    "segment_count": len(r.segments),
                    "segments": [{"start": s, "end": e} for s, e in r.segments],
                    "success": r.success,
                    "error": r.error,
                    "duration": r.duration,
                    "highlight_duration": r.highlight_duration
                }
                for r in results
            ]
        }
        
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary exported to: {output_path}")
