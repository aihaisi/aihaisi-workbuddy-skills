---
name: ffmpeg-video-pipeline-pitfalls
description: 用 ffmpeg 搭视频处理流水线时的五个高发坑——输出端 -ss 配 -c copy 会丢掉整条视频流（产出"有声无画"的废片且退出码为 0）、Windows 上 subtitles 滤镜路径被冒号切断、字幕字体名在本机不存在导致中文变方块、MSYS2 路径转换污染原生程序参数、xfade 转场的 offset 需按公式累减且音频必须同步 acrossfade。当需要裁剪/切分/拼接/加转场特效/加字幕/转码视频，或排查"剪出来的片子没有画面""字幕是方块""ffmpeg 报 original_size 解析失败""转场位置错乱"时使用。
agent_created: true
---

# ffmpeg 视频流水线的五个坑

这些坑的共同特征：**不报错、退出码 0、文件正常生成**，但产物是废的。
2026-09-28 在 Windows + ffmpeg 8.1.1 (gyan.dev full build) 上实测复现。

---

## 坑 1（致命）：输出端 `-ss` + `-c copy` 会静默丢掉整条视频流

### 症状
- 命令 exit 0，输出文件存在、体积正常、**有声音**
- 播放器打开是**黑屏 / 无画面**
- `ffprobe` 显示输出只有 `audio` 流，video 流凭空消失
- ffmpeg 日志里**没有** `Stream mapping:` 段（正常输出都会有）

### 实测对照（源：12 秒 1280x720 h264 + aac，25fps）

| 命令 | 结果 |
|---|---|
| `ffmpeg -i in.mp4 -c copy -ss 3 -to 8 out.mp4` | ❌ 只剩 audio |
| `ffmpeg -i in.mp4 -ss 3 -to 8 -c copy out.mp4` | ❌ 只剩 audio |
| `ffmpeg -i in.mp4 -c copy -ss 3 -t 5 out.mp4` | ❌ 只剩 audio |
| `ffmpeg -ss 3 -i in.mp4 -c copy out.mp4` | ✅ video+audio |
| `ffmpeg -i in.mp4 -c copy -to 8 out.mp4`（无 `-ss`） | ✅ video+audio |
| `ffmpeg -i in.mp4 -ss 3 -to 8 out.mp4`（重编码） | ✅ video+audio |

### 规律
**只要 `-ss` 出现在 `-i` 之后（输出侧 seek）且配 `-c copy`，视频流就会被整体丢弃。**
音频之所以幸存：AAC 帧极小（每帧约 23ms），几乎每帧都可作为切入点；而视频必须从**关键帧**切入，`-c copy` 无法在非关键帧处剪接，ffmpeg 找不到符合条件的视频包，于是整条流被静默丢弃，且不报错。

### 修复
把 `-ss` / `-to` / `-t` **全部移到 `-i` 之前**（输入侧 seek）：

```python
cmd = ["ffmpeg", "-y"]
if start_time: cmd += ["-ss", start_time]
if end_time:   cmd += ["-to", end_time]
if duration:   cmd += ["-t", duration]
cmd += ["-i", input_path, "-c", "copy", output_path]
```

### 附带收益（性能）
输入侧 seek 是**快速定位**，不需要从头解码文件。
反面写法（输出侧 seek + copy）会从 0 解码到切点——切片 N 段的循环调用会退化成 O(N²)，1 小时直播回放切片可能从秒级变成分钟级。

### 代价（必须知道）
输入侧 seek + `-c copy` ⇒ **切点对齐到最近的关键帧**，不是帧级精确。误差取决于源的 GOP 长度（典型 < 2 秒）。
- 直播切片 / 批量粗剪 → 可接受，且这是正确选择
- 需要帧级精确 → 改用重编码，或 `-ss` 在 `-i` 前 + 重编码（输入侧 seek 仍省去大量解码）

---

## 坑 2：Windows 上 `subtitles=` 滤镜的路径必须「转义冒号 + 单引号整体包裹」

### 症状
```
[Parsed_subtitles_0] Unable to parse "original_size" option value "Users<user>WorkBuddyClawoutputs..." as image size
[fc#-1] Error applying option 'original_size' to filter 'subtitles': Invalid argument
```
报的是 `original_size` —— **极具误导性**，与实际病因（路径）毫无字面关系。

### 实测对照

| 写法 | 结果 |
|---|---|
| `subtitles=demo/zh.srt`（相对路径） | ✅ |
| `subtitles=C:/Users/x/zh.srt` | ❌ 冒号被当参数分隔符 |
| `subtitles=C\:/Users/x/zh.srt`（只转义） | ❌ 仍被切碎 |
| `subtitles='C\:/Users/x/zh.srt'`（转义 + 单引号） | ✅ |

### 修复
```python
sub_path = str(srt_path).replace("\\", "/")          # 反斜杠 → 正斜杠
if len(sub_path) > 1 and sub_path[1] == ":":
    sub_path = sub_path[0] + "\\:" + sub_path[2:]    # 'C:' -> 'C\:'
filter_str = f"subtitles='{sub_path}':force_style='...'"
```
两道都要：`\:` 保护冒号，单引号让 filter 解析器把整串当**一个**参数。

---

## 坑 3：字幕字体名必须在本机真实存在，否则中文变方块

### 易错点：两个字体名字不同
- `Noto Sans CJK SC` —— Google CJK 大全集（`NotoSansCJKsc-Regular.otf`）
- `Noto Sans SC` —— 单独的中文子集（`NotoSansSC-VF.ttf`）

**这是两个不同的字体族名。** 写前者、装的是后者 ⇒ libass 匹配失败，静默 fallback（Windows 上常退到 Arial）⇒ 中文显示为**豆腐块**。

### 做法
- Windows 上直接用 `Microsoft YaHei`（`C:\Windows\Fonts\msyh.ttc`，必装）或 `SimHei`
- 先查本机有什么：`ls /c/Windows/Fonts | grep -iE "msyh|simhei|noto"`
- 把字体名做成可覆盖参数（如环境变量 `VEDIT_SUB_FONT`），别硬编码
- 注意：libass **找不到字体时不报错**，只 fallback。所以"命令成功"不能证明字体对了 —— 必须抽帧肉眼看（见下）

---

## 坑 4：bash/MSYS2 会把路径参数改坏后再交给原生 ffmpeg

Git Bash 会把看起来像 POSIX 路径的参数自动转换；本机该行为时有时无（`MSYS2_ARG_CONV_EXCL` 未稳定注入）。

**表现**：诊断时看到的错误信息里混入了 `PortableGit` 等无关路径片段，让人误判成程序 bug。

**对策**：
- 诊断 ffmpeg 时优先用**相对路径**（`-vf "subtitles=demo/zh.srt"`），绕开转换层
- 需要绝对路径时在 bash 里显式 `cygpath -w`
- 从 Python 脚本里 `subprocess` 直调 ffmpeg（列表参数、不经 shell）最干净，不受 MSYS 影响
- 涉及原生程序（curl/ffmpeg/ffprobe）的写法，可参考 `douyin-media-download` / `bilibili-transcript`

---

## 坑 5：`xfade` 转场有三件事必须同时做对，否则位置错乱或观感撕裂

2026-09-29 实测（ffmpeg 8.1.1，3 段各 5s 素材，转场 1s）。

### 5.1 offset 要自己算，且随转场数累减

`xfade` 不知道"上一段接完了没" —— `offset` 是**在已合成时间轴上的绝对起点**，不是相对上一段的偏移。

N 段素材、每段 d、转场时长 t：

```
第 k 个转场的 offset = (d₁ + … + d_k) − k × t
  第 1 个: d − t
  第 2 个: 2d − 2t
总时长 = Σd − (N − 1) × t
```

实测：3 段各 5s、t=1s ⇒ `offset=4` / `offset=8`，输出 **13.05s**（= 15 − 2）。✓

**高发错误**：第 2 个转场照抄 `offset = 5 − 1 = 4`，转场在错误位置触发，画面直接跳变。

### 5.2 音频必须同步 `acrossfade`，否则声画撕裂

`xfade` **只处理视频**。音频不管 ⇒ 画面柔和过渡 1 秒、声音在同一帧"啪"地切断，观感极差。

```bash
[0:a][1:a]acrossfade=d=1:c1=tri:c2=tri[a01];
[a01][2:a]acrossfade=d=1:c1=tri:c2=tri[aout]
```

`d` 必须与对应 `xfade` 的 `duration` 一致。
**副作用**：音频被重新混合，所以转场合成时 `-c:a copy` **不可用**，必须重编码音频（`-c:a aac`）。

### 5.3 输入必须预先统一四项，否则报错或隐蔽错位

```bash
[0:v]scale=1280:720,format=yuv420p,fps=30,settb=AVTB[v0]
```

**分辨率、像素格式、帧率、时间基（`settb`）四项都要一致。**
时间基不一致时 offset 的含义会漂移 —— 这是最隐蔽的一种错位，表现是"转场大概在正确位置但偏几帧"。

### 参考：59 种转场

`ffmpeg -h filter=xfade` 实测 59 种：`fade` / `fadeblack` / `fadewhite` / `dissolve` / `wipe*`（4 向）/ `slide*`（4 向）/ `circleopen` `circleclose` / `radial` / `smooth*` / `pixelize` / `zoomin` / `hlslice` `hrslice` `vuslice` `hdslice` / `squeeze*` / `reveal*`（4 向）/ `cover*`（4 向）/ `diag*` / `wind*` / `rectcrop` / `distance` 等。

### 常用特效滤镜组合（实测可用）

| 效果 | 滤镜 |
|---|---|
| 胶片感 | `eq=contrast=1.15:saturation=0.85,vignette=angle=PI/4.5,noise=alls=8:allf=t` |
| 冷色调 | `colorbalance=rs=-0.22:bs=0.28,eq=contrast=1.12` |
| 色差／故障 | `rgbashift=rh=6:bh=-6` |
| 锐化 | `unsharp=5:5:0.6` |
| 模糊 | `gblur=sigma=2` |
| 多效果对比拼图 | `[0][1][2][3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0` |

**注意**：`eq` / `colorbalance` 这类色彩调整在 **SMPTE 纯色测试图（`smptebars`）上几乎看不出差别** —— 色彩偏移会被饱和原色块掩盖。验证调色效果要用**细节丰富、有肤色/渐变的真实素材**，否则会误判成"滤镜没生效"。

---

## 验证纪律（最重要的一条）

**不要用 exit code、文件存在、文件体积来判断 ffmpeg 成功。** 上述坑全部满足"exit 0 + 文件正常"，产物却是废的。

必须做的三层验证：

```bash
# 1) 流类型 —— 一眼看出视频流有没有丢
ffprobe -v error -show_entries stream=codec_type -of csv=p=0 out.mp4
# 期望: video\naudio ...  只有 audio 就是中招了

# 2) 时长 + 分辨率（确认裁剪/缩放真的生效）
ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 out.mp4

# 3) 字幕类输出必须抽帧肉眼确认（字体 fallback 不报错）
ffmpeg -y -loglevel error -ss 1 -i out.mp4 -frames:v 1 frame.png
# 然后用 Read 看这张 PNG，确认中文正常渲染而非方块
```

批量验证时用循环 + `tr '\n' '+'` 把多行流类型压成一行，便于一眼扫出哪一个缺 video。

---

## 别踩的坑（写日志/报告时）
本机 PowerShell 工具不回传 stdout，所以上述验证命令一律走 **Bash + 修复 PATH**，或让脚本自己写文件再用 Read 读回。
