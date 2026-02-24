下面是一个**可落地的高效率人工标记方案 Plan（Phase-H Efficient MVP）**，目标是做到：

> **45分钟羽毛球视频 → 3~5分钟内完成标记 → 自动输出剪辑视频**

核心思想：
**最少按键 + 不拖动时间轴 + 自动剪辑**

技术栈保持你偏好的：

* Python
* OpenCV（播放与交互）
* FFmpeg（剪辑）
* CLI工具

这是一个**真正可实现的工程计划**。

---

# Phase-H Efficient MVP Plan

## 目标能力

实现一个 CLI 工具：

```bash
python mark_rallies.py badminton.mp4
```

用户操作：

```
R → 回合开始/结束（toggle）
D → 快进5秒
A → 后退5秒
Q → 退出并导出
```

输出：

```
segments.txt
output.mp4
```

示例：

```
12.3 42.8
55.2 75.1
80.1 103.7
```

---

# 一、系统架构

整体流程：

```
视频输入
   ↓
OpenCV播放器
   ↓
键盘交互记录segments
   ↓
保存segments.txt
   ↓
FFmpeg自动剪辑
   ↓
highlight.mp4
```

模块结构：

```
mark_rallies.py

├── VideoPlayer
├── SegmentRecorder
├── KeyboardController
└── FFmpegExporter
```

代码规模：

```
150–250行
```

---

# 二、核心交互设计（效率核心）

## 键盘设计

推荐最终键位：

```
R  toggle回合
D  +5秒
A  -5秒

F  +30秒（快速跳）
S  -30秒

W  加速播放
X  减速播放

Q  退出并保存
```

最常用的是：

```
R
D
D
R
```

例如：

```
R  开始回合
D  D  跳过捡球
R  结束回合
```

几乎不需要停顿。

---

# 三、Segment记录设计

数据结构：

```python
segments = [
 (start,end),
 (start,end)
]
```

状态机：

```
recording = False
```

逻辑：

### 按R：

如果：

```
recording=False
```

则：

```
start=t
recording=True
```

否则：

```
segments.append((start,t))
recording=False
```

这是效率最高方案。

---

# 四、播放器设计

使用OpenCV：

核心循环：

```python
while True:

    ret,frame=cap.read()

    cv2.imshow("Video",frame)

    key=cv2.waitKey(delay)
```

delay：

```
delay = int(1000/fps/playback_speed)
```

支持速度变化：

```
1x
2x
3x
```

例如：

```python
playback_speed=2
```

回合识别时通常可以：

```
2x观看
```

效率提升明显。

---

# 五、跳转系统设计

核心函数：

```python
def jump_seconds(cap,seconds,fps):

    pos=cap.get(cv2.CAP_PROP_POS_FRAMES)

    new_pos=pos+seconds*fps

    cap.set(
        cv2.CAP_PROP_POS_FRAMES,
        max(new_pos,0)
    )
```

按键：

```
D → +5秒
A → -5秒
F → +30秒
S → -30秒
```

这个是效率关键。

否则必须看完整视频。

---

# 六、实时状态显示（强烈推荐）

在画面上叠加信息：

```
Time: 12.3s
Speed: 2x
REC ●
Segments: 3
```

代码：

```python
cv2.putText(
 frame,
 f"Time:{t:.1f}",
 (20,40),
 cv2.FONT_HERSHEY_SIMPLEX,
 1,
 (0,255,0),
 2
)
```

如果正在记录：

显示：

```
REC ●
```

避免忘记结束。

这是非常重要的UX。

---

# 七、自动保存segments

输出文件：

```
segments.txt
```

格式：

```
12.3 42.8
55.1 73.0
```

代码：

```python
with open("segments.txt","w") as f:

    for s,e in segments:

        f.write(f"{s} {e}\n")
```

这样可以复用。

---

# 八、自动剪辑模块

生成FFmpeg命令：

```python
expr="+".join(
 f"between(t,{s},{e})"
 for s,e in segments
)
```

执行：

```bash
ffmpeg -i badminton.mp4 \
-vf "select='expr'" \
-af "aselect='expr'" \
-vsync 0 \
highlight.mp4
```

Python：

```python
subprocess.run(cmd)
```

完全自动化。

---

# 九、性能目标

设计目标：

| 项目       | 目标    |
| -------- | ----- |
| 标记45分钟视频 | 3–5分钟 |
| 剪辑时间     | 30秒   |
| 总代价      | <6分钟  |

比传统剪辑：

```
30分钟+
```

快一个数量级。

---

# 十、MVP实现顺序

推荐顺序：

### Step1

基础播放器：

```
播放视频
```

预计：

```
20分钟
```

---

### Step2

R toggle：

```
记录segments
```

预计：

```
30分钟
```

---

### Step3

跳转键：

```
A/D/F/S
```

预计：

```
20分钟
```

---

### Step4

FFmpeg输出：

```
自动剪辑
```

预计：

```
20分钟
```

---

### Step5

UI overlay：

```
Time
REC
Speed
```

预计：

```
20分钟
```

---

总开发时间：

```
2–3小时
```

即可完成一个**真正好用的工具**。

---

# 十一、Phase-H+（未来增强）

后续可以加入：

### 自动建议回合

比如：

```
suggested_segments.txt
```

播放器自动跳转：

```
先看AI建议
```

你只修正。

效率可以再翻倍。

---

# 十二、关键设计原则（非常重要）

这个工具成功的关键不是算法，而是：

### 原则1

> 不要拖时间轴

必须：

```
键盘跳转
```

---

### 原则2

> 不要频繁暂停

支持：

```
2x播放
```

---

### 原则3

> 按键最少

理想：

```
R D R
```

就是一个回合。

---

# 十三、结论

这个 **Phase-H Efficient MVP**：

* 比AI方案稳定
* 比剪辑软件快10倍
* 开发成本极低
* 非常适合个人使用

而且这是一个**真正能长期使用的工具架构**。

如果你愿意，我可以直接给你一个**完整版脚本（≈200行，直接可用）**，基本就是生产级CLI工具。
