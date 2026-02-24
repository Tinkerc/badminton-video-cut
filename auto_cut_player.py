import cv2
import numpy as np
import subprocess
import os
import sys
from ultralytics import YOLO

VIDEO = sys.argv[1]
OUTPUT = sys.argv[2]

# 参数（可调）
SAMPLE_FPS = 3           # 每秒采样帧数
WINDOW_SECONDS = 1.5     # 滑动窗口大小（秒）
THRESHOLD_RATIO = 0.4    # 阈值比例（相对于最大分数）
MIN_DURATION = 2         # 最小保留秒数
MERGE_GAP = 4            # 合并间隔秒数
USE_VELOCITY_STD = True  # 使用速度标准差（推荐）


def detect_persons(frame, model):

    results = model(frame)

    persons = []

    for box in results[0].boxes:
        cls = int(box.cls[0])

        # COCO class 0 = person
        if cls == 0:
            x1, y1, x2, y2 = box.xyxy[0]
            persons.append((int(x1), int(y1), int(x2), int(y2)))

    return persons


def select_player(persons):

    if len(persons) == 0:
        return None

    # 选择bbox面积最大的人（通常是场上球员）
    return max(persons, key=lambda p: (p[2] - p[0]) * (p[3] - p[1]))


def track_trajectory(video, model):

    cap = cv2.VideoCapture(video)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    duration = total_frames / fps

    step = int(fps / SAMPLE_FPS)

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

        persons = detect_persons(frame, model)

        player = select_player(persons)

        if player:

            x1, y1, x2, y2 = player

            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            trajectory.append((cx, cy))
            frame_times.append(frame_id / fps)

        frame_id += 1

    cap.release()

    return trajectory, frame_times, duration


def motion_score_distance(points):

    if len(points) < 2:
        return 0

    dist = 0

    for i in range(1, len(points)):

        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]

        dist += np.sqrt(dx * dx + dy * dy)

    return dist


def motion_score_velocity_std(points):

    if len(points) < 3:
        return 0

    velocities = []

    for i in range(1, len(points)):

        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]

        v = np.sqrt(dx * dx + dy * dy)

        velocities.append(v)

    return np.std(velocities)


def build_segments_trajectory(trajectory, frame_times, fps, actual_window_size):

    if len(trajectory) < actual_window_size:
        return [], [], [], 0

    scores = []
    times = []

    # 选择评分函数
    score_func = motion_score_velocity_std if USE_VELOCITY_STD else motion_score_distance

    # 滑动窗口分析
    for i in range(actual_window_size, len(trajectory)):

        segment = trajectory[i - actual_window_size:i]

        score = score_func(segment)

        t = frame_times[i]

        scores.append(score)
        times.append(t)

    # 自适应阈值
    if len(scores) == 0:
        return [], [], [], 0

    max_score = max(scores)
    threshold = max_score * THRESHOLD_RATIO

    # 判定回合阶段
    segments = []

    start = None

    for t, score in zip(times, scores):

        if score > threshold:

            if start is None:
                start = t

        else:

            if start is not None:

                end = t

                if end - start > MIN_DURATION:
                    segments.append((start, end))

                start = None

    return segments, scores, times, threshold


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
    print("Player Trajectory Video Cutter - Analysis Mode")
    print("=" * 60)
    print()

    print(f"Input video: {VIDEO}")
    print(f"Output file: {OUTPUT}")
    print()

    print("Parameters:")
    print(f"  - SAMPLE_FPS: {SAMPLE_FPS} (sample {SAMPLE_FPS} frames per second)")
    print(f"  - WINDOW_SECONDS: {WINDOW_SECONDS}s (sliding window)")
    print(f"  - THRESHOLD_RATIO: {THRESHOLD_RATIO} (adaptive threshold)")
    print(f"  - MIN_DURATION: {MIN_DURATION}s (minimum segment duration)")
    print(f"  - MERGE_GAP: {MERGE_GAP}s (merge segments closer than this)")
    print(f"  - USE_VELOCITY_STD: {USE_VELOCITY_STD} (score method)")
    print()

    print("Loading YOLO model...")
    model = YOLO("yolov8s.pt")  # 使用更大的模型提高检测率
    print("YOLO model loaded.")
    print()

    print("Tracking player trajectory...")
    trajectory, frame_times, duration = track_trajectory(VIDEO, model)

    print(f"Video duration: {duration:.1f} seconds")
    print(f"Trajectory points: {len(trajectory)}")

    # 获取实际fps
    cap = cv2.VideoCapture(VIDEO)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    print(f"Video FPS: {actual_fps:.1f}")

    # 计算期望的轨迹点数
    expected_points = int(duration * SAMPLE_FPS)
    detection_rate = len(trajectory) / expected_points * 100 if expected_points > 0 else 0
    print(f"Expected points: {expected_points}, Detection rate: {detection_rate:.1f}%")
    print()

    # 计算窗口大小
    actual_window_size = int(actual_fps * WINDOW_SECONDS)
    print(f"Window size: {actual_window_size} frames ({WINDOW_SECONDS}s @ {actual_fps:.1f}fps)")

    if len(trajectory) < actual_window_size:
        print("Error: Not enough trajectory points for analysis.")
        return

    print("Analyzing trajectory segments...")
    segments, scores, times, threshold = build_segments_trajectory(trajectory, frame_times, actual_fps, actual_window_size)

    # 诊断信息
    print()
    print("=" * 60)
    print("Score Statistics:")
    print("=" * 60)
    print(f"Min: {min(scores):.2f}")
    print(f"Max: {max(scores):.2f}")
    print(f"Avg: {sum(scores)/len(scores):.2f}")
    print(f"Threshold: {threshold:.2f} ({THRESHOLD_RATIO*100:.0f}% of max)")
    print()

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
    print(f"{'Time':>5} | {'Score':>8} | {'Thresh':>8} | {'Keep':>4}")
    print("-" * 40)

    filtered_count = 0
    kept_count = 0
    for t, score in zip(times, scores):
        keep = "YES" if score > threshold else "NO"
        if keep == "NO":
            print(f"{t:5.1f} | {score:8.2f} | {threshold:8.2f} | {keep:>4}")
            filtered_count += 1
        else:
            kept_count += 1

    print()
    print(f"Kept: {kept_count} / {len(scores)} windows ({kept_count / len(scores) * 100:.1f}%)")
    print(f"Filtered out: {filtered_count} / {len(scores)} windows ({filtered_count / len(scores) * 100:.1f}%)")
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
