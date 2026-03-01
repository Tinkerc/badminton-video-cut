"""
core/audio_extractor.py

Production-grade audio extraction module for badminton video processing.

Features:
- Auto-detect original audio codec (AAC/Opus/MP3)
- Copy mode (fastest, lossless) or transcode mode
- Batch processing support
- CLI and Python API

Usage:
    from core.audio_extractor import AudioExtractor
    
    extractor = AudioExtractor()
    
    # Copy mode (fastest)
    extractor.extract_audio("video.mp4", use_copy=True)
    
    # Transcode to WAV
    extractor.extract_audio("video.mp4", audio_format="wav")
    
    # Batch extract
    extractor.batch_extract("./videos/", output_folder="./audio/")
"""

from pathlib import Path
import subprocess
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AudioStreamInfo:
    """Audio stream information from video file."""
    codec_name: str
    sample_rate: int
    channels: int
    bit_rate: Optional[int] = None
    duration: Optional[float] = None
    
    def __str__(self) -> str:
        """String representation."""
        info = f"{self.codec_name}"
        if self.sample_rate:
            info += f", {self.sample_rate}Hz"
        if self.channels:
            info += f", {self.channels}ch"
        if self.bit_rate:
            info += f", {self.bit_rate // 1000}kbps"
        return info


class AudioExtractionError(Exception):
    """Custom exception for audio extraction errors."""
    pass


class AudioExtractor:
    """
    Production-grade audio extractor.
    
    Supports:
    - Copy mode: Direct stream copy (fastest, lossless)
    - Transcode mode: Convert to WAV/MP3/AAC
    
    Example:
        >>> extractor = AudioExtractor()
        >>> info = extractor.detect_audio_stream("video.mp4")
        >>> print(f"Audio codec: {info.codec_name}")
        >>> extractor.extract_audio("video.mp4", "audio.wav", use_copy=False)
    """
    
    # Supported audio formats and their codecs
    CODECS = {
        "wav": "pcm_s16le",
        "mp3": "libmp3lame",
        "aac": "aac"
    }
    
    # Map codec to recommended file extension
    CODEC_TO_EXT = {
        "aac": "aac",
        "mp3": "mp3",
        "opus": "opus",
        "vorbis": "ogg",
        "pcm_s16le": "wav",
        "pcm_s24le": "wav",
        "pcm_s32le": "wav"
    }
    
    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe"
    ):
        """
        Initialize audio extractor.
        
        Args:
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        
        # Verify FFmpeg is available
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        """Verify FFmpeg is installed and accessible."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"FFmpeg found: {result.stdout.splitlines()[0]}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise AudioExtractionError(
                "FFmpeg not found. Please install FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Linux: sudo apt install ffmpeg\n"
                "  Windows: https://ffmpeg.org/download.html"
            )
    
    def detect_audio_stream(self, video_path: Path) -> Optional[AudioStreamInfo]:
        """
        Detect audio stream information in video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            AudioStreamInfo if audio stream exists, None otherwise
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "a:0",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            if not data.get("streams"):
                logger.debug(f"No audio stream found in {video_path}")
                return None
            
            stream = data["streams"][0]
            
            return AudioStreamInfo(
                codec_name=stream.get("codec_name", "unknown"),
                sample_rate=int(stream.get("sample_rate", 0)),
                channels=int(stream.get("channels", 0)),
                bit_rate=int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None,
                duration=float(stream.get("duration", 0)) if stream.get("duration") else None
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed for {video_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {video_path}: {e}")
            return None
    
    def extract_audio(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        audio_format: str = "wav",
        use_copy: bool = False,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_bitrate: str = "192k"
    ) -> Path:
        """
        Extract audio from video file.
        
        Args:
            video_path: Input video file path
            output_path: Output audio file path (optional, auto-generated if None)
            audio_format: Target format (wav/mp3/aac), ignored if use_copy=True
            use_copy: If True, copy stream without re-encoding (fastest)
            sample_rate: Sample rate for WAV output (Hz)
            channels: Number of audio channels (1=mono, 2=stereo)
            audio_bitrate: Bitrate for MP3/AAC output (e.g., "192k")
            
        Returns:
            Path to output audio file
            
        Raises:
            AudioExtractionError: If extraction fails
            FileNotFoundError: If video file not found
            ValueError: If unsupported audio format
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Detect original audio stream
        stream_info = self.detect_audio_stream(video_path)
        
        # Determine output path
        if output_path is None:
            if use_copy and stream_info:
                ext = self._codec_to_ext(stream_info.codec_name)
            else:
                ext = audio_format
            output_path = video_path.with_suffix("." + ext)
        else:
            output_path = Path(output_path)
        
        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y", "-i", str(video_path), "-vn"]
        
        if use_copy:
            # Copy mode: fastest, lossless
            cmd.extend(["-acodec", "copy"])
            logger.info(
                f"Extracting audio (copy mode): {video_path.name} -> {output_path.name}\n"
                f"  Original codec: {stream_info}" if stream_info else ""
            )
        else:
            # Transcode mode
            if audio_format not in self.CODECS:
                raise ValueError(
                    f"Unsupported format: {audio_format}. "
                    f"Supported: {list(self.CODECS.keys())}"
                )
            
            codec = self.CODECS[audio_format]
            cmd.extend(["-acodec", codec])
            
            # Format-specific options
            if audio_format == "wav":
                cmd.extend(["-ar", str(sample_rate), "-ac", str(channels)])
            elif audio_format in ("mp3", "aac"):
                cmd.extend(["-b:a", audio_bitrate])
            
            logger.info(
                f"Extracting audio (transcode to {audio_format}): "
                f"{video_path.name} -> {output_path.name}\n"
                f"  Codec: {codec}, Sample rate: {sample_rate}Hz, Channels: {channels}"
            )
        
        cmd.append(str(output_path))
        
        # Execute FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.decode(errors="ignore")
            raise AudioExtractionError(f"FFmpeg failed: {error_msg}")
        
        # Verify output file was created
        if not output_path.exists():
            raise AudioExtractionError(f"Output file not created: {output_path}")
        
        logger.info(f"Audio extracted: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
        return output_path
    
    def _get_codec(self, fmt: str) -> str:
        """Get codec name for audio format."""
        if fmt not in self.CODECS:
            raise ValueError(f"Unsupported format: {fmt}")
        return self.CODECS[fmt]
    
    def _codec_to_ext(self, codec: str) -> str:
        """Get recommended file extension for codec."""
        return self.CODEC_TO_EXT.get(codec, "wav")
    
    def batch_extract(
        self,
        input_folder: Path,
        output_folder: Optional[Path] = None,
        patterns: Optional[List[str]] = None,
        use_copy: bool = False,
        audio_format: str = "wav",
        **kwargs
    ) -> List[Path]:
        """
        Batch extract audio from multiple video files.
        
        Args:
            input_folder: Folder containing video files
            output_folder: Output folder (default: input_folder/audio)
            patterns: File patterns to match (default: [".mp4", ".webm"])
            use_copy: Use copy mode for all files
            audio_format: Target format for transcoding
            **kwargs: Additional arguments passed to extract_audio()
            
        Returns:
            List of output audio file paths
        """
        if patterns is None:
            patterns = [".mp4", ".webm", ".mkv", ".avi", ".mov"]
        
        input_folder = Path(input_folder)
        
        if not input_folder.exists():
            raise FileNotFoundError(f"Input folder not found: {input_folder}")
        
        if output_folder is None:
            output_folder = input_folder / "audio"
        
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        
        output_files = []
        failed_files = []
        
        logger.info(f"Batch extracting from: {input_folder}")
        logger.info(f"Output folder: {output_folder}")
        logger.info(f"Patterns: {patterns}")
        logger.info(f"Mode: {'copy' if use_copy else f'transcode to {audio_format}'}")
        logger.info("=" * 60)
        
        for pattern in patterns:
            for video_path in input_folder.glob(f"*{pattern}"):
                try:
                    output_path = output_folder / f"{video_path.stem}.wav"
                    self.extract_audio(
                        video_path,
                        output_path,
                        audio_format=audio_format,
                        use_copy=use_copy,
                        **kwargs
                    )
                    output_files.append(output_path)
                    logger.info(f"✓ {video_path.name}")
                except Exception as e:
                    failed_files.append((video_path, str(e)))
                    logger.error(f"✗ {video_path.name}: {e}")
        
        # Summary
        logger.info("=" * 60)
        logger.info(f"Batch complete: {len(output_files)} succeeded, {len(failed_files)} failed")
        
        if failed_files:
            logger.warning("Failed files:")
            for path, error in failed_files:
                logger.warning(f"  - {path.name}: {error}")
        
        return output_files
    
    def extract_for_analysis(
        self,
        video_path: Path,
        temp_dir: Optional[Path] = None
    ) -> tuple[Path, bool]:
        """
        Extract audio optimized for analysis (e.g., motion+audio detection).
        
        This is a convenience method that:
        1. Tries copy mode first (fastest)
        2. Falls back to WAV if copy fails or codec is incompatible
        
        Args:
            video_path: Input video file
            temp_dir: Directory for temp files (default: video's parent)
            
        Returns:
            Tuple of (audio_path, is_copy)
        """
        video_path = Path(video_path)
        
        if temp_dir is None:
            temp_dir = video_path.parent
        
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Detect original codec
        stream_info = self.detect_audio_stream(video_path)
        
        if stream_info:
            # Check if original codec is suitable for analysis
            suitable_codecs = ["pcm_s16le", "aac", "mp3"]
            
            if stream_info.codec_name in suitable_codecs:
                # Use copy mode
                output_path = temp_dir / f"{video_path.stem}.tmp{self._codec_to_ext(stream_info.codec_name)}"
                try:
                    self.extract_audio(video_path, output_path, use_copy=True)
                    logger.debug(f"Using copy mode for {video_path.name}")
                    return output_path, True
                except AudioExtractionError:
                    pass  # Fall through to transcode
        
        # Transcode to WAV for analysis
        output_path = temp_dir / f"{video_path.stem}.tmp.wav"
        self.extract_audio(
            video_path,
            output_path,
            audio_format="wav",
            sample_rate=16000,
            channels=1
        )
        logger.debug(f"Using transcode mode for {video_path.name}")
        return output_path, False
