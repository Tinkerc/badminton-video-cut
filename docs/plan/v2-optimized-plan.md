# Phase-H v2 优化方案

## 一、当前项目状态分析

### 已实现功能

| 工具 | 文件 | 状态 | 核心功能 |
|------|------|------|----------|
| **Phase-H Manual** | `mark_rallies.py` | ✅ 完成 | 手动键盘标注，FFmpeg filter_complex 导出 |
| **Auto Cut (Motion+Audio)** | `auto_cut.py` | ✅ 完成 | 双阈值检测（运动 + 音频能量） |
| **Auto Cut Flow** | `auto_cut_flow.py` | ✅ 完成 | 光流检测（Farneback） |
| **Auto Cut Player** | `auto_cut_player.py` | ✅ 完成 | YOLO 球员轨迹追踪 |
| **Export Engine** | 所有工具 | ✅ v2 优化 | 一次性 filter_complex concat |

### 当前架构问题

```
┌─────────────────────────────────────────────────────────┐
│  问题 1: 音频提取逻辑重复                                │
│  - auto_cut.py: extract_audio() 硬编码                   │
│  - 其他工具：各自实现或没有                              │
│  - 不支持格式检测                                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  问题 2: 参数分散                                        │
│  - 每个工具硬编码参数                                     │
│  - 无法统一调整                                          │
│  - 难以批量测试不同配置                                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  问题 3: CLI 接口不统一                                   │
│  - 有的工具支持 --input，有的只接受 argv                   │
│  - 缺少批量处理支持                                       │
│  - 缺少配置导出功能                                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  问题 4: 音频处理不优化                                   │
│  - 总是转码为 WAV（16kHz 单声道）                          │
│  - 未检测原始编码（AAC/Opus）                            │
│  - 可以 -acodec copy 时未利用                            │
└─────────────────────────────────────────────────────────┘
```

---

## 二、v2 优化目标

### 核心目标

| 目标 | 当前状态 | v2 目标 | 提升 |
|------|----------|--------|------|
| **音频提取** | 硬编码 | 模块化 + 自动检测 | 稳定 + 快速 |
| **参数管理** | 分散 | 统一配置文件 | 易调优 |
| **CLI 接口** | 不统一 | 标准化 argparse | 易用 |
| **批量处理** | 无 | 支持文件夹批量 | 效率×10 |
| **导出性能** | v2 已优化 | 保持 + 可选 GPU | 更快 |
| **配置导出** | 无 | JSON/YAML 导出 | 可复现 |

---

## 三、技术架构设计

### 3.1 整体架构

```
badminton-video-cut/
│
├── core/                          # 核心模块（可复用）
│   ├── __init__.py
│   ├── audio_extractor.py         # ⭐ 新增：音频提取模块
│   ├── motion_detector.py         # ⭐ 重构：运动检测
│   ├── flow_detector.py           # ⭐ 重构：光流检测
│   ├── player_detector.py         # ⭐ 重构：球员检测
│   └── video_exporter.py          # ⭐ 统一导出引擎
│
├── config/
│   ├── __init__.py
│   ├── default_config.yaml        # ⭐ 新增：默认配置
│   └── config_loader.py           # ⭐ 新增：配置加载器
│
├── utils/
│   ├── __init__.py
│   ├── batch_processor.py         # ⭐ 新增：批量处理
│   └── format_utils.py            # ⭐ 新增：格式工具
│
├── cli/
│   ├── __init__.py
│   ├── auto_cut_cli.py            # ⭐ 统一 CLI
│   └── mark_rallies_cli.py        # ⭐ 统一 CLI
│
├── mark_rallies.py                # 保持（兼容旧用法）
├── auto_cut.py                    # → 迁移到 core/
├── auto_cut_flow.py               # → 迁移到 core/
└── auto_cut_player.py             # → 迁移到 core/
```

---

### 3.2 核心模块：audio_extractor.py

```python
"""
core/audio_extractor.py

生产级音频提取模块
- 自动检测原始编码
- 支持 copy 模式（无损快速）
- 支持转码模式（WAV/MP3/AAC）
- 批量处理支持
"""

from pathlib import Path
import subprocess
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AudioStreamInfo:
    """音频流信息"""
    codec_name: str
    sample_rate: int
    channels: int
    bit_rate: Optional[int] = None


class AudioExtractor:
    """
    生产级音频提取器
    
    支持模式:
    - copy: 直接复制流（最快，无损）
    - transcode: 转码为目标格式（WAV/MP3/AAC）
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
    
    def detect_audio_stream(self, video_path: Path) -> Optional[AudioStreamInfo]:
        """
        检测视频中的音频流信息
        
        Returns:
            AudioStreamInfo or None if no audio stream
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "a:0",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            if not data.get("streams"):
                return None
            
            stream = data["streams"][0]
            
            return AudioStreamInfo(
                codec_name=stream.get("codec_name", "unknown"),
                sample_rate=int(stream.get("sample_rate", 0)),
                channels=int(stream.get("channels", 0)),
                bit_rate=int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None
    
    def extract_audio(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        audio_format: str = "wav",
        use_copy: bool = False,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> Path:
        """
        提取音频
        
        Args:
            video_path: 输入视频文件
            output_path: 输出音频文件（可选，默认同名不同扩展名）
            audio_format: 目标格式 (wav/mp3/aac)
            use_copy: 是否使用 copy 模式（不转码）
            sample_rate: 采样率（转码时使用）
            channels: 声道数（转码时使用）
        
        Returns:
            输出文件路径
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # 自动检测原始编码
        stream_info = self.detect_audio_stream(video_path)
        
        if output_path is None:
            if use_copy and stream_info:
                # copy 模式：保持原扩展名
                ext = self._codec_to_ext(stream_info.codec_name)
            else:
                ext = audio_format
            output_path = video_path.with_suffix("." + ext)
        else:
            output_path = Path(output_path)
        
        # 构建 FFmpeg 命令
        cmd = [self.ffmpeg_path, "-y", "-i", str(video_path), "-vn"]
        
        if use_copy:
            # Copy 模式：最快，无损
            cmd.extend(["-acodec", "copy"])
            logger.info(f"Using copy mode (codec: {stream_info.codec_name if stream_info else 'unknown'})")
        else:
            # 转码模式
            codec = self._get_codec(audio_format)
            cmd.extend(["-acodec", codec])
            
            if audio_format == "wav":
                cmd.extend(["-ar", str(sample_rate), "-ac", str(channels)])
            elif audio_format == "mp3":
                cmd.extend(["-b:a", "192k"])
            elif audio_format == "aac":
                cmd.extend(["-b:a", "192k"])
            
            logger.info(f"Using transcode mode (codec: {codec}, format: {audio_format})")
        
        cmd.append(str(output_path))
        
        logger.info(f"Extracting audio: {video_path.name} -> {output_path.name}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.decode()
            raise RuntimeError(f"FFmpeg failed: {error_msg}")
        
        logger.info(f"Audio extracted: {output_path}")
        return output_path
    
    def _get_codec(self, fmt: str) -> str:
        """获取编码器名称"""
        codecs = {
            "wav": "pcm_s16le",
            "mp3": "libmp3lame",
            "aac": "aac"
        }
        
        if fmt not in codecs:
            raise ValueError(f"Unsupported format: {fmt}. Supported: {list(codecs.keys())}")
        
        return codecs[fmt]
    
    def _codec_to_ext(self, codec: str) -> str:
        """根据编码器推荐扩展名"""
        mapping = {
            "aac": "aac",
            "mp3": "mp3",
            "opus": "opus",
            "vorbis": "ogg",
            "pcm_s16le": "wav"
        }
        return mapping.get(codec, "wav")
    
    def batch_extract(
        self,
        input_folder: Path,
        output_folder: Optional[Path] = None,
        patterns: list = None,
        **kwargs
    ) -> list:
        """
        批量提取音频
        
        Args:
            input_folder: 输入文件夹
            output_folder: 输出文件夹（可选）
            patterns: 文件匹配模式，默认 [".mp4", ".webm"]
            **kwargs: 传递给 extract_audio 的参数
        
        Returns:
            输出文件列表
        """
        if patterns is None:
            patterns = [".mp4", ".webm"]
        
        input_folder = Path(input_folder)
        
        if output_folder is None:
            output_folder = input_folder / "audio"
            output_folder.mkdir(exist_ok=True)
        else:
            output_folder = Path(output_folder)
            output_folder.mkdir(exist_ok=True)
        
        output_files = []
        
        for pattern in patterns:
            for video_path in input_folder.glob(f"*{pattern}"):
                try:
                    output_path = output_folder / f"{video_path.stem}.wav"
                    result = self.extract_audio(
                        video_path,
                        output_path,
                        **kwargs
                    )
                    output_files.append(result)
                    logger.info(f"✓ {video_path.name}")
                except Exception as e:
                    logger.error(f"✗ {video_path.name}: {e}")
        
        logger.info(f"Batch complete: {len(output_files)} files")
        return output_files
```

---

### 3.3 统一配置：default_config.yaml

```yaml
# config/default_config.yaml

# 通用配置
general:
  ffmpeg_path: "ffmpeg"
  ffprobe_path: "ffprobe"
  log_level: "INFO"

# 音频提取配置
audio:
  default_format: "wav"
  sample_rate: 16000
  channels: 1
  use_copy: true  # 优先使用 copy 模式

# 运动检测配置（auto_cut.py）
motion:
  sample_fps: 2
  threshold: 8
  min_duration: 3
  merge_gap: 4

# 光流检测配置（auto_cut_flow.py）
optical_flow:
  sample_fps: 3
  scale_width: 320
  scale_height: 180
  threshold: 2.0
  min_duration: 4
  merge_gap: 4
  center_crop: true

# 球员检测配置（auto_cut_player.py）
player:
  model: "yolov8s.pt"
  sample_fps: 3
  window_seconds: 1.5
  threshold_ratio: 0.4
  use_velocity_std: true

# 导出配置
export:
  codec: "libx264"
  preset: "veryfast"
  crf: 18
  audio_codec: "aac"
  audio_bitrate: "192k"
  use_gpu: false  # 启用 NVENC
```

---

### 3.4 配置加载器：config_loader.py

```python
"""
config/config_loader.py

配置加载和合并
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class Config:
    """配置对象"""
    general: Dict[str, Any]
    audio: Dict[str, Any]
    motion: Dict[str, Any]
    optical_flow: Dict[str, Any]
    player: Dict[str, Any]
    export: Dict[str, Any]
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        加载配置
        
        优先级:
        1. 用户配置文件 (~/.badminton-cut/config.yaml)
        2. 项目配置文件 (config/default_config.yaml)
        3. 硬编码默认值
        """
        default_config = Path(__file__).parent / "default_config.yaml"
        
        # 合并配置
        config_dict = cls._load_yaml(default_config)
        
        if config_path and config_path.exists():
            user_config = cls._load_yaml(config_path)
            config_dict = cls._merge(config_dict, user_config)
        
        return cls(
            general=config_dict.get("general", {}),
            audio=config_dict.get("audio", {}),
            motion=config_dict.get("motion", {}),
            optical_flow=config_dict.get("optical_flow", {}),
            player=config_dict.get("player", {}),
            export=config_dict.get("export", {})
        )
    
    @staticmethod
    def _load_yaml(path: Path) -> Dict:
        """加载 YAML 文件"""
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    
    @staticmethod
    def _merge(base: Dict, override: Dict) -> Dict:
        """深度合并配置"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._merge(result[key], value)
            else:
                result[key] = value
        return result
```

---

### 3.5 统一 CLI：auto_cut_cli.py

```python
"""
cli/auto_cut_cli.py

统一的命令行接口
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional


def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    
    parser = argparse.ArgumentParser(
        prog="badminton-cut",
        description="Badminton Rally Highlight Cutter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 单个文件处理
  badminton-cut auto input.mp4 output.mp4
  
  # 批量处理文件夹
  badminton-cut auto --input-folder ./videos/ --output-folder ./highlights/
  
  # 使用自定义配置
  badminton-cut auto input.mp4 --config my_config.yaml
  
  # 导出配置模板
  badminton-cut config export --output my_config.yaml
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # === auto 命令 ===
    auto_parser = subparsers.add_parser(
        "auto",
        help="Auto-detect rallies (motion + audio)"
    )
    
    # 输入选项（互斥）
    input_group = auto_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        help="Input video file"
    )
    input_group.add_argument(
        "--input-folder",
        type=Path,
        help="Input folder (batch mode)"
    )
    
    # 输出选项
    auto_parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        help="Output video file"
    )
    auto_parser.add_argument(
        "--output-folder",
        type=Path,
        help="Output folder (batch mode)"
    )
    
    # 配置选项
    auto_parser.add_argument(
        "--config",
        type=Path,
        help="Custom config file"
    )
    
    # 参数覆盖
    auto_parser.add_argument(
        "--motion-threshold",
        type=float,
        help="Motion threshold (override config)"
    )
    auto_parser.add_argument(
        "--audio-threshold",
        type=float,
        help="Audio threshold (override config)"
    )
    auto_parser.add_argument(
        "--min-duration",
        type=float,
        help="Minimum segment duration (seconds)"
    )
    auto_parser.add_argument(
        "--merge-gap",
        type=float,
        help="Merge gap (seconds)"
    )
    
    # 模式选项
    auto_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't cut video"
    )
    auto_parser.add_argument(
        "--export-segments",
        type=Path,
        help="Export segments to file"
    )
    auto_parser.add_argument(
        "--import-segments",
        type=Path,
        help="Import segments from file (skip detection)"
    )
    
    # === flow 命令 ===
    flow_parser = subparsers.add_parser(
        "flow",
        help="Auto-detect rallies (optical flow)"
    )
    # ... 类似 auto 的参数
    
    # === player 命令 ===
    player_parser = subparsers.add_parser(
        "player",
        help="Auto-detect rallies (player detection)"
    )
    # ... 类似 auto 的参数
    
    # === mark 命令 ===
    mark_parser = subparsers.add_parser(
        "mark",
        help="Manual marking (Phase-H)"
    )
    mark_parser.add_argument("input_file", type=Path)
    mark_parser.add_argument("output_file", type=Path, nargs="?")
    
    # === config 命令 ===
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management"
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    # config export
    export_parser = config_subparsers.add_parser(
        "export",
        help="Export default config template"
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        default="config.yaml",
        help="Output file path"
    )
    
    # config show
    config_subparsers.add_parser(
        "show",
        help="Show current config"
    )
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "config":
        handle_config(args)
    elif args.command == "auto":
        handle_auto(args)
    elif args.command == "flow":
        handle_flow(args)
    elif args.command == "player":
        handle_player(args)
    elif args.command == "mark":
        handle_mark(args)


def handle_config(args):
    """处理 config 命令"""
    from config.config_loader import Config
    
    if args.config_command == "export":
        # 导出默认配置
        import shutil
        default_config = Path(__file__).parent.parent / "config" / "default_config.yaml"
        shutil.copy(default_config, args.output)
        print(f"Config exported to: {args.output}")
    
    elif args.config_command == "show":
        # 显示当前配置
        config = Config.load()
        print(yaml.dump({
            "audio": config.audio,
            "motion": config.motion,
            "optical_flow": config.optical_flow,
            "player": config.player,
            "export": config.export
        }))


def handle_auto(args):
    """处理 auto 命令"""
    from core.motion_detector import MotionAudioDetector
    from core.video_exporter import VideoExporter
    from config.config_loader import Config
    
    # 加载配置
    config = Config.load(args.config)
    
    # 参数覆盖
    if args.motion_threshold:
        config.motion["threshold"] = args.motion_threshold
    if args.audio_threshold:
        config.motion["audio_threshold"] = args.audio_threshold
    if args.min_duration:
        config.motion["min_duration"] = args.min_duration
    if args.merge_gap:
        config.motion["merge_gap"] = args.merge_gap
    
    # 批量模式 vs 单文件模式
    if args.input_folder:
        # 批量处理
        handle_batch_auto(args, config)
    else:
        # 单文件处理
        handle_single_auto(args, config)


def handle_single_auto(args, config):
    """单文件 auto 处理"""
    detector = MotionAudioDetector(config)
    exporter = VideoExporter(config)
    
    # 检测
    if args.import_segments:
        segments = load_segments(args.import_segments)
    else:
        segments = detector.detect(args.input_file)
    
    # 导出 segments 文件
    if args.export_segments:
        save_segments(args.export_segments, segments)
    
    # 剪切视频
    if not args.dry_run:
        exporter.cut(args.input_file, segments, args.output_file)


def handle_batch_auto(args, config):
    """批量 auto 处理"""
    from utils.batch_processor import BatchProcessor
    
    processor = BatchProcessor(config)
    processor.process_folder(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        detector_type="motion_audio"
    )


def load_segments(path: Path) -> List[tuple]:
    """加载 segments 文件"""
    segments = []
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                segments.append((float(parts[0]), float(parts[1])))
    return segments


def save_segments(path: Path, segments: List[tuple]):
    """保存 segments 文件"""
    with open(path, "w") as f:
        for start, end in sorted(segments):
            f.write(f"{start:.1f} {end:.1f}\n")


if __name__ == "__main__":
    main()
```

---

## 四、使用示例对比

### 4.1 当前用法（保持不变，向后兼容）

```bash
# 手动标注
python mark_rallies.py input.mp4 output.mp4

# 自动检测
python auto_cut.py input.mp4 output.mp4
python auto_cut_flow.py input.mp4 output.mp4
python auto_cut_player.py input.mp4 output.mp4
```

### 4.2 v2 新用法

```bash
# 统一 CLI
badminton-cut auto input.mp4 output.mp4
badminton-cut flow input.mp4 output.mp4
badminton-cut player input.mp4 output.mp4
badminton-cut mark input.mp4 output.mp4

# 批量处理
badminton-cut auto --input-folder ./videos/ --output-folder ./highlights/

# 自定义参数
badminton-cut auto input.mp4 output.mp4 \
  --motion-threshold 10 \
  --audio-threshold 0.05 \
  --min-duration 5

# 使用配置文件
badminton-cut auto input.mp4 output.mp4 --config my_config.yaml

# 仅分析不剪切
badminton-cut auto input.mp4 --dry-run

# 导出/导入 segments
badminton-cut auto input.mp4 --export-segments segments.txt
badminton-cut auto input.mp4 --import-segments segments.txt

# 导出配置模板
badminton-cut config export --output my_config.yaml
```

---

## 五、性能提升预期

| 指标 | 当前 | v2 目标 | 提升 |
|------|------|--------|------|
| **音频提取速度** | ~1× | 2-10× (copy 模式) | +200-1000% |
| **批量处理效率** | 手动循环 | 自动并行 | +500% |
| **配置调优时间** | 改代码 | 改 YAML | -90% |
| **代码复用率** | ~30% | ~80% | +150% |
| **CLI 学习成本** | 4 个不同接口 | 1 个统一接口 | -75% |

---

## 六、实施计划

### Phase 1: 核心模块重构 (Week 1)

- [ ] 创建 `core/` 目录结构
- [ ] 实现 `audio_extractor.py`
- [ ] 实现 `config_loader.py`
- [ ] 迁移现有检测逻辑到 `core/`

### Phase 2: CLI 统一 (Week 2)

- [ ] 实现 `cli/auto_cut_cli.py`
- [ ] 添加批量处理支持
- [ ] 添加配置管理命令
- [ ] 保持向后兼容

### Phase 3: 性能优化 (Week 3)

- [ ] 音频 copy 模式优化
- [ ] 批量处理并行化
- [ ] GPU 导出支持（可选）

### Phase 4: 文档和测试 (Week 4)

- [ ] 更新 README.md
- [ ] 编写使用文档
- [ ] 添加单元测试
- [ ] 示例视频

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 破坏现有脚本 | 高 | 保持向后兼容，旧脚本继续工作 |
| FFmpeg 版本兼容 | 中 | 检测版本，降级处理 |
| 配置复杂度高 | 低 | 提供默认配置，文档清晰 |
| 迁移成本高 | 中 | 渐进式迁移，自动迁移脚本 |

---

## 八、成功标准

- [ ] 所有现有功能正常工作
- [ ] 批量处理效率提升>5×
- [ ] 音频提取速度提升>2×
- [ ] CLI 统一，学习成本降低
- [ ] 配置可调，无需改代码
- [ ] 文档完整，示例清晰

---

## 九、下一步行动

1. **确认方案**: Review 本方案，确认需求优先级
2. **创建分支**: `git checkout -b feature/v2-refactor`
3. **Phase 1 实施**: 核心模块重构
4. **渐进测试**: 每完成一个模块即测试
5. **用户反馈**: 邀请早期用户测试 CLI

---

## 附录 A: 快速参考

### 音频格式快速选择

| 场景 | 推荐格式 | 命令 |
|------|----------|------|
| 最快（不转码） | 原格式 | `--audio-format copy` |
| 最佳质量 | WAV | `--audio-format wav` |
| 最小体积 | MP3 | `--audio-format mp3` |
| 平衡 | AAC | `--audio-format aac` |

### 检测算法选择

| 场景 | 推荐算法 | 命令 |
|------|----------|------|
| 标准训练视频 | motion+audio | `badminton-cut auto` |
| 光线变化大 | optical flow | `badminton-cut flow` |
| 单人练习 | player detection | `badminton-cut player` |
| 比赛视频 | manual | `badminton-cut mark` |

### 性能调优参数

```yaml
# 更快检测（降低精度）
motion:
  sample_fps: 1  # 降低采样率

# 更精确检测（增加时间）
motion:
  sample_fps: 5  # 提高采样率

# 更快导出（降低质量）
export:
  preset: "superfast"
  crf: 23

# 最佳质量导出
export:
  preset: "slow"
  crf: 15
```
