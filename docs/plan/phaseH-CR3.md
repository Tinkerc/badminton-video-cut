可以把快捷键改为：

* **方向键 ← / →**：前进 / 后退（短跳转）
* **方向键 ↑ / ↓**：前进 / 后退（长跳转）
* **空格 Space**：代替 `R`，用于 Start / End rally
* **Q**：退出并导出（保持不变）
* **W / X**：调节速度（保持不变）

下面是修改后的说明文档版本：

```python
"""
Phase-H Efficient MVP - Manual Rally Marker
Keyboard-controlled video player for marking badminton rally segments.

Usage:
    python mark_rallies.py input.mp4 [output.mp4]

Keyboard Controls:
    Space      - Toggle rally recording (start/end segment)

    Right Arrow  →  - Jump forward 5 seconds
    Left Arrow   ←  - Jump backward 5 seconds

    Up Arrow     ↑  - Jump forward 30 seconds
    Down Arrow   ↓  - Jump backward 30 seconds

    W - Increase playback speed
    X - Decrease playback speed

    Q - Quit and export video
"""
```

如果你用的是 **OpenCV `cv2.waitKey()`**，方向键的 keycode 通常是：

```python
KEY_LEFT  = 81
KEY_UP    = 82
KEY_RIGHT = 83
KEY_DOWN  = 84
KEY_SPACE = 32
```

示例修改：

```python
key = cv2.waitKey(1) & 0xFF

if key == 32:  # Space
    toggle_rally()

elif key == 81:  # Left arrow
    jump(-5)

elif key == 83:  # Right arrow
    jump(5)

elif key == 82:  # Up arrow
    jump(30)

elif key == 84:  # Down arrow
    jump(-30)

elif key == ord('w'):
    speed_up()

elif key == ord('x'):
    speed_down()

elif key == ord('q'):
    quit_and_export()
```

**这个设计其实更符合人体工学：**

* 左右键 = 精细移动（±5秒）
* 上下键 = 粗移动（±30秒）
* 空格 = Start/Stop（符合播放器直觉）

如果你愿意，我可以给你一个**完整优化版 mark_rallies.py（含方向键兼容 Windows/Linux/Mac）**，避免 OpenCV 方向键识别不稳定的问题。
