"""
config/config_loader.py

Configuration loading and management for badminton video cut.

Features:
- Load default configuration from YAML
- Merge with user configuration
- Environment variable overrides
- Type-safe access to configuration values

Usage:
    from config import Config
    
    # Load default configuration
    config = Config.load()
    
    # Load with user config override
    config = Config.load("my_config.yaml")
    
    # Access configuration values
    print(config.motion.threshold)
    print(config.export.crf)
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeneralConfig:
    """General settings."""
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    log_level: str = "INFO"


@dataclass
class AudioConfig:
    """Audio extraction settings."""
    default_format: str = "wav"
    sample_rate: int = 16000
    channels: int = 1
    use_copy: bool = True
    audio_bitrate: str = "192k"


@dataclass
class MotionConfig:
    """Motion + audio detection settings."""
    sample_fps: int = 2
    threshold: float = 8.0
    audio_threshold: float = 0.04
    min_duration: float = 3.0
    merge_gap: float = 4.0


@dataclass
class OpticalFlowConfig:
    """Optical flow detection settings."""
    sample_fps: int = 3
    scale_width: int = 320
    scale_height: int = 180
    threshold: float = 2.0
    min_duration: float = 4.0
    merge_gap: float = 4.0
    center_crop: bool = True


@dataclass
class PlayerConfig:
    """Player detection settings."""
    model: str = "yolov8s.pt"
    sample_fps: int = 3
    window_seconds: float = 1.5
    threshold_ratio: float = 0.4
    use_velocity_std: bool = True
    confidence: float = 0.5
    iou: float = 0.7


@dataclass
class ExportConfig:
    """Video export settings."""
    codec: str = "libx264"
    preset: str = "veryfast"
    crf: int = 18
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    use_gpu: bool = False
    faststart: bool = True


@dataclass
class BatchConfig:
    """Batch processing settings."""
    max_workers: int = 4
    video_patterns: List[str] = field(default_factory=lambda: [".mp4", ".webm", ".mkv", ".avi", ".mov"])


@dataclass
class Config:
    """
    Main configuration class.
    
    Loads and merges configuration from:
    1. Default configuration (config/default_config.yaml)
    2. User configuration (~/.badminton-cut/config.yaml)
    3. Project configuration (./config.yaml)
    4. Environment variables (optional)
    
    Example:
        >>> config = Config.load()
        >>> print(config.motion.threshold)
        8.0
        
        >>> config = Config.load("my_config.yaml")
        >>> print(config.export.crf)
        18
    """
    general: GeneralConfig = field(default_factory=GeneralConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    optical_flow: OpticalFlowConfig = field(default_factory=OpticalFlowConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from files.
        
        Priority (highest to lowest):
        1. Explicit config_path parameter
        2. Project config (./config.yaml)
        3. User config (~/.badminton-cut/config.yaml)
        4. Default config (config/default_config.yaml)
        
        Args:
            config_path: Optional explicit config file path
            
        Returns:
            Config object with merged settings
        """
        # Start with defaults
        config_dict = cls._load_default_config()
        
        # Merge user config (~/.badminton-cut/config.yaml)
        user_config_path = Path.home() / ".badminton-cut" / "config.yaml"
        if user_config_path.exists():
            logger.debug(f"Loading user config: {user_config_path}")
            user_config = cls._load_yaml(user_config_path)
            config_dict = cls._merge_dicts(config_dict, user_config)
        
        # Merge project config (./config.yaml)
        project_config_path = Path.cwd() / "config.yaml"
        if project_config_path.exists():
            logger.debug(f"Loading project config: {project_config_path}")
            project_config = cls._load_yaml(project_config_path)
            config_dict = cls._merge_dicts(config_dict, project_config)
        
        # Merge explicit config path (highest priority)
        if config_path is not None:
            config_path = Path(config_path)
            if config_path.exists():
                logger.debug(f"Loading explicit config: {config_path}")
                explicit_config = cls._load_yaml(config_path)
                config_dict = cls._merge_dicts(config_dict, explicit_config)
            else:
                logger.warning(f"Config file not found: {config_path}")
        
        # Apply environment variable overrides (optional)
        config_dict = cls._apply_env_overrides(config_dict)
        
        return cls._from_dict(config_dict)
    
    @classmethod
    def _load_default_config(cls) -> Dict:
        """Load default configuration from package."""
        default_path = Path(__file__).parent / "default_config.yaml"
        
        if not default_path.exists():
            logger.warning("Default config not found, using hardcoded defaults")
            return {}
        
        return cls._load_yaml(default_path)
    
    @classmethod
    def _load_yaml(cls, path: Path) -> Dict:
        """Load YAML file safely."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return {}
    
    @classmethod
    def _merge_dicts(cls, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        
        override takes precedence over base.
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._merge_dicts(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def _apply_env_overrides(cls, config_dict: Dict) -> Dict:
        """
        Apply environment variable overrides.
        
        Format: BADMINTON_CUT_<SECTION>_<KEY>=value
        Example: BADMINTON_CUT_MOTION_THRESHOLD=10
        """
        env_prefix = "BADMINTON_CUT_"
        
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(env_prefix):
                continue
            
            # Parse env key: BADMINTON_CUT_MOTION_THRESHOLD -> motion.threshold
            parts = env_key[len(env_prefix):].lower().split("_", 1)
            
            if len(parts) != 2:
                continue
            
            section, key = parts
            
            if section in config_dict and isinstance(config_dict[section], dict):
                # Convert value to appropriate type
                config_dict[section][key] = cls._convert_value(env_value)
                logger.debug(f"Env override: {section}.{key} = {env_value}")
        
        return config_dict
    
    @classmethod
    def _convert_value(cls, value: str) -> Any:
        """Convert string value to appropriate Python type."""
        # Boolean
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False
        
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        
        # String (default)
        return value
    
    @classmethod
    def _from_dict(cls, config_dict: Dict) -> "Config":
        """Create Config object from dictionary."""
        return cls(
            general=GeneralConfig(**config_dict.get("general", {})),
            audio=AudioConfig(**config_dict.get("audio", {})),
            motion=MotionConfig(**config_dict.get("motion", {})),
            optical_flow=OpticalFlowConfig(**config_dict.get("optical_flow", {})),
            player=PlayerConfig(**config_dict.get("player", {})),
            export=ExportConfig(**config_dict.get("export", {})),
            batch=BatchConfig(**config_dict.get("batch", {}))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "general": {
                "ffmpeg_path": self.general.ffmpeg_path,
                "ffprobe_path": self.general.ffprobe_path,
                "log_level": self.general.log_level
            },
            "audio": {
                "default_format": self.audio.default_format,
                "sample_rate": self.audio.sample_rate,
                "channels": self.audio.channels,
                "use_copy": self.audio.use_copy,
                "audio_bitrate": self.audio.audio_bitrate
            },
            "motion": {
                "sample_fps": self.motion.sample_fps,
                "threshold": self.motion.threshold,
                "audio_threshold": self.motion.audio_threshold,
                "min_duration": self.motion.min_duration,
                "merge_gap": self.motion.merge_gap
            },
            "optical_flow": {
                "sample_fps": self.optical_flow.sample_fps,
                "scale_width": self.optical_flow.scale_width,
                "scale_height": self.optical_flow.scale_height,
                "threshold": self.optical_flow.threshold,
                "min_duration": self.optical_flow.min_duration,
                "merge_gap": self.optical_flow.merge_gap,
                "center_crop": self.optical_flow.center_crop
            },
            "player": {
                "model": self.player.model,
                "sample_fps": self.player.sample_fps,
                "window_seconds": self.player.window_seconds,
                "threshold_ratio": self.player.threshold_ratio,
                "use_velocity_std": self.player.use_velocity_std,
                "confidence": self.player.confidence,
                "iou": self.player.iou
            },
            "export": {
                "codec": self.export.codec,
                "preset": self.export.preset,
                "crf": self.export.crf,
                "audio_codec": self.export.audio_codec,
                "audio_bitrate": self.export.audio_bitrate,
                "use_gpu": self.export.use_gpu,
                "faststart": self.export.faststart
            },
            "batch": {
                "max_workers": self.batch.max_workers,
                "video_patterns": self.batch.video_patterns
            }
        }
    
    def save(self, path: Path):
        """Save configuration to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Configuration saved to: {path}")
    
    def __str__(self) -> str:
        """String representation."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


# Convenience function
def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration.
    
    Args:
        config_path: Optional config file path
        
    Returns:
        Config object
    """
    return Config.load(config_path)
