---
name: bilibili-transcript
description: B 站视频口播转文字：短链/完整链接/BV 号 → 元信息 → 音频流 → 本地 Whisper 转写。当用户发来 B 站链接并要求"分析视频/总结视频/视频里说了什么/转写"时使用。
agent_created: true
---

# Bilibili 视频转写

把 B 站视频的口播内容转成带时间戳的文本，用于内容分析、总结、事实核查。

## 一键用法

```bash
bash {baseDir}/scripts/bili_transcript.sh "<链接或BV号>" [输出txt路径]
```

支持：`b23.tv` 短链、完整视频页链接、裸 `BV` 号。输出默认 `bili_<BV>.txt`（当前目录）。

## 管线（四步，全部已验证）

1. **短链解析**：`curl -L` 跟 302 拿真实地址，正则提 `BV[0-9A-Za-z]{10}`
2. **元信息**：`api.bilibili.com/x/web-interface/view?bvid=` → 标题/UP主/时长/**cid**（公开接口，无需登录）
3. **音频流**：`api.bilibili.com/x/player/playurl?bvid=&cid=&fnval=16` → `data.dash.audio[0].baseUrl`；下载必须带 `Referer: https://www.bilibili.com/`，流地址有时效**即取即下**，`ffprobe` 验证
4. **本地转写**：faster-whisper `small` int8 CPU，2 分钟音频约 1-2 分钟出稿

## 依赖与环境（一次性）

- ffmpeg/ffprobe、curl（系统自带）
- faster-whisper 装在托管 venv：`C:/Users/17876/.workbuddy/binaries/python/envs/default/`
  安装命令：`<venv>/Scripts/pip.exe install faster-whisper`
- 模型下载走 `HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1`（脚本内已设）。
  **坑**：国内网络直连 HuggingFace 的 xet 下载通道会 401，必须关 xet + 换镜像；模型缓存约 500MB（首次自动下载）

## 边界

- 无登录状态下拿不到 B 站官方字幕/AI 字幕（`view/conclusion/get` 返回 -403），所以走音频转写而非字幕接口
- 采样 `small` 模型对口语够用，专有名词可能错（如"潜意识"被转成"前衣室"），分析时需人工校对关键句
- 仅转写口播，画面文字（PPT/字幕贴图）不包含
- 长视频（>30 分钟）建议换 `medium` 模型或分段，CPU 耗时约实时一半
