"""
tests/test_config.py

Unit tests for configuration loading.
"""

import unittest
from pathlib import Path
import tempfile
import os

from config import Config
from config.config_loader import (
    GeneralConfig,
    AudioConfig,
    MotionConfig,
    OpticalFlowConfig,
    PlayerConfig,
    ExportConfig,
    BatchConfig
)


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        config = Config.load()

        # Check default values
        self.assertEqual(config.general.ffmpeg_path, "ffmpeg")
        self.assertEqual(config.motion.sample_fps, 2)
        self.assertEqual(config.motion.threshold, 8)
        self.assertEqual(config.export.crf, 18)
        self.assertEqual(config.export.preset, "veryfast")

    def test_load_custom_config(self):
        """Test loading custom configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
motion:
  sample_fps: 5
  threshold: 10

export:
  crf: 23
  preset: ultrafast
""")
            temp_path = f.name

        try:
            config = Config.load(Path(temp_path))

            # Custom values should override defaults
            self.assertEqual(config.motion.sample_fps, 5)
            self.assertEqual(config.motion.threshold, 10)
            self.assertEqual(config.export.crf, 23)
            self.assertEqual(config.export.preset, "ultrafast")

            # Other values should remain default
            self.assertEqual(config.motion.audio_threshold, 0.04)
        finally:
            os.unlink(temp_path)

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = Config.load()
        config_dict = config.to_dict()

        self.assertIsInstance(config_dict, dict)
        self.assertIn("motion", config_dict)
        self.assertIn("export", config_dict)
        self.assertEqual(config_dict["motion"]["sample_fps"], 2)
        self.assertEqual(config_dict["export"]["crf"], 18)

    def test_config_save_and_load(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "config.yaml"

            # Save config
            config = Config.load()
            config.save(temp_path)

            # Load it back
            loaded_config = Config.load(temp_path)

            # Should be identical
            self.assertEqual(
                config.to_dict(),
                loaded_config.to_dict()
            )


class TestConfigDataclasses(unittest.TestCase):
    """Test configuration dataclasses."""

    def test_motion_config_defaults(self):
        """Test MotionConfig default values."""
        motion = MotionConfig()

        self.assertEqual(motion.sample_fps, 2)
        self.assertEqual(motion.threshold, 8)
        self.assertEqual(motion.audio_threshold, 0.04)
        self.assertEqual(motion.min_duration, 3)
        self.assertEqual(motion.merge_gap, 4)

    def test_export_config_defaults(self):
        """Test ExportConfig default values."""
        export = ExportConfig()

        self.assertEqual(export.codec, "libx264")
        self.assertEqual(export.preset, "veryfast")
        self.assertEqual(export.crf, 18)
        self.assertEqual(export.audio_codec, "aac")

    def test_player_config_defaults(self):
        """Test PlayerConfig default values."""
        player = PlayerConfig()

        self.assertEqual(player.model, "yolov8s.pt")
        self.assertEqual(player.sample_fps, 3)
        self.assertEqual(player.window_seconds, 1.5)
        self.assertEqual(player.threshold_ratio, 0.4)


class TestConfigMerge(unittest.TestCase):
    """Test configuration merging."""

    def test_merge_dicts(self):
        """Test deep merging of dictionaries."""
        base = {
            "motion": {"sample_fps": 2, "threshold": 8},
            "export": {"crf": 18}
        }

        override = {
            "motion": {"threshold": 10}
        }

        result = Config._merge_dicts(base, override)

        # Override should update threshold
        self.assertEqual(result["motion"]["threshold"], 10)
        # Base values should remain
        self.assertEqual(result["motion"]["sample_fps"], 2)
        self.assertEqual(result["export"]["crf"], 18)


if __name__ == "__main__":
    unittest.main()
