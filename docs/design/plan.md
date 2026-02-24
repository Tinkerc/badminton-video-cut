推荐三阶段：

------

## Phase1（最推荐）

只用：

```
motion detection
```

技术：

```
Python
OpenCV
FFmpeg
```

开发时间：

1–2天。

成功率：

70–85%。

已经很好。

------

## Phase2（强烈建议）

增加：

```
audio detection
```

技术：

```
librosa
```

成功率：

85–95%。

非常稳。

------

## Phase3（未来）

增加：

```
pose estimation
```

成功率：

95%+

但复杂。

------

# 十二、最终架构（推荐）

最合理：

```
match.mp4

↓ OpenCV

motion curve

↓ librosa

audio curve

↓ Python

segment detection

↓

segments.json

↓

FFmpeg

↓

highlight.mp4
```

------

# 十三、关键洞察（最重要）

真正核心不是AI模型。

而是：

**把“对抗阶段”转化为信号特征**

例如：

```
对抗阶段 =

高motion
+
连续时间
+
击球声
```

这是工程关键。