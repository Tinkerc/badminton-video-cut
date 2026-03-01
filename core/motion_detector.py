"""
core/motion_detector.py

Motion + Audio detection for badminton rally highlights.

This module refactors the logic from auto_cut.py into a reusable class
with configuration support.

Features:
- Motion detection via frame differencing
- Audio energy detection via librosa
- Dual-threshold segment detection
- Configurable parameters via Config

Usage:
    from core.motion_detector import MotionAudioDetector
    from config import Config
    
    config = Config.load()
    detector = MotionAudioDetector(config)
    
    segments = detector.detect("video.mp4")
    print(f"Found {len(segments)} segments")
"""

import cv2
import numpy as np
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import tempfile
import os

from config.config_loader import Config, MotionConfig
from core.audio_extractor import AudioExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MotionFrame:
    """Motion data for a single frame."""
    time: float
    motion: float


@dataclass
class AudioFrame:
    """Audio energy data for a single frame."""
    time: float
    energy: float


class MotionAudioDetector:
    """
    Detect badminton rallies using motion and audio cues.
    
    The detection algorithm:
    1. Sample frames at configured FPS
    2. Calculate motion via frame differencing
    3. Extract audio and calculate energy
    4. Combine signals with dual-threshold logic
    5. Build and merge segments
    
    Example:
        >>> config = Config.load()
        >>> detector = MotionAudioDetector(config)
        >>> segments = detector.detect("training_video.mp4")
        >>> print(segments)
        [(12.5, 45.2), (52.1, 78.3)]
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        motion_config: Optional[MotionConfig] = None
    ):
        """
        Initialize motion detector.
        
        Args:
            config: Full configuration object
            motion_config: Motion-specific configuration (overrides config)
        """
        if config is None:
            config = Config.load()
        
        self.config = config
        
        if motion_config is not None:
            self.motion_config = motion_config
        else:
            self.motion_config = config.motion
        
        self.audio_extractor = AudioExtractor(
            ffmpeg_path=config.general.ffmpeg_path,
            ffprobe_path=config.general.ffprobe_path
        )
        
        # Parameters from config
        self.sample_fps = self.motion_config.sample_fps
        self.motion_threshold = self.motion_config.threshold
        self.audio_threshold = self.motion_config.audio_threshold
        self.min_duration = self.motion_config.min_duration
        self.merge_gap = self.motion_config.merge_gap
    
    def detect(
        self,
        video_path: Path,
        progress_callback: Optional[callable] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect rally segments in video.
        
        Args:
            video_path: Path to input video
            progress_callback: Optional callback(current_percent, message)
            
        Returns:
            List of (start, end) tuples in seconds
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        logger.info(f"Detecting rallies in: {video_path.name}")
        logger.info(f"Parameters: sample_fps={self.sample_fps}, "
                   f"motion_thresh={self.motion_threshold}, "
                   f"audio_thresh={self.audio_threshold}")
        
        # Step 1: Detect motion
        if progress_callback:
            progress_callback(10, "Detecting motion...")
        
        logger.info("Step 1: Detecting motion...")
        motion_timeline, duration = self._detect_motion(video_path)
        logger.info(f"  Motion timeline: {len(motion_timeline)} samples, "
                   f"duration: {duration:.1f}s")
        
        # Step 2: Extract and detect audio
        if progress_callback:
            progress_callback(40, "Extracting audio...")
        
        logger.info("Step 2: Extracting audio...")
        audio_path, is_copy = self.audio_extractor.extract_for_analysis(video_path)
        
        if progress_callback:
            progress_callback(50, "Detecting audio...")
        
        logger.info("Step 3: Detecting audio energy...")
        audio_timeline = self._detect_audio(audio_path)
        logger.info(f"  Audio timeline: {len(audio_timeline)} samples")
        
        # Step 3: Combine signals
        if progress_callback:
            progress_callback(60, "Combining signals...")
        
        logger.info("Step 4: Combining signals...")
        combined = self._combine_signals(motion_timeline, audio_timeline, duration)
        
        # Step 4: Build segments
        if progress_callback:
            progress_callback(70, "Building segments...")
        
        logger.info("Step 5: Building segments...")
        segments = self._build_segments(combined)
        logger.info(f"  Raw segments: {len(segments)}")
        
        # Step 5: Merge segments
        if progress_callback:
            progress_callback(80, "Merging segments...")
        
        logger.info("Step 6: Merging segments...")
        segments = self._merge_segments(segments)
        logger.info(f"  Merged segments: {len(segments)}")
        
        # Cleanup temp audio file
        if audio_path.exists() and str(audio_path).startswith(tempfile.gettempdir()):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.debug(f"Failed to remove temp file: {e}")
        
        if progress_callback:
            progress_callback(100, f"Detection complete: {len(segments)} segments")
        
        return segments
    
    def _detect_motion(self, video_path: Path) -> Tuple[List[MotionFrame], float]:
        """
        Detect motion from video frames.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (motion_timeline, duration)
        """
        cap = cv2.VideoCapture(str(video_path))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = total_frames / fps
        
        step = max(1, int(fps / self.sample_fps))
        
        prev_gray = None
        timeline = []
        frame_id = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            if frame_id % step != 0:
                frame_id += 1
                continue
            
            # Convert to grayscale and resize
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (320, 180))
            
            if prev_gray is not None:
                # Calculate frame difference
                diff = cv2.absdiff(prev_gray, gray)
                motion = diff.mean()
                
                t = frame_id / fps
                timeline.append(MotionFrame(time=t, motion=motion))
            
            prev_gray = gray
            frame_id += 1
        
        cap.release()
        
        return timeline, duration
    
    def _detect_audio(self, audio_path: Path) -> List[AudioFrame]:
        """
        Detect audio energy from audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            List of AudioFrame objects
        """
        import librosa
        
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=16000)
        
        # Calculate RMS energy
        energy = librosa.feature.rms(y=y)[0]
        
        # Build timeline
        hop_length = 512
        timeline = []
        
        for i, e in enumerate(energy):
            t = i * hop_length / sr
            timeline.append(AudioFrame(time=t, energy=e))
        
        return timeline
    
    def _combine_signals(
        self,
        motion_timeline: List[MotionFrame],
        audio_timeline: List[AudioFrame],
        duration: float
    ) -> List[Tuple[int, float, float]]:
        """
        Combine motion and audio signals into per-second buckets.
        
        Args:
            motion_timeline: Motion data
            audio_timeline: Audio data
            duration: Video duration
            
        Returns:
            List of (second, motion, audio) tuples
        """
        # Bucket by second
        motion_by_second: Dict[int, List[float]] = {}
        audio_by_second: Dict[int, List[float]] = {}
        
        for frame in motion_timeline:
            second = int(frame.time)
            if second not in motion_by_second:
                motion_by_second[second] = []
            motion_by_second[second].append(frame.motion)
        
        for frame in audio_timeline:
            second = int(frame.time)
            if second not in audio_by_second:
                audio_by_second[second] = []
            audio_by_second[second].append(frame.energy)
        
        # Calculate averages
        combined = []
        
        for second in range(int(duration)):
            motion_values = motion_by_second.get(second, [])
            audio_values = audio_by_second.get(second, [])
            
            motion = sum(motion_values) / len(motion_values) if motion_values else 0
            audio = sum(audio_values) / len(audio_values) if audio_values else 0
            
            combined.append((second, motion, audio))
        
        return combined
    
    def _build_segments(
        self,
        combined: List[Tuple[int, float, float]]
    ) -> List[Tuple[float, float]]:
        """
        Build segments using dual-threshold logic.
        
        Both motion AND audio must exceed thresholds to keep a segment.
        
        Args:
            combined: Combined timeline data
            
        Returns:
            List of (start, end) tuples
        """
        segments = []
        start = None
        
        for t, motion, audio in combined:
            # Dual-threshold: BOTH must exceed
            if motion > self.motion_threshold and audio > self.audio_threshold:
                if start is None:
                    start = t
            else:
                if start is not None:
                    end = t
                    
                    if end - start >= self.min_duration:
                        segments.append((start, end))
                    
                    start = None
        
        # Handle open segment at end
        if start is not None:
            end = int(len(combined))
            if end - start >= self.min_duration:
                segments.append((start, end))
        
        return segments
    
    def _merge_segments(
        self,
        segments: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """
        Merge segments that are close together.
        
        Args:
            segments: Raw segments
            
        Returns:
            Merged segments
        """
        if not segments:
            return []
        
        # Sort by start time
        segments = sorted(segments)
        
        merged = [segments[0]]
        
        for start, end in segments[1:]:
            last_start, last_end = merged[-1]
            
            # Merge if gap is smaller than merge_gap
            if start - last_end < self.merge_gap:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        
        return merged
    
    def detect_with_debug(
        self,
        video_path: Path,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Detect with detailed debug information.
        
        Args:
            video_path: Input video
            output_path: Optional path for debug output
            
        Returns:
            Debug information dictionary
        """
        segments = self.detect(video_path)
        
        # Build debug info
        debug = {
            "video": str(video_path),
            "duration": None,
            "segments": segments,
            "total_highlight_duration": sum(e - s for s, e in segments),
            "parameters": {
                "sample_fps": self.sample_fps,
                "motion_threshold": self.motion_threshold,
                "audio_threshold": self.audio_threshold,
                "min_duration": self.min_duration,
                "merge_gap": self.merge_gap
            }
        }
        
        # Get duration
        cap = cv2.VideoCapture(str(video_path))
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        debug["duration"] = total_frames / fps
        cap.release()
        
        # Calculate stats
        debug["highlight_percentage"] = (
            debug["total_highlight_duration"] / debug["duration"] * 100
            if debug["duration"] > 0 else 0
        )
        
        debug["time_saved"] = debug["duration"] - debug["total_highlight_duration"]
        
        return debug


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


def save_segments(path: Path, segments: List[Tuple[float, float]]):
    """
    Save segments to file.
    
    Args:
        path: Output file path
        segments: List of (start, end) tuples
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        for start, end in sorted(segments):
            f.write(f"{start:.1f} {end:.1f}\n")
    
    logger.info(f"Segments saved to: {path}")
