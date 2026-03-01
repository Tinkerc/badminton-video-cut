"""
tests/test_audio_extractor.py

Unit tests for audio extraction module.
"""

import unittest
from pathlib import Path
import tempfile
import os

from core.audio_extractor import AudioExtractor, AudioStreamInfo, AudioExtractionError


class TestAudioExtractor(unittest.TestCase):
    """Test audio extractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = AudioExtractor()

    def test_init(self):
        """Test extractor initialization."""
        extractor = AudioExtractor()
        self.assertEqual(extractor.ffmpeg_path, "ffmpeg")
        self.assertEqual(extractor.ffprobe_path, "ffprobe")

    def test_init_custom_paths(self):
        """Test extractor with custom FFmpeg paths."""
        extractor = AudioExtractor(
            ffmpeg_path="/usr/bin/ffmpeg",
            ffprobe_path="/usr/bin/ffprobe"
        )
        self.assertEqual(extractor.ffmpeg_path, "/usr/bin/ffmpeg")
        self.assertEqual(extractor.ffprobe_path, "/usr/bin/ffprobe")

    def test_detect_audio_stream_nonexistent_file(self):
        """Test detecting audio stream in nonexistent file."""
        with self.assertRaises(FileNotFoundError):
            self.extractor.detect_audio_stream(Path("nonexistent.mp4"))

    def test_extract_audio_nonexistent_file(self):
        """Test extracting audio from nonexistent file."""
        with self.assertRaises(FileNotFoundError):
            self.extractor.extract_audio(Path("nonexistent.mp4"))

    def test_codec_mapping(self):
        """Test codec to extension mapping."""
        self.assertEqual(self.extractor._codec_to_ext("aac"), "aac")
        self.assertEqual(self.extractor._codec_to_ext("mp3"), "mp3")
        self.assertEqual(self.extractor._codec_to_ext("opus"), "opus")
        self.assertEqual(self.extractor._codec_to_ext("pcm_s16le"), "wav")
        self.assertEqual(self.extractor._codec_to_ext("unknown"), "wav")

    def test_get_codec_valid(self):
        """Test getting valid codec."""
        self.assertEqual(self.extractor._get_codec("wav"), "pcm_s16le")
        self.assertEqual(self.extractor._get_codec("mp3"), "libmp3lame")
        self.assertEqual(self.extractor._get_codec("aac"), "aac")

    def test_get_codec_invalid(self):
        """Test getting invalid codec."""
        with self.assertRaises(ValueError):
            self.extractor._get_codec("flac")

    def test_audio_stream_info_str(self):
        """Test AudioStreamInfo string representation."""
        info = AudioStreamInfo(
            codec_name="aac",
            sample_rate=48000,
            channels=2,
            bit_rate=128000
        )
        info_str = str(info)
        self.assertIn("aac", info_str)
        self.assertIn("48000", info_str)
        self.assertIn("2", info_str)


class TestAudioFormats(unittest.TestCase):
    """Test audio format handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = AudioExtractor()

    def test_supported_formats(self):
        """Test supported audio formats."""
        self.assertIn("wav", self.extractor.CODECS)
        self.assertIn("mp3", self.extractor.CODECS)
        self.assertIn("aac", self.extractor.CODECS)


if __name__ == "__main__":
    unittest.main()
