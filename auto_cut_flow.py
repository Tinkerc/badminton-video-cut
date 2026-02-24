import cv2
import numpy as np
import subprocess
import os
import sys

VIDEO = sys.argv[1]
OUTPUT = sys.argv[2]

# 参数（可调）
SAMPLE_FPS = 3           # 每秒采样帧数（光流计算较重）
SCALE_WIDTH = 320        # 缩放宽度
SCALE_HEIGHT = 180       # 缩放高度
THRESHOLD = 2.0          # 综合评分阈值
MIN_DURATION = 4         # 最小保留秒数
MERGE_GAP = 4            # 合并间隔秒数
CENTER_CROP = True       # 是否只分析中心区域


def detect_optical_flow(video):

    cap = cv2.VideoCapture(video)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    duration = total_frames / fps

    step = int(fps / SAMPLE_FPS)

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

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (SCALE_WIDTH, SCALE_HEIGHT))

        # 中心裁剪（去除边缘干扰）
        if CENTER_CROP:
            h, w = gray.shape
            gray = gray[
                int(h * 0.2):int(h * 0.8),
                int(w * 0.2):int(w * 0.8)
            ]

        if prev_gray is not None and prev_gray.shape == gray.shape:

            # 计算光流
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray,
                gray,
                None,
                0.5,      # pyr_scale
                3,        # levels
                15,       # winsize
                3,        # iterations
                5,        # poly_n
                1.2,      # poly_sigma
                0         # flags
            )

            # 提取特征
            features = extract_flow_features(flow)

            t = frame_id / fps
            timeline.append((t, features))

        prev_gray = gray

        frame_id += 1

    cap.release()

    return timeline, duration


def extract_flow_features(flow):

    # 提取dx, dy分量
    dx = flow[:, :, 0]
    dy = flow[:, :, 1]

    # 计算速度
    speed = np.sqrt(dx * dx + dy * dy)

    # 平均速度
    avg_speed = np.mean(speed)

    # 速度标准差（运动模式复杂度）
    flow_std = np.std(speed)

    # 综合评分
    score = avg_speed + 2 * flow_std

    return {
        'avg_speed': avg_speed,
        'flow_std': flow_std,
        'score': score
    }


def build_segments_flow(timeline):

    segments = []

    start = None

    for t, features in timeline:

        score = features['score']

        if score > THRESHOLD:

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
    print("Optical Flow Video Cutter - Analysis Mode")
    print("=" * 60)
    print()

    print(f"Input video: {VIDEO}")
    print(f"Output file: {OUTPUT}")
    print()

    print("Parameters:")
    print(f"  - SAMPLE_FPS: {SAMPLE_FPS} (sample {SAMPLE_FPS} frames per second)")
    print(f"  - SCALE: {SCALE_WIDTH}x{SCALE_HEIGHT} (downscale for speed)")
    print(f"  - THRESHOLD: {THRESHOLD} (score threshold)")
    print(f"  - MIN_DURATION: {MIN_DURATION}s (minimum segment duration)")
    print(f"  - MERGE_GAP: {MERGE_GAP}s (merge segments closer than this)")
    print(f"  - CENTER_CROP: {CENTER_CROP} (analyze center 60% only)")
    print()

    print("Detecting optical flow...")
    timeline, duration = detect_optical_flow(VIDEO)

    print(f"Video duration: {duration:.1f} seconds")
    print(f"Optical flow samples: {len(timeline)} points")
    print()

    print("Building segments...")
    segments = build_segments_flow(timeline)

    print(f"Raw segments detected: {len(segments)}")
    for i, (s, e) in enumerate(segments):
        print(f"  Segment {i + 1}: {s:.1f}s -> {e:.1f}s (duration: {e - s:.1f}s)")
    print()

    segments = merge_segments(segments)

    print(f"Merged segments: {len(segments)}")
    print()

    print("=" * 60)
    print("Debug Output (filtered segments only):")
    print("=" * 60)
    print(f"{'Time':>5} | {'Speed':>6} | {'Std':>6} | {'Score':>6} | {'Keep':>4}")
    print("-" * 50)

    # Only show segments where Keep=NO
    filtered_count = 0
    for t, features in timeline:
        speed = features['avg_speed']
        std = features['flow_std']
        score = features['score']
        keep = "YES" if score > THRESHOLD else "NO"

        if keep == "NO":
            print(f"{t:5.1f} | {speed:6.2f} | {std:6.2f} | {score:6.2f} | {keep:>4}")
            filtered_count += 1

    print()
    print(f"Filtered out: {filtered_count} / {len(timeline)} samples ({filtered_count / len(timeline) * 100:.1f}%)")
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


if __name__ == "__main__":
    main()
