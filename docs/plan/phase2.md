下面给你一个**Phase2 工程计划（Motion + Audio 融合检测）**，目标是把 Phase1 的 MVP 升级为**稳定可用的自动羽毛球剪辑工具**。重点是：**不复杂，但准确率显著提升（通常可达 85–95%）**。

---

# Phase2 目标

在 Phase1 的基础上新增：

> 利用**击球声音 + 运动量融合判断回合阶段**

核心目标：

* 避免误判（例如捡球走动）
* 更稳定识别对抗阶段
* 自动剪辑更接近人工效果

Phase1：

```
只看 motion
```

Phase2：

```
motion + audio
```

---

# 一、Phase2 总体架构

整体流程：

```
video.mp4

↓ OpenCV
motion curve

↓ FFmpeg提取音频

↓ librosa
audio curve

↓ Python融合

segments.json

↓ FFmpeg

highlight.mp4
```

新增部分只有：

```
audio detection
```

其他完全复用 Phase1。

---

# 二、核心新增模块

新增两个文件逻辑：

```
detect_audio()
combine_signals()
```

---

# 三、音频分析方案设计

目标：

检测：

```
击球声音密集区域
```

羽毛球特征：

* 清晰的“啪”
* 高频瞬态
* 对抗阶段连续出现

捡球阶段：

* 几乎安静

非常适合音频检测。

---

# 四、音频提取（FFmpeg）

先提取音频：

```
ffmpeg -i video.mp4 -ac 1 -ar 16000 audio.wav
```

解释：

```
-ac 1
单声道

-ar 16000
16kHz采样
```

优点：

* 文件小
* 足够分析

Python调用：

```python
subprocess.run([
 "ffmpeg",
 "-y",
 "-i",video,
 "-ac","1",
 "-ar","16000",
 "audio.wav"
])
```

---

# 五、音频特征提取

推荐库：

```
librosa
```

安装：

```
pip install librosa
```

---

## 方法1（最简单）

计算音量曲线：

```python
import librosa

y, sr = librosa.load("audio.wav")

energy = librosa.feature.rms(y=y)[0]
```

得到：

```
time → energy
```

例如：

```
0s   0.01
1s   0.02
2s   0.15
3s   0.20
4s   0.18
5s   0.01
```

明显：

```
2-4秒是对抗
```

---

# 六、时间对齐

motion：

```
2fps
```

audio：

```
几十fps
```

需要统一。

建议：

统一到：

```
1秒一个值
```

例如：

```
second  motion  audio

0       2       0.01
1       3       0.02
2       15      0.15
3       20      0.20
```

实现：

```python
second = int(time)
bucket[second].append(value)
```

取平均。

---

# 七、融合算法设计（核心）

推荐最简单可靠方案：

## 方法1：加权评分（推荐）

定义：

```
score = a * motion + b * audio
```

例如：

```
score = motion + 50 * audio
```

原因：

audio值通常很小。

例如：

```
motion = 10
audio = 0.1

score = 10 + 5
```

合理。

---

判断：

```
score > threshold → 保留
```

例如：

```
threshold = 12
```

---

# 八、另一种融合方式（更稳）

推荐：

## 方法2：双阈值规则（强烈推荐）

规则：

```
保留 if：

motion > motion_threshold

AND

audio > audio_threshold
```

例如：

```
motion > 8
audio > 0.05
```

优点：

非常稳定。

不会误判：

* 捡球跑动
* 摄像机晃动

因为：

```
motion高但audio低
→ 删除
```

这正是捡球场景。

这是最推荐的。

---

# 九、Phase2 参数设计

建议参数：

```python
MOTION_THRESHOLD = 8

AUDIO_THRESHOLD = 0.04

MIN_DURATION = 3

MERGE_GAP = 4
```

羽毛球适配很好。

---

# 十、代码结构建议

Phase2结构：

```
auto_cut/

auto_cut.py

motion.py
audio.py
segment.py
ffmpeg.py
```

或者简单：

```
auto_cut_phase2.py
```

也可以。

---

# 十一、Phase2算法流程

完整流程：

---

## Step1

检测motion：

```
timeline_motion = detect_motion(video)
```

输出：

```
[(t,motion)]
```

---

## Step2

提取音频：

```
extract_audio(video)
```

生成：

```
audio.wav
```

---

## Step3

检测audio：

```
timeline_audio = detect_audio(audio.wav)
```

输出：

```
[(t,audio)]
```

---

## Step4

融合：

```
segments = combine(
 motion,
 audio
)
```

输出：

```
[(start,end)]
```

---

## Step5

FFmpeg裁剪：

和Phase1一样。

---

# 十二、Phase2开发时间估计

经验值：

| 任务       | 时间    |
| -------- | ----- |
| motion复用 | 0     |
| audio检测  | 1小时   |
| 融合算法     | 1小时   |
| 调参       | 1–2小时 |

总计：

```
3~5小时
```

就能完成。

---

# 十三、预期效果提升

Phase1：

```
motion only

准确率：

70-85%
```

典型问题：

* 捡球跑动被保留

---

Phase2：

```
motion + audio
```

准确率：

```
85-95%
```

通常已经接近人工剪辑。

---

# 十四、关键工程技巧（非常重要）

建议增加一个调试输出：

例如：

```
time motion audio score keep

10   12     0.1    17   yes
11   3      0.01   3.5  no
```

非常容易调参。

这是工程高手习惯。

---

# 十五、Phase2 MVP定义（推荐）

Phase2完成标准：

必须具备：

* motion detection
* audio detection
* 自动融合
* 自动剪辑

加分项：

* 输出segments.txt

例如：

```
10.2 35.6
40.0 60.3
```

便于调试。

---

# 十六、推荐路线（最优）

最优顺序：

### Step1

在Phase1中加入：

```
extract_audio()
```

10分钟。

---

### Step2

实现：

```
detect_audio()
```

30分钟。

---

### Step3

替换：

```
build_segments()
```

改为：

```
combine_segments()
```

1小时。

---

# 十七、最终能力

完成Phase2后，你实际上拥有：

```
自动羽毛球highlight生成器
```

非常接近产品级。

---

如果你愿意，我可以直接给你一个**Phase2完整可运行脚本（约150行）**，可以直接把羽毛球视频自动剪成 highlight，而且效果会明显优于 Phase1。
