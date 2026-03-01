下面是一个**Python 技术方案（Technical Design）**，用于实现：
**加载 WebM / MP4 视频文件 → 分离音频 → 输出音频文件（如 WAV / MP3 / AAC）**

方案强调：**稳定、简单、可扩展、适合生产环境**

---

# 一、方案目标

实现一个 Python 模块：

输入：

* `.webm`
* `.mp4`

输出：

* `.wav`
* `.mp3`
* `.aac`

功能：

* 自动识别视频格式
* 提取音频流
* 支持批量处理
* 支持CLI调用
* 支持Python调用

---

# 二、技术选型

推荐方案：

| 技术                             | 用途       | 原因     |
| ------------------------------ | -------- | ------ |
| **ffmpeg**                     | 音频提取核心   | 最稳定    |
| **ffmpeg-python** 或 subprocess | Python调用 | 灵活     |
| pathlib                        | 文件处理     | 标准库    |
| logging                        | 日志       | 生产环境需要 |

推荐：

> ⭐ 使用 **FFmpeg + subprocess**
> 比 moviepy 更稳定更快

---

# 三、依赖安装

安装 ffmpeg：

Linux：

```bash
sudo apt install ffmpeg
```

Mac：

```bash
brew install ffmpeg
```

Windows：

下载：

[https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

验证：

```bash
ffmpeg -version
```

---

# 四、项目结构

建议结构：

```
video_audio_extractor/
│
├── extractor.py
├── cli.py
├── config.py
└── requirements.txt
```

requirements.txt：

```
# 无第三方依赖（推荐）
```

---

# 五、核心模块设计

## extractor.py

核心功能：

* 加载视频
* 提取音频
* 输出文件

示例实现：

```python
from pathlib import Path
import subprocess
import logging

logging.basicConfig(level=logging.INFO)


class AudioExtractor:

    def __init__(self):
        pass

    def extract_audio(
        self,
        video_path: str,
        output_path: str = None,
        audio_format: str = "wav"
    ):
        """
        Extract audio from video file

        Args:
            video_path: mp4 or webm
            output_path: output audio file
            audio_format: wav/mp3/aac
        """

        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(video_path)

        if output_path is None:
            output_path = video_path.with_suffix("." + audio_format)

        output_path = Path(output_path)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", self._codec(audio_format),
            str(output_path)
        ]

        logging.info("Running ffmpeg...")
        logging.info(" ".join(cmd))

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())

        logging.info(f"Audio saved: {output_path}")

        return output_path


    def _codec(self, fmt):

        codecs = {
            "wav": "pcm_s16le",
            "mp3": "libmp3lame",
            "aac": "aac"
        }

        if fmt not in codecs:
            raise ValueError("Unsupported format")

        return codecs[fmt]
```

---

# 六、CLI支持

cli.py

```python
import argparse
from extractor import AudioExtractor


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="video file"
    )

    parser.add_argument(
        "--output",
        default=None,
        help="audio file"
    )

    parser.add_argument(
        "--format",
        default="wav",
        choices=["wav", "mp3", "aac"]
    )

    args = parser.parse_args()

    extractor = AudioExtractor()

    extractor.extract_audio(
        args.input,
        args.output,
        args.format
    )


if __name__ == "__main__":
    main()
```

运行：

```
python cli.py \
  --input video.webm \
  --format wav
```

---

# 七、Python调用方式

示例：

```python
from extractor import AudioExtractor

extractor = AudioExtractor()

extractor.extract_audio(
    "test.webm",
    "audio.wav",
    "wav"
)
```

---

# 八、支持批量处理（扩展）

示例：

```python
from pathlib import Path
from extractor import AudioExtractor

extractor = AudioExtractor()

folder = Path("videos")

for video in folder.glob("*"):
    if video.suffix in [".mp4", ".webm"]:
        extractor.extract_audio(
            video,
            audio_format="wav"
        )
```

---

# 九、性能优化建议

## 1）避免重新编码（最快）

如果只是提取：

```
ffmpeg -i video.mp4 -vn -acodec copy audio.aac
```

Python：

```python
cmd = [
    "ffmpeg",
    "-i", str(video_path),
    "-vn",
    "-acodec", "copy",
    str(output_path)
]
```

优势：

* 超快
* 无损
* CPU占用低

推荐用于：

* WebM → opus
* MP4 → aac

---

# 十、异常处理设计

建议捕获：

| 异常                | 场景       |
| ----------------- | -------- |
| FileNotFoundError | 文件不存在    |
| RuntimeError      | ffmpeg失败 |
| ValueError        | 格式错误     |

示例：

```python
try:
    extractor.extract_audio("test.mp4")
except Exception as e:
    print(e)
```

---

# 十一、生产级增强（推荐）

建议增加：

### 1）自动检测音频编码

```
ffprobe video.mp4
```

Python：

```python
cmd = [
    "ffprobe",
    "-v", "error",
    "-select_streams", "a:0",
    "-show_entries",
    "stream=codec_name",
    "-of", "default=noprint_wrappers=1:nokey=1",
    video
]
```

可以自动选择：

* opus
* aac
* mp3

避免转码。

---

### 2）多线程处理

```python
from concurrent.futures import ThreadPoolExecutor
```

---

### 3）大文件支持

ffmpeg 已天然支持：

* 10GB+
* 100GB+

无需额外处理。

---

# 十二、最简实现（推荐）

如果只需要核心功能：

```python
import subprocess

def extract_audio(video, audio):

    subprocess.run([
        "ffmpeg",
        "-i", video,
        "-vn",
        audio
    ])
```

调用：

```
extract_audio("a.webm", "a.wav")
```

---

# 十三、推荐最佳实践（重要）

生产环境建议：

**最佳组合：**

* ffmpeg
* subprocess
* wav输出

原因：

* 稳定
* 无依赖
* 快
* 支持所有编码

---

如果你需要，我可以给你写一个 **工业级版本（支持 10万视频处理 + 并发 + 自动检测编码）** 的完整方案。
