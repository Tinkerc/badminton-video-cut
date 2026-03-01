"""
core/video_exporter.py

Unified video export engine for badminton rally highlights.

This module provides the Phase-H v2 high-performance export functionality:
- Single-pass FFmpeg filter_complex concat (2x faster)
- Frame-level precision cuts (zero stutter)
- Configurable quality/speed tradeoffs
- Optional GPU acceleration (NVENC)

Usage:
    from core.video_exporter import VideoExporter
    from config import Config
    
    config = Config.load()
    exporter = VideoExporter(config)
    
    # Export segments to highlight video
    exporter.cut("video.mp4", [(10.5, 42.0), (48.3, 75.8)], "output.mp4")
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from config.config_loader import Config, ExportConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoExportError(Exception):
    """Custom exception for video export errors."""
    pass


class VideoExporter:
    """
    High-performance video exporter using FFmpeg filter_complex.
    
    Features:
    - Single-pass encoding (faster than temp clips)
    - Frame-level precision cuts
    - Configurable quality (CRF) and speed (preset)
    - Optional GPU acceleration (NVENC)
    - Faststart for web playback
    
    Example:
        >>> config = Config.load()
        >>> exporter = VideoExporter(config)
        >>> segments = [(10.5, 42.0), (48.3, 75.8)]
        >>> exporter.cut("video.mp4", segments, "highlights.mp4")
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        export_config: Optional[ExportConfig] = None
    ):
        """
        Initialize video exporter.
        
        Args:
            config: Full configuration object
            export_config: Export-specific configuration (overrides config)
        """
        if config is None:
            config = Config.load()
        
        self.config = config
        
        if export_config is not None:
            self.export_config = export_config
        else:
            self.export_config = config.export
        
        self.ffmpeg_path = config.general.ffmpeg_path
        
        # Verify FFmpeg
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        """Verify FFmpeg is installed."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"FFmpeg found: {result.stdout.splitlines()[0]}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise VideoExportError(
                "FFmpeg not found. Please install FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Linux: sudo apt install ffmpeg\n"
                "  Windows: https://ffmpeg.org/download.html"
            )
    
    def cut(
        self,
        video_path: Path,
        segments: List[Tuple[float, float]],
        output_path: Path,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Cut and concatenate video segments.
        
        Uses FFmpeg filter_complex for single-pass processing.
        
        Args:
            video_path: Input video file
            segments: List of (start, end) tuples in seconds
            output_path: Output video file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to output file
            
        Raises:
            VideoExportError: If export fails
            FileNotFoundError: If input file not found
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        if not segments:
            logger.warning("No segments to export")
            return None
        
        logger.info(f"Exporting {len(segments)} segments to: {output_path.name}")
        
        # Sort segments
        segments = sorted(segments)
        
        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(video_path, segments, output_path)
        
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        if progress_callback:
            progress_callback(0, "Starting export...")
        
        # Execute FFmpeg
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                raise VideoExportError(f"FFmpeg failed: {error_msg}")
            
            if not output_path.exists():
                raise VideoExportError(f"Output file not created: {output_path}")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Export complete: {output_path} ({file_size_mb:.1f} MB)")
            
            if progress_callback:
                progress_callback(100, "Export complete")
            
            return output_path
            
        except Exception as e:
            raise VideoExportError(f"Export failed: {e}")
    
    def _build_ffmpeg_command(
        self,
        video_path: Path,
        segments: List[Tuple[float, float]],
        output_path: Path
    ) -> list:
        """
        Build FFmpeg command with filter_complex.
        
        Args:
            video_path: Input video
            segments: List of segments
            output_path: Output file
            
        Returns:
            FFmpeg command list
        """
        # Build trim filters for video
        video_filters = []
        audio_filters = []
        
        for i, (start, end) in enumerate(segments):
            # Video trim with timestamp reset
            video_filters.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )
            
            # Audio trim with timestamp reset
            audio_filters.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},"
                f"asetpts=PTS-STARTPTS[a{i}]"
            )
        
        # Build concat labels
        v_labels = "".join([f"[v{i}]" for i in range(len(segments))])
        a_labels = "".join([f"[a{i}]" for i in range(len(segments))])
        
        # Build filter_complex string
        all_filters = video_filters + audio_filters
        filter_complex = ";".join(all_filters)
        filter_complex += f";{v_labels}{a_labels}concat=n={len(segments)}:v=1:a=1[outv][outa]"
        
        # Build base command
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output
            "-i", str(video_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]"
        ]
        
        # Add encoding options
        if self.export_config.use_gpu:
            # GPU encoding (NVENC)
            cmd.extend([
                "-c:v", "h264_cuvid" if "cuvid" in self.export_config.codec else self.export_config.codec,
                "-preset", self._map_preset(self.export_config.preset),
                "-cq", str(self.export_config.crf)  # CQ mode for GPU
            ])
        else:
            # CPU encoding (x264)
            cmd.extend([
                "-c:v", self.export_config.codec,
                "-preset", self.export_config.preset,
                "-crf", str(self.export_config.crf)
            ])
        
        # Audio encoding
        cmd.extend([
            "-c:a", self.export_config.audio_codec,
            "-b:a", self.export_config.audio_bitrate
        ])
        
        # Faststart for web playback
        if self.export_config.faststart:
            cmd.extend(["-movflags", "+faststart"])
        
        cmd.append(str(output_path))
        
        return cmd
    
    def _map_preset(self, preset: str) -> str:
        """
        Map preset name to FFmpeg preset.
        
        For GPU encoding, some presets need mapping.
        """
        # GPU preset mapping (if needed)
        gpu_presets = {
            "ultrafast": "p1",
            "veryfast": "p2",
            "faster": "p3",
            "fast": "p4",
            "medium": "p5",
            "slow": "p6",
            "slower": "p7",
            "veryslow": "p8"
        }
        
        if self.export_config.use_gpu and preset in gpu_presets:
            return gpu_presets[preset]
        
        return preset
    
    def export_with_segments(
        self,
        video_path: Path,
        segments: List[Tuple[float, float]],
        output_path: Path,
        segments_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Export video and optionally save segments file.
        
        Args:
            video_path: Input video
            segments: List of segments
            output_path: Output video
            segments_file: Optional path to save segments
            
        Returns:
            Export statistics dictionary
        """
        # Export video
        self.cut(video_path, segments, output_path)
        
        # Save segments file
        if segments_file:
            self._save_segments(segments_file, segments)
        
        # Calculate statistics
        cap = subprocess.run(
            [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-f", "null", "-"
            ],
            capture_output=True,
            text=True
        )
        
        # Parse duration from stderr
        duration = None
        for line in cap.stderr.splitlines():
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                duration = float(h) * 3600 + float(m) * 60 + float(s)
                break
        
        total_duration = sum(e - s for s, e in segments)
        
        return {
            "input": str(video_path),
            "output": str(output_path),
            "segments": segments,
            "segment_count": len(segments),
            "input_duration": duration,
            "output_duration": total_duration,
            "compression_ratio": total_duration / duration if duration else None,
            "time_saved": duration - total_duration if duration else None
        }
    
    @staticmethod
    def _save_segments(path: Path, segments: List[Tuple[float, float]]):
        """Save segments to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            for start, end in sorted(segments):
                f.write(f"{start:.1f} {end:.1f}\n")
        
        logger.info(f"Segments saved to: {path}")
    
    @staticmethod
    def load_segments(path: Path) -> List[Tuple[float, float]]:
        """
        Load segments from file.
        
        Args:
            path: Path to segments file
            
        Returns:
            List of (start, end) tuples
        """
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
    
    def cut_with_copy(
        self,
        video_path: Path,
        segments: List[Tuple[float, float]],
        output_path: Path
    ) -> Path:
        """
        Cut video using stream copy (fastest, no re-encoding).
        
        Note: This method uses multiple FFmpeg passes (one per segment
        plus concat) but avoids re-encoding, making it faster for
        large videos where quality is acceptable.
        
        Args:
            video_path: Input video
            segments: List of segments
            output_path: Output video
            
        Returns:
            Path to output file
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        
        if not segments:
            logger.warning("No segments to export")
            return None
        
        logger.info(f"Exporting {len(segments)} segments (copy mode) to: {output_path.name}")
        
        import tempfile
        import os
        
        segments = sorted(segments)
        temp_files = []
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="badminton_cut_")
        
        try:
            # Step 1: Cut individual segments
            for i, (start, end) in enumerate(segments):
                temp_file = Path(temp_dir) / f"clip_{i}.mp4"
                
                cmd = [
                    self.ffmpeg_path,
                    "-y",
                    "-ss", str(start),
                    "-to", str(end),
                    "-i", str(video_path),
                    "-c", "copy",
                    str(temp_file)
                ]
                
                result = subprocess.run(cmd, capture_output=True)
                
                if result.returncode != 0:
                    logger.warning(f"Segment {i} copy failed, will re-encode")
                    # Fall back to re-encoding
                    cmd = [
                        self.ffmpeg_path,
                        "-y",
                        "-ss", str(start),
                        "-to", str(end),
                        "-i", str(video_path),
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "18",
                        "-c:a", "aac",
                        str(temp_file)
                    ]
                    result = subprocess.run(cmd, capture_output=True)
                
                if temp_file.exists():
                    temp_files.append(temp_file)
                else:
                    logger.error(f"Failed to create segment {i}")
            
            if not temp_files:
                raise VideoExportError("No segments created")
            
            # Step 2: Create concat file
            concat_file = Path(temp_dir) / "concat.txt"
            
            with open(concat_file, "w") as f:
                for temp_file in temp_files:
                    f.write(f"file '{temp_file}'\n")
            
            # Step 3: Concatenate
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode != 0:
                raise VideoExportError(f"Concat failed: {result.stderr.decode()}")
            
            logger.info(f"Export complete (copy mode): {output_path}")
            return output_path
            
        finally:
            # Cleanup temp files
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.debug(f"Failed to cleanup temp files: {e}")
