"""
core/flow_detector.py

Optical flow detection for badminton rally highlights.

This module refactors the logic from auto_cut_flow.py into a reusable class
with configuration support.

Features:
- Farneback optical flow calculation
- Motion pattern analysis via flow features
- Configurable parameters via Config
- Center crop option to reduce edge noise

Usage:
    from core.flow_detector import OpticalFlowDetector
    from config import Config
    
    config = Config.load()
    detector = OpticalFlowDetector(config)
    
    segments = detector.detect("video.mp4")
    print(f"Found {len(segments)} segments")
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

from config.config_loader import Config, OpticalFlowConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FlowFeatures:
    """Optical flow features for a frame."""
    time: float
    avg_speed: float
    flow_std: float
    score: float


class OpticalFlowDetector:
    """
    Detect badminton rallies using optical flow analysis.
    
    The detection algorithm:
    1. Sample frames at configured FPS
    2. Calculate Farneback optical flow
    3. Extract flow features (speed, std, score)
    4. Apply threshold-based segment detection
    5. Merge nearby segments
    
    Example:
        >>> config = Config.load()
        >>> detector = OpticalFlowDetector(config)
        >>> segments = detector.detect("training_video.mp4")
        >>> print(segments)
        [(10.5, 42.0), (48.3, 75.8)]
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        flow_config: Optional[OpticalFlowConfig] = None
    ):
        """
        Initialize optical flow detector.
        
        Args:
            config: Full configuration object
            flow_config: Flow-specific configuration (overrides config)
        """
        if config is None:
            config = Config.load()
        
        self.config = config
        
        if flow_config is not None:
            self.flow_config = flow_config
        else:
            self.flow_config = config.optical_flow
        
        # Parameters from config
        self.sample_fps = self.flow_config.sample_fps
        self.scale_width = self.flow_config.scale_width
        self.scale_height = self.flow_config.scale_height
        self.threshold = self.flow_config.threshold
        self.min_duration = self.flow_config.min_duration
        self.merge_gap = self.flow_config.merge_gap
        self.center_crop = self.flow_config.center_crop
    
    def detect(
        self,
        video_path: Path,
        progress_callback: Optional[callable] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect rally segments using optical flow.
        
        Args:
            video_path: Path to input video
            progress_callback: Optional callback(current_percent, message)
            
        Returns:
            List of (start, end) tuples in seconds
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        logger.info(f"Detecting rallies (optical flow) in: {video_path.name}")
        logger.info(f"Parameters: sample_fps={self.sample_fps}, "
                   f"scale={self.scale_width}x{self.scale_height}, "
                   f"threshold={self.threshold}, "
                   f"center_crop={self.center_crop}")
        
        # Step 1: Calculate optical flow
        if progress_callback:
            progress_callback(10, "Calculating optical flow...")
        
        logger.info("Step 1: Calculating optical flow...")
        timeline, duration = self._detect_optical_flow(video_path)
        logger.info(f"  Flow samples: {len(timeline)}, duration: {duration:.1f}s")
        
        # Step 2: Build segments
        if progress_callback:
            progress_callback(60, "Building segments...")
        
        logger.info("Step 2: Building segments...")
        segments = self._build_segments(timeline)
        logger.info(f"  Raw segments: {len(segments)}")
        
        # Step 3: Merge segments
        if progress_callback:
            progress_callback(80, "Merging segments...")
        
        logger.info("Step 3: Merging segments...")
        segments = self._merge_segments(segments)
        logger.info(f"  Merged segments: {len(segments)}")
        
        if progress_callback:
            progress_callback(100, f"Detection complete: {len(segments)} segments")
        
        return segments
    
    def _detect_optical_flow(
        self,
        video_path: Path
    ) -> Tuple[List[FlowFeatures], float]:
        """
        Calculate optical flow for video frames.
        
        Uses Farneback dense optical flow algorithm.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (flow_timeline, duration)
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
            gray = cv2.resize(gray, (self.scale_width, self.scale_height))
            
            # Center crop (optional)
            if self.center_crop:
                h, w = gray.shape
                gray = gray[
                    int(h * 0.2):int(h * 0.8),
                    int(w * 0.2):int(w * 0.8)
                ]
            
            if prev_gray is not None and prev_gray.shape == gray.shape:
                # Calculate Farneback optical flow
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray,
                    gray,
                    None,
                    pyr_scale=0.5,
                    levels=3,
                    winsize=15,
                    iterations=3,
                    poly_n=5,
                    poly_sigma=1.2,
                    flags=0
                )
                
                # Extract features
                features = self._extract_flow_features(flow)
                
                t = frame_id / fps
                timeline.append(FlowFeatures(
                    time=t,
                    avg_speed=features['avg_speed'],
                    flow_std=features['flow_std'],
                    score=features['score']
                ))
            
            prev_gray = gray
            frame_id += 1
        
        cap.release()
        
        return timeline, duration
    
    def _extract_flow_features(self, flow: np.ndarray) -> Dict[str, float]:
        """
        Extract features from optical flow field.
        
        Args:
            flow: Optical flow field (H x W x 2)
            
        Returns:
            Dictionary with avg_speed, flow_std, score
        """
        # Extract dx, dy components
        dx = flow[:, :, 0]
        dy = flow[:, :, 1]
        
        # Calculate speed magnitude
        speed = np.sqrt(dx * dx + dy * dy)
        
        # Average speed
        avg_speed = float(np.mean(speed))
        
        # Speed standard deviation (complexity of motion patterns)
        flow_std = float(np.std(speed))
        
        # Combined score: emphasizes both speed and complexity
        score = avg_speed + 2 * flow_std
        
        return {
            'avg_speed': avg_speed,
            'flow_std': flow_std,
            'score': score
        }
    
    def _build_segments(
        self,
        timeline: List[FlowFeatures]
    ) -> List[Tuple[float, float]]:
        """
        Build segments using threshold-based detection.
        
        Args:
            timeline: Flow features timeline
            
        Returns:
            List of (start, end) tuples
        """
        segments = []
        start = None
        
        for features in timeline:
            if features.score > self.threshold:
                if start is None:
                    start = features.time
            else:
                if start is not None:
                    end = features.time
                    
                    if end - start >= self.min_duration:
                        segments.append((start, end))
                    
                    start = None
        
        # Handle open segment at end
        if start is not None:
            if timeline:
                end = timeline[-1].time
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
    
    def detect_with_analysis(
        self,
        video_path: Path,
        show_debug: bool = False
    ) -> Dict:
        """
        Detect with detailed analysis information.
        
        Args:
            video_path: Input video
            show_debug: Include per-frame debug data
            
        Returns:
            Analysis dictionary
        """
        segments = self.detect(video_path)
        
        # Calculate statistics
        timeline, duration = self._detect_optical_flow(video_path)
        
        scores = [f.score for f in timeline]
        
        analysis = {
            "video": str(video_path),
            "duration": duration,
            "segments": segments,
            "total_highlight_duration": sum(e - s for s, e in segments),
            "parameters": {
                "sample_fps": self.sample_fps,
                "threshold": self.threshold,
                "min_duration": self.min_duration,
                "merge_gap": self.merge_gap,
                "center_crop": self.center_crop
            },
            "statistics": {
                "min_score": min(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "mean_score": np.mean(scores) if scores else 0,
                "std_score": np.std(scores) if scores else 0
            }
        }
        
        analysis["highlight_percentage"] = (
            analysis["total_highlight_duration"] / duration * 100
            if duration > 0 else 0
        )
        
        if show_debug and timeline:
            analysis["timeline"] = [
                {
                    "time": f.time,
                    "avg_speed": f.avg_speed,
                    "flow_std": f.flow_std,
                    "score": f.score
                }
                for f in timeline
            ]
        
        return analysis
