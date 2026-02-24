import cv2
import numpy as np
import subprocess
import os
import sys
import librosa

VIDEO = sys.argv[1]
OUTPUT = sys.argv[2]

# 参数（可调）
SAMPLE_FPS = 2           # 每秒采样帧数
MOTION_THRESHOLD = 8     # 运动阈值
AUDIO_THRESHOLD = 0.04   # 音频阈值
MIN_DURATION = 3         # 最小保留秒数
MERGE_GAP = 4            # 合并间隔秒数


def detect_motion(video):

    cap = cv2.VideoCapture(video)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    duration = total_frames / fps

    step = int(fps / SAMPLE_FPS)

    prev_gray = None

    timeline = []

    t = 0

    frame_id = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        if frame_id % step != 0:
            frame_id += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (320, 180))

        if prev_gray is not None:

            diff = cv2.absdiff(prev_gray, gray)
            motion = diff.mean()

            timeline.append((t, motion))

        prev_gray = gray

        t = frame_id / fps

        frame_id += 1

    cap.release()

    return timeline, duration


def extract_audio(video, output_wav="temp_audio.wav"):

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video,
        "-ac", "1",
        "-ar", "16000",
        output_wav
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return output_wav


def detect_audio(audio_file):

    y, sr = librosa.load(audio_file, sr=16000)

    energy = librosa.feature.rms(y=y)[0]

    timeline = []

    hop_length = 512

    for i, e in enumerate(energy):

        t = i * hop_length / sr

        timeline.append((t, e))

    return timeline


def combine_signals(timeline_motion, timeline_audio, duration):

    # Bucket by second for time alignment
    motion_by_second = {}
    audio_by_second = {}

    for t, motion in timeline_motion:
        second = int(t)
        if second not in motion_by_second:
            motion_by_second[second] = []
        motion_by_second[second].append(motion)

    for t, audio in timeline_audio:
        second = int(t)
        if second not in audio_by_second:
            audio_by_second[second] = []
        audio_by_second[second].append(audio)

    # Calculate average per second
    motion_avg = {}
    audio_avg = {}

    for second in motion_by_second:
        motion_avg[second] = sum(motion_by_second[second]) / len(motion_by_second[second])

    for second in audio_by_second:
        audio_avg[second] = sum(audio_by_second[second]) / len(audio_by_second[second])

    # Build combined timeline
    combined = []

    for second in range(int(duration)):

        motion = motion_avg.get(second, 0)
        audio = audio_avg.get(second, 0)

        combined.append((second, motion, audio))

    return combined


def build_segments_combined(combined):

    segments = []

    start = None

    for t, motion, audio in combined:

        # Dual-threshold rule: BOTH motion and audio must exceed thresholds
        if motion > MOTION_THRESHOLD and audio > AUDIO_THRESHOLD:

            if start is None:
                start = t

        else:

            if start is not None:

                end = t

                if end - start > MIN_DURATION:
                    segments.append((start, end))

                start = None

    return segments


def build_segments(timeline):

    segments = []

    start = None

    for t, motion in timeline:

        if motion > MOTION_THRESHOLD:

            if start is None:
                start = t

        else:

            if start is not None:

                end = t

                if end - start > MIN_DURATION:
                    segments.append((start, end))

                start = None

    return segments


def merge_segments(segments):

    if not segments:
        return []

    merged = [segments[0]]

    for s, e in segments[1:]:

        last_s, last_e = merged[-1]

        if s - last_e < MERGE_GAP:

            merged[-1] = (last_s, e)

        else:

            merged.append((s, e))

    return merged


def cut_video(video, segments):

    files = []

    for i, (s, e) in enumerate(segments):

        out = f"clip_{i}.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video,
            "-ss", str(s),
            "-to", str(e),
            "-c", "copy",
            out
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        files.append(out)

    return files


def concat(files, output):

    with open("list.txt", "w") as f:

        for file in files:
            f.write(f"file '{file}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "list.txt",
        "-c", "copy",
        output
    ]

    subprocess.run(cmd)

    os.remove("list.txt")

    for f in files:
        os.remove(f)


def main():

    print("=" * 60)
    print("Motion + Audio Detection Video Cutter - Analysis Mode")
    print("=" * 60)
    print()

    print(f"Input video: {VIDEO}")
    print(f"Output file: {OUTPUT}")
    print()

    print("Parameters:")
    print(f"  - SAMPLE_FPS: {SAMPLE_FPS} (sample {SAMPLE_FPS} frames per second)")
    print(f"  - MOTION_THRESHOLD: {MOTION_THRESHOLD} (motion sensitivity)")
    print(f"  - AUDIO_THRESHOLD: {AUDIO_THRESHOLD} (audio energy threshold)")
    print(f"  - MIN_DURATION: {MIN_DURATION}s (minimum segment duration)")
    print(f"  - MERGE_GAP: {MERGE_GAP}s (merge segments closer than this)")
    print()

    print("Detecting motion...")
    timeline_motion, duration = detect_motion(VIDEO)
    print(f"Video duration: {duration:.1f} seconds")
    print(f"Motion timeline samples: {len(timeline_motion)} points")
    print()

    print("Extracting audio...")
    audio_file = extract_audio(VIDEO)
    print(f"Audio extracted: {audio_file}")
    print()

    print("Detecting audio...")
    timeline_audio = detect_audio(audio_file)
    print(f"Audio timeline samples: {len(timeline_audio)} points")
    print()

    print("Combining signals...")
    combined = combine_signals(timeline_motion, timeline_audio, duration)
    print(f"Combined timeline: {len(combined)} seconds")
    print()

    print("Building segments (dual-threshold: motion + audio)...")
    segments = build_segments_combined(combined)

    print(f"Raw segments detected: {len(segments)}")
    for i, (s, e) in enumerate(segments):
        print(f"  Segment {i + 1}: {s:.1f}s -> {e:.1f}s (duration: {e - s:.1f}s)")
    print()

    segments = merge_segments(segments)

    print(f"Merged segments: {len(segments)}")
    print()

    print("=" * 60)
    print("Debug Output (per second):")
    print("=" * 60)
    print(f"{'Time':>5} | {'Motion':>7} | {'Audio':>7} | {'Keep':>4}")
    print("-" * 35)
    for t, motion, audio in combined[:30]:  # Show first 30 seconds
        keep = "YES" if motion > MOTION_THRESHOLD and audio > AUDIO_THRESHOLD else "NO"
        print(f"{t:5d} | {motion:7.2f} | {audio:7.4f} | {keep:>4}")
    if len(combined) > 30:
        print(f"... ({len(combined) - 30} more seconds)")
    print()

    print("=" * 60)
    print("Final Segments to be cut:")
    print("=" * 60)

    total_duration = 0
    for i, (s, e) in enumerate(segments):
        segment_duration = e - s
        total_duration += segment_duration
        print(f"Segment {i + 1:2d}: {s:7.1f}s -> {e:7.1f}s  (duration: {segment_duration:5.1f}s)")

    print()
    print("=" * 60)
    print(f"Total segments: {len(segments)}")
    print(f"Total output duration: {total_duration:.1f}s / {duration:.1f}s ({total_duration / duration * 100:.1f}%)")
    print(f"Time saved: {duration - total_duration:.1f}s ({(duration - total_duration) / duration * 100:.1f}%)")
    print("=" * 60)
    print()
    print("[DRY RUN] Skipping actual video cutting. Use '-c' flag to enable cutting.")

    # Clean up temp audio file
    if os.path.exists(audio_file):
        os.remove(audio_file)


if __name__ == "__main__":
    main()
