# Manual-first 视频剪辑便利性优化方案

## 目标

把当前分散的流程：

```bash
python mark_rallies.py
python export_segments.py
```

优化成一个稳定的主流程：

```bash
python mark_rallies.py
```

用户进入后可以完成：

- 新建或恢复视频标注
- 快速标记回合
- 复核已标片段
- 一键导出成品视频
- 自动保存 session
- 自动生成输出文件名

## 核心原则

1. 不依赖自动检测。
   自动检测之前没有稳定跑通，因此不作为主路径。先保证人工剪辑稳定可用。

2. 保留现有使用习惯。
   继续基于 `mark_rallies.py`，不重做 UI，不引入新依赖。

3. 减少脚本切换。
   把 `export_segments.py` 的导出能力合并进 `mark_rallies.py`，用户不需要记多个入口。

4. 先做闭环，再做智能化。
   等手动流程顺了，再考虑自动候选片段和半自动 review。

## Phase 1：一键导出闭环

改造 `mark_rallies.py`，在退出时如果存在片段，直接提供导出能力。

当前结束后只显示：

- 片段数量
- 总时长
- session 文件路径

优化为：

```text
Recorded 18 segments
Total highlight duration: 12m 34s
Original duration: 43m 20s
Reduction: 71.0%

Segments saved to: sessions/IMG_6884.txt
Output video: output/IMG_6884_3.mp4

Export now? [Y/n]
```

实现要点：

- 复用 `export_segments.py` 的 FFmpeg `filter_complex` 导出逻辑，或优先调用 `core.video_exporter.VideoExporter`
- 自动创建 `output/`
- 自动生成不覆盖旧文件的输出名
- 导出失败时保留 session，不丢标注结果

验收标准：

- 标注完按 `Q` 后可以直接导出
- 不再需要手动运行 `export_segments.py`
- 导出文件路径清晰显示
- 无片段时不触发导出

## Phase 2：强化 session 管理

当前已有 `sessions/{video_name}.txt`，但启动和恢复体验还可以更直接。

优化启动菜单：

```text
Badminton Video Cut

1. Continue last session
2. Open existing session
3. New video
4. Export existing session
Q. Quit
```

每个 session 显示：

```text
[18 segments] IMG_6884  highlight 12m34s  video found
[09 segments] IMG_6883  highlight 06m12s  video missing
```

实现要点：

- 读取 `# VIDEO:` 头部定位原视频
- 统计片段数量和总时长
- 视频缺失时允许重新指定路径
- session 文件里的注释行不计入片段数

验收标准：

- 打开工具即可恢复历史项目
- 不需要重新输入视频路径
- 视频移动后能重新绑定路径

## Phase 3：已标片段复核模式

这一步解决“标完以后修片麻烦”的问题，不做自动候选 review。

增强现有 LIST / PREVIEW 模式。

快捷键建议：

```text
Space      预览当前片段 / 停止预览
Enter      下一个片段
Backspace  上一个片段
U          删除当前片段
← / →      开始时间 -0.5s / +0.5s
↑ / ↓      结束时间 -0.5s / +0.5s
S          保存
E          导出
Q          退出
```

体验目标：

- 进入复核模式后自动跳到第一个片段
- 预览结束自动进入下一个片段
- 每次调整自动保存
- 删除后自动选中下一个片段
- 导出前显示统计

验收标准：

- 可以连续复核所有片段，不需要回到命令行
- 修正 start/end 后 session 文件立即更新
- 删除片段不会破坏排序

## Phase 4：导出前检查与缓冲设置

增加导出前的可控参数：

```text
Export settings:
Start padding: 0.8s
End padding:   1.2s
CRF: 18
Preset: veryfast
```

默认建议：

- 开始前补 `0.8s`
- 结束后补 `1.2s`

原因：羽毛球回合切太紧会影响观看体验，尤其是发球前和落点后。

验收标准：

- 导出应用 padding，但 session 原始时间不被永久改写
- padding 后不小于 `0s`
- 片段之间重叠时自动合并，避免重复画面

## Phase 5：统一命令入口

保留兼容入口：

```bash
python mark_rallies.py
python export_segments.py
```

推荐主入口：

```bash
python mark_rallies.py
```

后续可选接入：

```bash
badminton-cut mark
badminton-cut export
badminton-cut review
```

不要一开始就做 CLI 大重构，先把主脚本体验打通。

## 建议实施顺序

1. 把导出功能合并进 `mark_rallies.py`
2. 修 session 统计和导出 session 选择
3. 优化 LIST / PREVIEW 复核模式
4. 增加 padding 和导出前统计
5. 再考虑统一到 `badminton-cut`

## 最小可用版本

如果只做一个最小可用版本，建议实现：

- `mark_rallies.py` 退出后直接导出
- 自动生成 `output/{video_name}_{n}.mp4`
- 复用当前 session 文件
- 导出前显示片段数和总时长

这一步完成后，剪辑流程会从“两段脚本 + 手动找 session”变成“一个工具内完成闭环”。
