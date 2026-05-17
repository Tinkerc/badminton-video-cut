# tests/test_mark_rallies.py
"""Tests for mark_rallies helper functions — built incrementally per phase."""
from mark_rallies import _format_duration, _build_export_cmd


class TestFormatDuration:
    def test_seconds_only(self):
        assert _format_duration(5.3) == "5.3s"

    def test_zero(self):
        assert _format_duration(0) == "0.0s"

    def test_exact_minute(self):
        assert _format_duration(60) == "1m 00s"

    def test_minutes_and_seconds(self):
        assert _format_duration(125) == "2m 05s"

    def test_hours(self):
        assert _format_duration(3661) == "1h 1m 01s"

    def test_round_minutes(self):
        assert _format_duration(120) == "2m 00s"


class TestBuildExportCmd:
    def test_basic_two_segments(self):
        segments = [(10.0, 20.0), (30.0, 45.0)]
        cmd = _build_export_cmd("input.mp4", segments, "output.mp4")
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "input.mp4" in cmd
        assert "output.mp4" in cmd
        assert "-filter_complex" in cmd
        assert any("concat=n=2" in part for part in cmd)

    def test_single_segment(self):
        segments = [(5.0, 10.0)]
        cmd = _build_export_cmd("vid.mov", segments, "out.mp4")
        assert any("concat=n=1" in part for part in cmd)

    def test_custom_quality(self):
        segments = [(1.0, 2.0)]
        cmd = _build_export_cmd("in.mp4", segments, "out.mp4", crf=22, preset="fast")
        assert "22" in cmd
        assert "fast" in cmd

    def test_trim_precision(self):
        segments = [(1.234, 5.678)]
        cmd = _build_export_cmd("in.mp4", segments, "out.mp4")
        filter_idx = cmd.index("-filter_complex")
        fc = cmd[filter_idx + 1]
        assert "start=1.234" in fc
        assert "end=5.678" in fc


import os
import tempfile
from mark_rallies import _parse_session_info


class TestParseSessionInfo:
    def _write_session(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_basic_session(self):
        path = self._write_session("# VIDEO: /tmp/test.mp4\n10.0 20.0\n30.0 40.0\n")
        info = _parse_session_info(path)
        assert info["seg_count"] == 2
        assert info["highlight_duration"] == 20.0
        assert info["video_path"] == "/tmp/test.mp4"
        os.unlink(path)

    def test_skips_comments_and_blanks(self):
        path = self._write_session("# VIDEO: /tmp/test.mp4\n# comment\n\n10.0 20.0\n\n")
        info = _parse_session_info(path)
        assert info["seg_count"] == 1
        os.unlink(path)

    def test_empty_session(self):
        path = self._write_session("# VIDEO: /tmp/test.mp4\n")
        info = _parse_session_info(path)
        assert info["seg_count"] == 0
        assert info["highlight_duration"] == 0.0
        os.unlink(path)

    def test_no_video_header(self):
        path = self._write_session("10.0 20.0\n")
        info = _parse_session_info(path)
        assert info["video_path"] == ""
        assert info["video_exists"] is False
        os.unlink(path)

    def test_count_bug_fix(self):
        """The old _list_sessions counted # VIDEO: lines as segments."""
        path = self._write_session("# VIDEO: /tmp/test.mp4\n10.0 20.0\n")
        info = _parse_session_info(path)
        assert info["seg_count"] == 1  # NOT 2
        os.unlink(path)


from mark_rallies import _apply_padding


class TestApplyPadding:
    def test_no_padding(self):
        segs = [(10.0, 20.0), (30.0, 40.0)]
        assert _apply_padding(segs, 0, 0) == segs

    def test_basic_padding(self):
        segs = [(10.0, 20.0)]
        result = _apply_padding(segs, 0.8, 1.2)
        assert result == [(9.2, 21.2)]

    def test_clamp_to_zero(self):
        segs = [(0.5, 5.0)]
        result = _apply_padding(segs, 0.8, 1.2)
        assert result[0][0] == 0.0

    def test_merge_overlap(self):
        segs = [(10.0, 15.0), (14.0, 20.0)]
        result = _apply_padding(segs, 1.0, 1.0)
        assert len(result) == 1
        assert result[0] == (9.0, 21.0)

    def test_no_merge_when_separate(self):
        segs = [(10.0, 15.0), (30.0, 40.0)]
        result = _apply_padding(segs, 0.5, 0.5)
        assert len(result) == 2

    def test_empty_segments(self):
        assert _apply_padding([], 0.8, 1.2) == []

    def test_three_merge(self):
        segs = [(10.0, 12.0), (11.5, 14.0), (13.5, 16.0)]
        result = _apply_padding(segs, 0.5, 0.5)
        assert len(result) == 1
        assert result[0] == (9.5, 16.5)
