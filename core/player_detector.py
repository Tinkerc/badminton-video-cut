"""
core/player_detector.py

Player trajectory detection for badminton rally highlights using YOLO.

This module refactors the logic from auto_cut_player.py into a reusable class
with configuration support.

Features:
- YOLOv8 person detection
- Player trajectory tracking
- Velocity-based motion analysis
- Configurable parameters via Config

Requirements:
    pip install ultralytics

Usage:
    from core import PlayerDetector
    from config import Config
    
    config = Config.load()
    detector = PlayerDetector(config)
    
    segments = detector.detect("video.mp4")
    print(f"Found {len(segments)} segments")
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

from config.config_loader import Config, PlayerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrajectoryPoint:
    """Player position at a point in time."""
    time: float
    x: float
    y: float
    bbox: Optional[Tuple[int, int, int, int]] = None


@dataclass
class FlowFeatures:
    """Motion features for a time window."""
    time: float
    distance: float
    velocity_std: float
    score: float


class PlayerDetector:
    """
    Detect badminton rallies using player trajectory analysis.
    
    The detection algorithm:
    1. Detect players using YOLOv8 person detection
    2. Track player position over time
    3. Calculate motion features (distance, velocity std)
    4. Apply adaptive threshold-based segment detection
    5. Merge nearby segments
    
    Requirements:
        pip install ultralytics
    
    Example:
        >>> config = Config.load()
        >>> detector = PlayerDetector(config)
        >>> segments = detector.detect("training_video.mp4")
        >>> print(segments)
        [(15.2, 48.5), (55.0, 82.3)]
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        player_config: Optional[PlayerConfig] = None,
        model_path: str = None
    ):
        """
        Initialize player detector.
        
        Args:
            config: Full configuration object
            player_config: Player-specific configuration (overrides config)
            model_path: YOLO model path (default: yolov8s.pt)
        """
        if config is None:
            config = Config.load()
        
        self.config = config
        
        if player_config is not None:
            self.player_config = player_config
        else:
            self.player_config = config.player
        
        # Parameters from config
        self.model_path = model_path or self.player_config.model
        self.sample_fps = self.player_config.sample_fps
        self.window_seconds = self.player_config.window_seconds
        self.threshold_ratio = self.player_config.threshold_ratio
        self.min_duration = self.player_config.min_duration
        self.merge_gap = self.player_config.merge_gap
        self.use_velocity_std = self.player_config.use_velocity_std
        self.confidence = self.player_config.confidence
        self.iou = self.player_config.iou
        
        self.model = None
    
    def _load_model(self):
        """Load YOLO model lazily."""
        if self.model is None:
            try:
                from ultralytics import YOLO
                logger.info(f"Loading YOLO model: {self.model_path}")
                self.model = YOLO(self.model_path)
                self.model.conf = self.confidence
                self.model.iou = self.iou
                logger.info("YOLO model loaded")
            except ImportError:
                raise ImportError(
                    "ultralytics not installed. Install with: pip install ultralytics"
                )
    
    def detect(
        self,
        video_path: Path,
        progress_callback: Optional[callable] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect rally segments using player trajectory.
        
        Args:
            video_path: Path to input video
            progress_callback: Optional callback(current_percent, message)
            
        Returns:
            List of (start, end) tuples in seconds
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        logger.info(f"Detecting rallies (player trajectory) in: {video_path.name}")
        logger.info(f"Parameters: sample_fps={self.sample_fps}, "
                   f"window={self.window_seconds}s, "
                   f"threshold_ratio={self.threshold_ratio}")
        
        # Load model
        if progress_callback:
            progress_callback(5, "Loading YOLO model...")
        
        self._load_model()
        
        # Step 1: Track player trajectory
        if progress_callback:
            progress_callback(10, "Tracking player trajectory...")
        
        logger.info("Step 1: Tracking player trajectory...")
        trajectory, frame_times, duration = self._track_trajectory(video_path)
        logger.info(f"  Trajectory points: {len(trajectory)}, "
                   f"duration: {duration:.1f}s")
        
        # Calculate detection rate
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        
        expected_points = int(duration * self.sample_fps)
        detection_rate = len(trajectory) / expected_points * 100 if expected_points > 0 else 0
        logger.info(f"  Detection rate: {detection_rate:.1f}%")
        
        # Check minimum trajectory length
        window_size = int(fps * self.window_seconds)
        if len(trajectory) < window_size:
            logger.warning("Not enough trajectory points for analysis")
            return []
        
        # Step 2: Analyze trajectory segments
        if progress_callback:
            progress_callback(60, "Analyzing trajectory segments...")
        
        logger.info("Step 2: Analyzing trajectory segments...")
        segments, scores, times, threshold = self._build_segments(
            trajectory, frame_times, fps
        )
        logger.info(f"  Raw segments: {len(segments)}, threshold: {threshold:.2f}")
        
        # Step 3: Merge segments
        if progress_callback:
            progress_callback(80, "Merging segments...")
        
        logger.info("Step 3: Merging segments...")
        segments = self._merge_segments(segments)
        logger.info(f"  Merged segments: {len(segments)}")
        
        if progress_callback:
            progress_callback(100, f"Detection complete: {len(segments)} segments")
        
        return segments
    
    def _detect_persons(self, frame) -> List[Tuple[int, int, int, int]]:
        """
        Detect persons in frame using YOLO.
        
        Args:
            frame: Video frame (BGR)
            
        Returns:
            List of (x1, y1, x2, y2) bounding boxes
        """
        results = self.model(frame, verbose=False, conf=self.confidence, iou=self.iou)
        
        persons = []
        for box in results[0].boxes:
            cls = int(box.cls[0])
            # COCO class 0 = person
            if cls == 0:
                x1, y1, x2, y2 = box.xyxy[0]
                persons.append((int(x1), int(y1), int(x2), int(y2)))
        
        return persons
    
    def _select_player(self, persons: List[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        """
        Select the main player from detected persons.
        
        Uses the largest bounding box (usually the on-court player).
        
        Args:
            persons: List of bounding boxes
            
        Returns:
            Selected player bounding box or None
        """
        if len(persons) == 0:
            return None
        
        # Select person with largest bbox area
        return max(persons, key=lambda p: (p[2] - p[0]) * (p[3] - p[1]))
    
    def _track_trajectory(
        self,
        video_path: Path
    ) -> Tuple[List[Tuple[float, float]], List[float], float]:
        """
        Track player trajectory through video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (trajectory, frame_times, duration)
        """
        cap = cv2.VideoCapture(str(video_path))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = total_frames / fps
        
        step = max(1, int(fps / self.sample_fps))
        
        trajectory = []
        frame_times = []
        frame_id = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            if frame_id % step != 0:
                frame_id += 1
                continue
            
            # Detect persons
            persons = self._detect_persons(frame)
            
            # Select main player
            player = self._select_player(persons)
            
            if player:
                x1, y1, x2, y2 = player
                
                # Calculate center position
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                
                trajectory.append((cx, cy))
                frame_times.append(frame_id / fps)
            
            frame_id += 1
        
        cap.release()
        
        return trajectory, frame_times, duration
    
    def _motion_score_distance(self, points: List[Tuple[float, float]]) -> float:
        """
        Calculate motion score based on total distance traveled.
        
        Args:
            points: List of (x, y) positions
            
        Returns:
            Total distance
        """
        if len(points) < 2:
            return 0
        
        dist = 0
        
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            dist += np.sqrt(dx * dx + dy * dy)
        
        return dist
    
    def _motion_score_velocity_std(self, points: List[Tuple[float, float]]) -> float:
        """
        Calculate motion score based on velocity standard deviation.
        
        Higher std = more varied movement (likely during rallies).
        
        Args:
            points: List of (x, y) positions
            
        Returns:
            Velocity standard deviation
        """
        if len(points) < 3:
            return 0
        
        velocities = []
        
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            v = np.sqrt(dx * dx + dy * dy)
            velocities.append(v)
        
        return float(np.std(velocities))
    
    def _build_segments(
        self,
        trajectory: List[Tuple[float, float]],
        frame_times: List[float],
        fps: float
    ) -> Tuple[List[Tuple[float, float]], List[float], List[float], float]:
        """
        Build segments from trajectory using sliding window analysis.
        
        Args:
            trajectory: Player positions
            frame_times: Time for each trajectory point
            fps: Video FPS
            
        Returns:
            Tuple of (segments, scores, times, threshold)
        """
        window_size = int(fps * self.window_seconds)
        
        if len(trajectory) < window_size:
            return [], [], [], 0
        
        scores = []
        times = []
        
        # Select scoring function
        score_func = (
            self._motion_score_velocity_std
            if self.use_velocity_std
            else self._motion_score_distance
        )
        
        # Sliding window analysis
        for i in range(window_size, len(trajectory)):
            window = trajectory[i - window_size:i]
            score = score_func(window)
            t = frame_times[i]
            
            scores.append(score)
            times.append(t)
        
        if len(scores) == 0:
            return [], [], [], 0
        
        # Adaptive threshold
        max_score = max(scores)
        threshold = max_score * self.threshold_ratio
        
        # Build segments
        segments = []
        start = None
        
        for t, score in zip(times, scores):
            if score > threshold:
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
            end = frame_times[-1]
            if end - start >= self.min_duration:
                segments.append((start, end))
        
        return segments, scores, times, threshold
    
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
        video_path: Path
    ) -> Dict[str, Any]:
        """
        Detect with detailed analysis information.
        
        Args:
            video_path: Input video
            
        Returns:
            Analysis dictionary with scores, statistics, etc.
        """
        segments = self.detect(video_path)
        
        # Get trajectory for statistics
        self._load_model()
        trajectory, frame_times, duration = self._track_trajectory(video_path)
        
        # Calculate scores
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        window_size = int(fps * self.window_seconds)
        scores = []
        
        score_func = (
            self._motion_score_velocity_std
            if self.use_velocity_std
            else self._motion_score_distance
        )
        
        for i in range(window_size, len(trajectory)):
            window = trajectory[i - window_size:i]
            scores.append(score_func(window))
        
        analysis = {
            "video": str(video_path),
            "duration": duration,
            "segments": segments,
            "total_highlight_duration": sum(e - s for s, e in segments),
            "trajectory_points": len(trajectory),
            "detection_rate": len(trajectory) / (duration * self.sample_fps) * 100 if duration > 0 else 0,
            "parameters": {
                "sample_fps": self.sample_fps,
                "window_seconds": self.window_seconds,
                "threshold_ratio": self.threshold_ratio,
                "min_duration": self.min_duration,
                "merge_gap": self.merge_gap,
                "use_velocity_std": self.use_velocity_std
            },
            "statistics": {
                "min_score": min(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "mean_score": np.mean(scores) if scores else 0,
                "std_score": np.std(scores) if scores else 0,
                "threshold": max(scores) * self.threshold_ratio if scores else 0
            }
        }
        
        analysis["highlight_percentage"] = (
            analysis["total_highlight_duration"] / duration * 100
            if duration > 0 else 0
        )
        
        return analysis
