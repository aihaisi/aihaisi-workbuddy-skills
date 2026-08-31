---
name: douyin-media-download
description: 下载抖音作品（视频/图文/实况图）并产出 MP4 + 循环 GIF。当用户发来抖音链接（www.douyin.com/video/、/note/、搜索页带 modal_id、v.douyin.com 短链、分享口令文本）、要求"下载这个抖音视频"、"转成 GIF/动图"、"扒抖音素材"时使用。基于实测管线：Chrome headless 渲染 → 特征抽直链 → 即取即下 → ffprobe 断言 → 转 GIF → 归档。
---

# Douyin Media Download

下载抖音作品为 MP4（带声音）+ 循环 GIF，按 `<根>/video/<作品ID>.mp4` + `<根>/gif/<作品ID>.gif` 归档（默认根 `D:\douyinVideo`）。

## 快速开始

```bash
bash scripts/dy_fetch.sh "https://www.douyin.com/jingxuan/search/xxx?modal_id=7435228944242117940&type=general" /d/douyinVideo
# 也接受: /video/<id> 链接、v.douyin.com 短链、分享口令文本、裸作品ID
```

脚本覆盖纯视频作品的全流程。返回非零或日志报错时，按下方「排障」处理；涉及图文/实况图时读 `references/forms.md`。

## 管线原理（为什么这么做）

1. **curl 直抓只能拿到空壳**（~72KB，无数据）——数据靠 JS 异步注水，headless 渲染是必经之路。
2. Chrome headless 一次渲染出完整 DOM：`--headless=new --disable-gpu --user-data-dir=<临时目录> --virtual-time-budget=15000 --timeout=30000 --dump-dom`。
3. 签名直链藏在渲染后 DOM 里。**按特征抽，不按位置抽**：grep `douyinvod` 域名的 `<source src>` / playAddr / downloadUrlList。数据所在的结构每次会变（曾见过 `<video><source>` 标签、`_ROUTER_DATA`、script 块），但域名特征稳定。
4. **URL 里的 hex 段（如 `/6a9563a9/`）是过期时间戳**，几分钟内失效——解析完必须立刻下载，不能缓存直链。
5. 下载必须带 `Referer: https://www.douyin.com/` + 浏览器 UA。
6. **ffprobe 强制断言视频流存在**：第一个 playAddr 可能是纯音频 M4A（背景曲坑），无视频流就换下一条直链。
7. 转 GIF 用 palettegen 两段式（`palettegen=stats_mode=diff` + `paletteuse`）。体积经验值：360px/12fps ≈ 1.4MB/秒；**时长 >8s 自动降到 320px/10fps**，>15s 考虑截段，全长 GIF 必然 10MB+。

## 环境依赖（Windows 实测）

- Chrome：`C:/Program Files/Google/Chrome/Application/chrome.exe`
- ffmpeg/ffprobe 8.x（Git Bash 环境直接可用）
- 网络：douyin.com 可直连

## 排障

| 症状 | 处理 |
|---|---|
| DOM 为空 / 渲染失败 | user-data-dir 必须指向全新临时目录（与日常 Chrome 抢 profile 会锁死）；加大 `--virtual-time-budget` 重试一次 |
| 无 douyinvod 直链 | 页面可能触发验证码或需登录；换 UA、加间隔后再试；批量抓取间隔 ≥ 数十秒 |
| 下载 403 | 签名已过期，重新渲染重新抽，别复用旧直链 |
| 全部直链无视频流 | 是音频坑/图文形态，读 `references/forms.md` 判别形态 |
| 直链抽到了但形态是图文 | `references/forms.md` 有 livePhoto / 图+视频 / 多图的处理判别 |

## 边界

- 个人用途、小量下载。批量/商用/去水印二次分发是另一条法律风险线，不做。
- 无水印地址不稳定可得，不承诺。
