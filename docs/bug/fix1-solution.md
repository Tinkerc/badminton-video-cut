并未自动播放：

 python mark_rallies.py ./data/21917.MP4                                                at  22:29:55
============================================================
Phase-H Efficient MVP - Manual Rally Marker
============================================================

Keyboard Controls:
  R - Toggle rally recording (start/end)
  D - Jump forward 5 seconds
  A - Jump backward 5 seconds
  F - Jump forward 30 seconds
  S - Jump backward 30 seconds
  W - Increase playback speed (0.5x - 4x)
  X - Decrease playback speed
  Q - Quit and export video

Typical workflow:
  1. Watch video at 2x speed
  2. Press R to start rally
  3. Press D/D to skip dead time
  4. Press R to end rally
  5. Press Q to export

============================================================

Input:  ./data/21917.MP4
Output: 21917_highlight.mp4

Video loaded: 1280x720 @ 30.0fps
Duration: 44.7 seconds

Press any key to start...

^[[A^[[A^[[A^[[A^[[A^[[Adddddddkkkk

参考解决方案：
是的，**设计目标就是：实时播放视频 + 实时预览 + 接收键盘输入**。
如果你没有看到播放窗口，说明 **OpenCV 显示或事件循环没有正确运行**。下面我把正确的工作机制和最小可运行版本说清楚。

---

# 一、正确的运行效果应该是这样

运行：

```bash
python mark_rallies.py badminton.mp4
```

应该出现一个窗口：

```
+----------------------------+
|                            |
|        视频画面            |
|                            |
| Time: 12.4s  Speed:1.0x    |
| Segments:2                |
| REC ●                     |
+----------------------------+
```

然后：

* 视频实时播放
* 按键即时响应
* 按 `R` 开始记录
* 按 `D` 快进
* 按 `Q` 退出

这是 **实时预览播放器**。

---

# 二、最小可运行版本（必须先验证）

先运行这个最简单版本测试：

```python
import cv2
import sys

video = sys.argv[1]

cap = cv2.VideoCapture(video)

fps = cap.get(cv2.CAP_PROP_FPS)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    cv2.imshow("Video", frame)

    key = cv2.waitKey(int(1000/fps)) & 0xFF

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

运行：

```bash
python test_player.py badminton.mp4
```

必须能看到视频窗口。

如果看不到，说明环境问题。

---

# 三、常见原因（90%在这里）

## 原因1：没有GUI环境

如果你在：

* SSH终端
* 服务器
* Docker
* WSL
* VSCode Remote

OpenCV窗口不会出现。

测试：

```bash
echo $DISPLAY
```

如果空的：

说明没有GUI。

必须在本地终端运行。

例如：

```
Mac Terminal
Windows CMD
Linux Desktop
```

---

# 四、正确的交互播放器版本

这是可以直接用的版本：

```python
import cv2
import sys

video=sys.argv[1]

cap=cv2.VideoCapture(video)

fps=cap.get(cv2.CAP_PROP_FPS)

segments=[]

recording=False
start=0

speed=1.0

while True:

    ret,frame=cap.read()

    if not ret:
        break

    t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000

    text=f"Time:{t:.1f}s Speed:{speed}x Seg:{len(segments)}"

    cv2.putText(
        frame,
        text,
        (20,40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    if recording:

        cv2.putText(
            frame,
            "REC",
            (20,80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0,0,255),
            2
        )

    cv2.imshow("Player",frame)

    delay=int(1000/fps/speed)

    key=cv2.waitKey(delay)&0xFF


    if key==ord('r'):

        if not recording:

            start=t
            recording=True

            print("START",round(t,2))

        else:

            segments.append((start,t))

            recording=False

            print("END",round(t,2))


    elif key==ord('d'):

        pos=cap.get(cv2.CAP_PROP_POS_FRAMES)

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            pos+fps*5
        )


    elif key==ord('a'):

        pos=cap.get(cv2.CAP_PROP_POS_FRAMES)

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            max(pos-fps*5,0)
        )


    elif key==ord('w'):

        speed=min(speed+0.5,4)


    elif key==ord('x'):

        speed=max(speed-0.5,0.5)


    elif key==ord('q'):
        break


cap.release()

cv2.destroyAllWindows()

print("\nSegments:")

print(segments)
```

---

# 五、预期体验

运行后：

### 正常流程：

```
视频自动播放
```

你按：

```
R
```

终端：

```
START 12.4
```

再按：

```
R
```

终端：

```
END 38.1
```

输出：

```
Segments:

[(12.4,38.1)]
```

---

# 六、如果还是没窗口

试这个：

```python
cv2.namedWindow("Player", cv2.WINDOW_NORMAL)
```

放在while前：

```python
cv2.namedWindow("Player", cv2.WINDOW_NORMAL)
```

完整：

```python
cv2.namedWindow("Player", cv2.WINDOW_NORMAL)

while True:
```

有些系统必须这样。

---

# 七、如果仍然不行（关键诊断）

告诉我：

1：

```
python --version
```

2：

```
pip show opencv-python
```

3：

你在哪里运行：

* Mac terminal？
* Windows？
* Linux？
* WSL？
* SSH？

因为 **OpenCV窗口不出现几乎都是环境问题，不是代码问题。**

---

# 八、确认一下设计目标

是的，你理解完全正确：

> 是会实时预览然后接收keyboard输入吗？

答案：

**完全是。**

就是一个：

```
极简视频播放器 + 标记工具
```

体验类似：

```
mpv + 键盘标记
```

但专门为剪辑优化。

---

如果你愿意，我可以给你一个 **更专业版（≈250行）**：

* 无卡顿跳转
* 自动保存
* 自动FFmpeg剪辑
* 更流畅播放

那个会接近真正工具级体验。
