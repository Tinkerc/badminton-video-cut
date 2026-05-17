# Manual-first Video Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge export into `mark_rallies.py` so users complete mark → review → export in one tool, no script switching.

**Architecture:** Add export/session/padding helpers as module-level functions in `mark_rallies.py`. Reuse FFmpeg `filter_complex` approach from `export_segments.py`. No new dependencies. Pure functions extracted for testability. Test file built incrementally — each phase appends its own test class, no forward imports of unimplemented functions.

**Tech Stack:** Python 3, OpenCV, FFmpeg (subprocess), pytest

**Spec:** `docs/plan/manual-first-video-cut-workflow.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `mark_rallies.py` | Modify | Add export helpers, fix session listing, fix LIST input model, add review keys, add padding |
| `tests/test_mark_rallies.py` | Create (incremental) | Test pure helper functions — built phase by phase |
| `export_segments.py` | No change | Keep as backward-compatible entry point |

---

## Phase 1: Export Merge (minimum viable)

### Task 1: Add `_format_duration()` and `_build_export_cmd()` + tests

**Files:**
- Create: `tests/test_mark_rallies.py` (Phase 1 tests only)
- Modify: `mark_rallies.py` (add `import subprocess`, add two functions)

- [ ] **Step 1: Add `import subprocess` to `mark_rallies.py`**

At line 46, add to the import block:

```python
import cv2
import sys
import os
import subprocess
import time
from typing import List, Tuple
```

- [ ] **Step 2: Add `_format_duration()` and `_build_export_cmd()` after constants**

Insert after `MIN_SEGMENT_SECONDS = 2.0` (line 57):

```python
def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}h {m}m {s:02d}s"
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s:02d}s"
    return f"{seconds:.1f}s"


def _build_export_cmd(video_path: str, segments: List[Tuple[float, float]],
                      output_path: str, crf: int = 18, preset: str = "veryfast") -> list:
    """Build FFmpeg filter_complex command for segment export."""
    video_filters = []
    audio_filters = []
    for i, (start, end) in enumerate(segments):
        video_filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
        audio_filters.append(
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_labels = "".join([f"[v{i}][a{i}]" for i in range(len(segments))])
    filter_complex = (
        ";".join(video_filters + audio_filters) +
        f";{concat_labels}concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )
    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]
```

- [ ] **Step 3: Create `tests/test_mark_rallies.py` with Phase 1 tests only**

No forward imports — only test what exists now:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_mark_rallies.py -v
```

Expected: All 10 tests pass.


### Task 2: Add `_export_segments()` with robust error handling

**Files:**
- Modify: `mark_rallies.py` (add function after `_build_export_cmd`)

- [ ] **Step 1: Add `_export_segments()`**

Insert after `_build_export_cmd()`:

```python
def _export_segments(video_path: str, segments: List[Tuple[float, float]],
                     output_path: str, crf: int = 18, preset: str = "veryfast") -> bool:
    """Export segments to video file using FFmpeg filter_complex.
    Returns True on success, False on failure."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    print(f"\nExporting {len(segments)} segments...")
    cmd = _build_export_cmd(video_path, segments, output_path, crf, preset)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nExport failed (exit code {result.returncode})")
        stderr_preview = result.stderr[-500:] if result.stderr else "(no stderr)"
        print(f"FFmpeg error: {stderr_preview}")
        print("Session file preserved. Retry with: python export_segments.py")
        return False
    if not os.path.exists(output_path):
        print("\nExport failed: output file not created.")
        print("Session file preserved. Retry with: python export_segments.py")
        return False
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nExport complete: {output_path} ({size_mb:.1f} MB)")
    return True
```

- [ ] **Step 2: Verify function is importable**

```bash
python -c "from mark_rallies import _export_segments; print('OK')"
```


### Task 3: Wire export into `main()` exit path

**Files:**
- Modify: `mark_rallies.py` (replace lines 786-803)

- [ ] **Step 1: Replace main() exit section**

Replace from `# Cleanup` (line 786) to end of `main()`:

```python
    # Cleanup
    player.release()
    cv2.destroyAllWindows()

    segments = recorder.get_segments()
    print(f"\nRecorded {len(segments)} segments")

    if segments:
        total_duration = sum(e - s for s, e in segments)
        print(f"Total highlight duration: {_format_duration(total_duration)}")
        print(f"Original duration: {_format_duration(player.duration)}")
        if player.duration > 0:
            reduction = (1 - total_duration / player.duration) * 100
            print(f"Reduction: {reduction:.1f}%")
        print()
        print(f"Segments saved to: {recorder._segments_file()}")
        print(f"Output video: {output_path}")
        print()
        confirm = input("Export now? [Y/n] ").strip().lower()
        if confirm != 'n':
            _export_segments(video_path, segments, output_path)
    else:
        print("No segments recorded.")
```

- [ ] **Step 2: Manual test — Phase 1**

```bash
python mark_rallies.py
# → Select session with segments → BROWSE mode → press Q
# → Should show stats with formatted duration + "Export now? [Y/n]"
# → Press Y → should create output file
# → Press N → should exit cleanly, session preserved
# → Verify: no segments case (start fresh, Q immediately) → no export prompt
```

---

## Phase 2: Session Management + Standalone Export

### Task 4: Add `_parse_session_info()` + tests (fixes segment count bug)

**Files:**
- Modify: `mark_rallies.py` (add function, replace `_list_sessions()`)
- Modify: `tests/test_mark_rallies.py` (append TestParseSessionInfo)

- [ ] **Step 1: Append session parsing tests to test file**

Add to end of `tests/test_mark_rallies.py`:

```python
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
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
python -m pytest tests/test_mark_rallies.py::TestParseSessionInfo -v
```

Expected: ImportError.

- [ ] **Step 3: Add `_parse_session_info()` and `_load_session_segments()` to `mark_rallies.py`**

Insert after `_build_export_cmd()`:

```python
def _parse_session_info(fpath: str) -> dict:
    """Parse session file for metadata.
    Returns dict: name, fpath, seg_count, highlight_duration, video_path, video_exists."""
    name = os.path.splitext(os.path.basename(fpath))[0]
    segments, video_path = _load_session_segments(fpath)
    highlight = sum(e - s for s, e in segments)
    return {
        "name": name,
        "fpath": fpath,
        "seg_count": len(segments),
        "highlight_duration": highlight,
        "video_path": video_path,
        "video_exists": bool(video_path) and os.path.exists(video_path),
    }


def _load_session_segments(fpath: str) -> Tuple[List[Tuple[float, float]], str]:
    """Load segments and video path from session file."""
    segments = []
    video_path = ""
    with open(fpath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# VIDEO:"):
                video_path = line[len("# VIDEO:"):].strip()
                continue
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) == 2:
                segments.append((float(parts[0]), float(parts[1])))
    return sorted(segments), video_path
```

- [ ] **Step 4: Replace `_list_sessions()` to use `_parse_session_info()`**

Replace the entire `_list_sessions()` function (lines 400-416):

```python
def _list_sessions(session_dir: str = "sessions") -> List[dict]:
    """List existing sessions with metadata. Returns list of info dicts."""
    if not os.path.exists(session_dir):
        return []
    results = []
    for f in sorted(os.listdir(session_dir)):
        if f.endswith(".txt"):
            fpath = os.path.join(session_dir, f)
            info = _parse_session_info(fpath)
            if info["seg_count"] > 0:
                results.append(info)
    return results
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/test_mark_rallies.py -v
```

Expected: All 16 tests pass.


### Task 5: Redesign startup menu + add standalone export

**Files:**
- Modify: `mark_rallies.py` (rewrite `_select_session()`, add `_export_session_standalone()`)

- [ ] **Step 1: Add `_export_session_standalone()` before `_select_session()`**

```python
def _export_session_standalone(sessions: list):
    """Export a session without entering the video player."""
    print("\nWhich session to export?")
    for i, s in enumerate(sessions):
        print(f"  {i+1}. [{s['seg_count']} segments] {s['name']}")
    choice = input("\nSelect [1]: ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
    except ValueError:
        idx = 0

    if not (0 <= idx < len(sessions)):
        print("Invalid selection.")
        return

    s = sessions[idx]
    if not s["video_exists"]:
        print(f"Video not found: {s.get('video_path', 'N/A')}")
        new_path = input("Enter video path: ").strip()
        if new_path and os.path.exists(new_path):
            video_path = os.path.abspath(new_path)
        else:
            print("File not found.")
            return
    else:
        video_path = s["video_path"]

    segments, _ = _load_session_segments(s["fpath"])
    if not segments:
        print("No segments to export.")
        return

    base_name = s["name"]
    output_dir = "./output"
    seq = _find_next_output_index(output_dir, base_name)
    output_path = os.path.join(output_dir, f"{base_name}_{seq}.mp4")

    print(f"\nVideo:    {video_path}")
    print(f"Segments: {len(segments)} ({_format_duration(sum(e - s for s, e in segments))})")
    print(f"Output:   {output_path}")

    confirm = input("\nExport? [Y/n] ").strip().lower()
    if confirm != 'n':
        _export_segments(video_path, segments, output_path)
```

- [ ] **Step 2: Replace `_select_session()` with enriched menu**

```python
def _select_session():
    """Show session list and let user pick existing or create new."""
    sessions = _list_sessions()

    print("=" * 60)
    print("Badminton Video Cut")
    print("=" * 60)

    if sessions:
        print()
        for i, s in enumerate(sessions):
            dur = _format_duration(s["highlight_duration"])
            status = "video found" if s["video_exists"] else "video missing"
            print(f"  {i+1}. [{s['seg_count']} segments] {s['name']}  highlight {dur}  {status}")

        print(f"\n  N - New video")
        print("  E - Export existing session")
        print("  Q - Quit")
        choice = input("\nSelect [1]: ").strip()

        if choice.upper() == 'Q':
            sys.exit(0)

        if choice.upper() == 'N':
            return _new_session()

        if choice.upper() == 'E':
            _export_session_standalone(sessions)
            sys.exit(0)

        try:
            idx = int(choice) - 1 if choice else 0
        except ValueError:
            idx = 0

        if 0 <= idx < len(sessions):
            s = sessions[idx]
            if s["video_exists"]:
                print(f"\nResuming: {s['name']} ({s['seg_count']} segments)")
                return s["video_path"]
            elif s["video_path"]:
                print(f"Video not found: {s['video_path']}")
                new_path = input("Enter correct video path: ").strip()
                if new_path and os.path.exists(new_path):
                    return os.path.abspath(new_path)
                print("File not found. Exiting.")
                sys.exit(1)
            else:
                print("No video path in session file.")
                new_path = input("Enter video path: ").strip()
                if new_path and os.path.exists(new_path):
                    return os.path.abspath(new_path)
                print("File not found. Exiting.")
                sys.exit(1)

        print("Invalid choice, exiting.")
        sys.exit(1)
    else:
        print("\nNo sessions found.")
        return _new_session()
```

- [ ] **Step 3: Manual test — startup menu**

```bash
python mark_rallies.py
# → Rich session list with durations and video status
# → N: new session prompt
# → E: export session sub-menu
# → Q: quit
# → Number: resume session (handles missing video with re-bind prompt)
```


## Phase 3: Fix LIST Input Model + Review Enhancements + Padding

### Task 6: Fix LIST mode — always create window, display frame with overlay

**Context:** Current LIST mode uses `cv2.waitKey(100)` without an OpenCV window (line 549 skips `cv2.namedWindow` for LIST). Without a window, key events are unreliable on macOS. The fix: always create the window and show the selected segment's frame in LIST mode.

**Files:**
- Modify: `mark_rallies.py` (startup window logic + LIST mode main loop)

- [ ] **Step 1: Always create the window**

Replace the conditional window creation (lines 549-551):

```python
    # Create window — always needed for key input (even LIST mode)
    window_name = "Phase-H Rally Marker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
```

- [ ] **Step 2: Replace LIST mode loop to display frames**

Replace the LIST mode block (lines 556-600). The new version reads the frame at the selected segment's start time and displays the overlay, making key input reliable:

```python
        if mode == "LIST":
            # LIST mode: show selected segment's frame with overlay, read keys
            segments = recorder.get_segments()
            if segments:
                seg = recorder.get_at_index(selected_index)
                if seg:
                    target_frame = int(seg[0] * player.fps)
                    player.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    player.current_frame = target_frame
                    ret, frame = player.cap.read()
                    if ret:
                        frame = draw_overlay(frame, player, recorder, mode, selected_index, preview_seg)
                        cv2.imshow(window_name, frame)

            key = cv2.waitKey(100) & 0xFF
            if key == 255:
                continue
            last_key_time = time.time()
            action = KeyboardController.get_action(key)

            if action == 'quit':
                print("Exiting...")
                recorder.finalize(player.get_current_time())
                break

            if action == 'toggle_list':  # R = back to browse
                mode = "BROWSE"
                paused = False
                print("Back to BROWSE mode")
                continue

            if not segments:
                continue

            # Navigation
            if action in ('up', 'back'):  # Up or Backspace — previous
                selected_index = max(0, selected_index - 1)
            elif action in ('down', 'confirm'):  # Down or Enter — next
                selected_index = min(len(segments) - 1, selected_index + 1)
            elif action == 'toggle':  # Space = preview selected
                seg = recorder.get_at_index(selected_index)
                if seg:
                    preview_seg = seg
                    player.jump_seconds(seg[0] - 1)
                    print(f"[Preview] Segment #{selected_index+1}: {seg[0]:.1f}s - {seg[1]:.1f}s")
                    mode = "PREVIEW"
                else:
                    print("No segments to preview.")
            elif action == 'undo':  # U = delete selected
                removed = recorder.delete_at_index(selected_index)
                if removed:
                    print(f"DELETED: {removed[0]:.1f}s - {removed[1]:.1f}s")
                    recorder._auto_save()
                    selected_index = min(selected_index, max(0, len(recorder.get_segments()) - 1))
                else:
                    print("No segments to delete.")
            elif action == 'export':  # E = export from list mode
                recorder._auto_save()
                segs = recorder.get_segments()
                if segs:
                    total_dur = sum(e - s for s, e in segs)
                    print(f"\n{len(segs)} segments, {_format_duration(total_dur)}")
                    confirm = input("Export? [Y/n] ").strip().lower()
                    if confirm != 'n':
                        _export_segments(video_path, segs, output_path)
            elif action == 'save':  # S = explicit save
                recorder._auto_save()
                print(f"Saved {recorder.get_count()} segments")
            continue
```

- [ ] **Step 3: Add new key mappings to `KeyboardController.KEY_MAP`**

Add to KEY_MAP dict (before the closing brace):

```python
        # Review navigation
        13: 'confirm',           # Enter — next segment
        8: 'back',               # Backspace (macOS)
        127: 'back',             # Backspace (alternate)

        # Export / Save from list mode
        ord('e'): 'export',
        ord('E'): 'export',
        ord('s'): 'save',
        ord('S'): 'save',
```

- [ ] **Step 4: Update `draw_overlay()` LIST mode hint text**

Replace the LIST mode overlay text (around line 298):

```python
        cv2.putText(frame, "LIST: Enter/Up/Down | Space=preview | E=export | S=save | U=delete",
                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
```

Note: reduced font size from 0.7 to 0.5 to fit the longer text.

- [ ] **Step 5: Update `print_help()` to reflect new review keys**

Add after the existing controls section:

```python
    print("  Review mode (LIST):")
    print("    Enter     - Next segment")
    print("    Backspace - Previous segment")
    print("    E         - Export")
    print("    S         - Save")
    print()
```

- [ ] **Step 6: Manual test — LIST mode with window**

```bash
python mark_rallies.py
# → Select session with segments → choose LIST mode at startup
# → Window should open showing first segment's frame with overlay
# → Enter/Down: next segment (frame updates)
# → Backspace/Up: previous segment
# → Space: preview with auto-advance
# → E: export prompt
# → S: save confirmation
# → U: delete, auto-select next
# → R: back to BROWSE mode (window stays, playback resumes)
```


### Task 7: Add auto-advance after preview ends

**Files:**
- Modify: `mark_rallies.py` (PREVIEW mode auto-end logic)

- [ ] **Step 1: Replace PREVIEW auto-end with auto-advance**

Find the PREVIEW auto-end block (inside the `if key == 255:` section, around the original line 654-659):

```python
            if mode == "PREVIEW" and preview_seg:
                if player.get_current_time() >= preview_seg[1]:
                    next_idx = selected_index + 1
                    if next_idx < recorder.get_count():
                        selected_index = next_idx
                        seg = recorder.get_at_index(selected_index)
                        preview_seg = seg
                        player.jump_seconds(seg[0] - 1)
                        print(f"[Preview -> #{selected_index+1}] {seg[0]:.1f}s - {seg[1]:.1f}s")
                    else:
                        print("[Review complete - last segment]")
                        mode = "LIST"
                    recorder._auto_save()
                    continue
```

Also update the video-ended-during-preview case (in the `if not ret:` block for PREVIEW mode):

```python
            if mode == "PREVIEW":
                next_idx = selected_index + 1
                if next_idx < recorder.get_count():
                    selected_index = next_idx
                    seg = recorder.get_at_index(selected_index)
                    preview_seg = seg
                    player.jump_seconds(seg[0] - 1)
                    print(f"[Preview -> #{selected_index+1}] {seg[0]:.1f}s - {seg[1]:.1f}s")
                else:
                    print("[Review complete - last segment]")
                    mode = "LIST"
                recorder._auto_save()
                continue
```

- [ ] **Step 2: Manual test — auto-advance**

```bash
python mark_rallies.py
# → Resume session → LIST mode → Space on first segment
# → Preview plays, auto-advances to next segment when done
# → Continues until last segment, then returns to LIST mode
```


### Task 8: Add `_apply_padding()` + tests + integrate into export

**Files:**
- Modify: `mark_rallies.py` (add function after `_build_export_cmd`)
- Modify: `tests/test_mark_rallies.py` (append TestApplyPadding)

- [ ] **Step 1: Append padding tests to test file**

Add to end of `tests/test_mark_rallies.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_mark_rallies.py::TestApplyPadding -v
```

Expected: ImportError.

- [ ] **Step 3: Add `_apply_padding()` after `_build_export_cmd()`**

```python
def _apply_padding(segments: List[Tuple[float, float]],
                   start_pad: float = 0.0, end_pad: float = 0.0) -> List[Tuple[float, float]]:
    """Apply start/end padding and merge overlapping segments."""
    if not segments:
        return []
    padded = sorted([(max(0, s - start_pad), e + end_pad) for s, e in segments])
    merged = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_mark_rallies.py -v
```

Expected: All 23 tests pass.

- [ ] **Step 5: Integrate padding into main() export prompt**

Replace the export section in main() (the `if segments:` block):

```python
    if segments:
        total_duration = sum(e - s for s, e in segments)
        print(f"Total highlight duration: {_format_duration(total_duration)}")
        print(f"Original duration: {_format_duration(player.duration)}")
        if player.duration > 0:
            reduction = (1 - total_duration / player.duration) * 100
            print(f"Reduction: {reduction:.1f}%")
        print()
        print(f"Segments saved to: {recorder._segments_file()}")
        print(f"Output video: {output_path}")
        print()
        print("Export settings:")
        print(f"  Start padding: 0.8s")
        print(f"  End padding:   1.2s")
        print(f"  CRF: 18")
        print(f"  Preset: veryfast")
        print()
        confirm = input("Export now? [Y/n] ").strip().lower()
        if confirm != 'n':
            padded = _apply_padding(segments, start_pad=0.8, end_pad=1.2)
            _export_segments(video_path, padded, output_path)
    else:
        print("No segments recorded.")
```

Also apply padding in `_export_session_standalone()` — replace the export block:

```python
    confirm = input("\nExport? [Y/n] ").strip().lower()
    if confirm != 'n':
        padded = _apply_padding(segments, start_pad=0.8, end_pad=1.2)
        print(f"After padding: {len(padded)} segments ({_format_duration(sum(e - s for s, e in padded))})")
        _export_segments(video_path, padded, output_path)
```

- [ ] **Step 6: Manual test — full workflow**

```bash
python mark_rallies.py
# → Full flow: resume → mark → review → export
# → Verify "Export settings" shows padding values
# → Verify session file still has original times after export
# → Verify output video plays correctly
# → Test E from LIST mode (with padding)
# → Test standalone export (E from startup menu)
```

---

## Phase 4: No code changes (documentation only)

The spec says: "不要一开始就做 CLI 大重构，先把主脚本体验打通."

`cli/badminton_cut.py` already delegates `mark` to `mark_rallies.py` (line 626-637). This works as-is.

**Post-implementation status:**

- `python mark_rallies.py` — full workflow: mark → review → export
- `python export_segments.py` — backward-compatible export-only entry
- `badminton-cut mark` — CLI entry (delegates to mark_rallies.py)

---

## Self-Review Checklist

### Spec Coverage

| Spec Phase | Requirement | Task |
|------------|-------------|------|
| Phase 1 | Export on quit | Task 3 |
| Phase 1 | Auto-create output/ | Task 2 (_export_segments) |
| Phase 1 | Auto-generate non-colliding name | Already exists (_find_next_output_index) |
| Phase 1 | Export failure preserves session + shows reason | Task 2 (capture_output + stderr + return bool) |
| Phase 1 | No segments = no export prompt | Task 3 (if segments check) |
| Phase 2 | Rich session display | Task 5 |
| Phase 2 | Video missing → re-bind path | Task 5 (_select_session) |
| Phase 2 | Skip # comments in count | Task 4 (_parse_session_info) |
| Phase 2 | Export existing session from menu | Task 5 (E option + _export_session_standalone) |
| Phase 3 | LIST mode reliable key input | Task 6 (always create window + display frame) |
| Phase 3 | Enter/Backspace navigation | Task 6 (KEY_MAP + handlers) |
| Phase 3 | E/S export/save keys | Task 6 (KEY_MAP + handlers) |
| Phase 3 | Auto-advance after preview | Task 7 |
| Phase 3 | Padding display | Task 8 |
| Phase 3 | Padding applied but session preserved | Task 8 (padding applied to copy) |
| Phase 3 | Overlap merge | Task 8 (_apply_padding) |
| Phase 4 | Keep compat entries | No change needed |

### Placeholder Scan

No TBD, TODO, "implement later", or placeholder steps found.

### Type Consistency

- `_parse_session_info()` returns dict with keys: `name, fpath, seg_count, highlight_duration, video_path, video_exists`
- `_list_sessions()` returns `List[dict]` via `_parse_session_info()` — all consumers updated in Task 5
- `_export_segments(video_path: str, segments, output_path: str) -> bool` — consistent across main(), _export_session_standalone(), and LIST mode handler
- `_apply_padding(segments, start_pad, end_pad) -> List[Tuple[float, float]]` — matches segment format everywhere
- `_load_session_segments(fpath) -> Tuple[List[Tuple[float, float]], str]` — shared by _parse_session_info and _export_session_standalone
