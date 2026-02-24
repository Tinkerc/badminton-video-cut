下面给你一个**Phase3-MVP（Optical Flow版）完整工程计划**。目标是解决你在双打羽毛球场景中遇到的问题：**捡球阶段仍然有运动，但运动模式与对抗阶段不同**。Phase3 的核心思想是：

> **识别“运动模式”而不是“运动强度”**

具体是：

> **回合阶段 = 高频方向变化 + 快速运动向量变化**
> **捡球阶段 = 低频方向变化 + 稳定移动**

这个方案仍然保持 **Python + OpenCV + FFmpeg 单机CLI可运行**，不依赖深度学习模型。

---

# 一、Phase3 MVP目标

输入：

```
badminton.mp4
```

输出：

```
highlight.mp4
```

自动：

* 检测回合阶段
* 删除捡球阶段
* 拼接视频

相比Phase2：

* 不依赖声音
* 不依赖运动量
* 更适合双打

---

# 二、核心算法设计

核心检测信号：

### Optical Flow（光流）

计算：

```
frame(t) → frame(t+1)
```

得到：

```
每个像素的运动向量
(dx, dy)
```

OpenCV函数：

```python
cv2.calcOpticalFlowFarneback()
```

输出：

```
flow[x,y] = (dx,dy)
```

---

# 三、关键特征定义（最重要）

Phase3 不再使用：

```
motion = diff.mean()
```

而是计算两个新指标：

---

## 指标1：平均运动速度

计算：

```
speed = sqrt(dx² + dy²)
```

取平均：

```python
avg_speed = np.mean(speed)
```

解释：

* 对抗阶段：速度大
* 捡球阶段：速度小

但不是唯一指标。

---

## 指标2（核心）：方向变化率

关键指标：

```
direction_change_rate
```

定义：

比较相邻帧：

```
flow(t)
vs
flow(t+1)
```

如果方向差异大：

说明运动模式变化快。

实现：

计算角度：

```python
angle = arctan2(dy, dx)
```

统计：

```
angle变化幅度
```

如果：

```
变化频繁 → 回合
```

如果：

```
稳定 → 捡球
```

这是核心创新点。

---

# 四、简化版特征设计（MVP推荐）

MVP不做复杂向量分析。

使用：

### Optical Flow标准差

定义：

```python
flow_std = np.std(flow)
```

解释：

| 场景 | flow_std |
| -- | -------- |
| 对抗 | 高        |
| 捡球 | 低        |

原因：

对抗：

```
方向乱
速度乱
```

捡球：

```
方向统一
速度统一
```

这个指标 surprisingly 有效。

---

# 五、Phase3 MVP指标组合

推荐公式：

```
score = a * avg_speed + b * flow_std
```

例如：

```
score = avg_speed + 2*flow_std
```

判断：

```
score > threshold
→ 保留
```

---

# 六、算法流程

完整流程：

---

## Step1 读取视频

```
cv2.VideoCapture()
```

---

## Step2 降采样

例如：

```
SAMPLE_FPS = 3
```

原因：

光流计算较重。

---

## Step3 灰度化 + 缩放

例如：

```
320x180
```

原因：

* 快10倍
* 足够检测运动模式

---

## Step4 Optical Flow计算

例如：

```python
flow = cv2.calcOpticalFlowFarneback(
 prev_gray,
 gray,
 None,
 0.5,
 3,
 15,
 3,
 5,
 1.2,
 0
)
```

---

## Step5 提取特征

例如：

```python
dx = flow[:,:,0]
dy = flow[:,:,1]

speed = np.sqrt(dx*dx + dy*dy)

avg_speed = speed.mean()

flow_std = speed.std()
```

得到：

```
(t,avg_speed,flow_std)
```

---

## Step6 时间序列生成

例如：

```
time speed std score
0    0.3   0.1 0.5
1    2.5   1.2 4.9
2    2.8   1.3 5.4
3    0.2   0.1 0.4
```

明显：

```
1-2秒是对抗
```

---

## Step7 片段检测

规则：

```
score > threshold
```

例如：

```
threshold = 2
```

生成：

```
(start,end)
```

---

## Step8 片段合并

同Phase1：

```
MERGE_GAP = 3秒
```

避免碎片。

---

## Step9 FFmpeg裁剪

同Phase1。

无需修改。

---

# 七、参数建议（羽毛球优化）

推荐初始参数：

```python
SAMPLE_FPS = 3

SCALE_WIDTH = 320

THRESHOLD = 2.0

MIN_DURATION = 4

MERGE_GAP = 4
```

非常适合双打。

---

# 八、工程结构建议

最简单：

```
auto_cut_flow.py
```

单文件。

推荐。

---

如果扩展：

```
flow.py
segment.py
ffmpeg.py
```

但MVP没必要。

---

# 九、调试工具（强烈建议）

输出：

```
time speed std score
```

例如：

```
10   2.3   1.1 4.5
11   2.6   1.2 5.0
12   0.2   0.1 0.4
```

可以一眼看出阈值。

这是成功关键。

---

# 十、性能预估

例如：

1080p视频：

```
60分钟
```

检测时间：

```
5~10分钟
```

完全可接受。

---

# 十一、预期效果

相比Phase1：

Phase1：

```
误保留捡球跑动
```

Phase3：

```
大部分捡球被删除
```

因为：

```
捡球 = 单向移动
```

```
回合 = 高频变化
```

Optical Flow对这个特别敏感。

---

# 十二、风险点（诚实评估）

可能失败情况：

### 情况1：

捡球阶段多人乱走。

可能误判。

但比motion好很多。

---

### 情况2：

摄像机晃动。

解决：

裁剪中心区域：

```
只分析中间70%
```

非常有效。

建议加。

---

# 十三、推荐增强（简单但很强）

只分析场地中间：

例如：

```
height 20%-80%
width 20%-80%
```

代码：

```python
gray = gray[
 h*0.2:h*0.8,
 w*0.2:w*0.8
]
```

效果明显提升。

因为：

* 去掉观众
* 去掉边缘移动

非常推荐。

---

# 十四、Phase3 MVP定义

完成标准：

必须：

* Optical Flow检测
* 自动分段
* 自动剪辑

如果达到：

```
60分钟 → 30分钟
基本都是回合
```

就成功。

---

# 十五、开发时间预估

实际：

| 任务   | 时间   |
| ---- | ---- |
| 光流实现 | 1小时  |
| 特征计算 | 30分钟 |
| 分段逻辑 | 30分钟 |
| 调参   | 1小时  |

总计：

```
3小时左右
```

---

如果你愿意，我可以直接给你 **Phase3完整脚本（真正可运行）**，这个版本通常是第一次开始真正接近“自动剪羽毛球比赛”的方案。
