# -*- coding: utf-8 -*-
"""口语录音客观指标实测：语速 / 停顿 / 响度 / 口语词频 / 段落占比

用法：
    python metrics.py <音频路径> [逐字稿json]

不传 json 时只做音频侧指标（停顿、响度）。
传 json（transcribe.py 的产物）时额外算语速、字数、口语词频、段间间隔。
"""
import json
import os
import re
import subprocess
import sys

FILLERS = ["然后", "这个", "就是", "其实", "比较", "所以说", "但是", "那个", "非常"]

# 演讲舒适区参考值，用于给出判断
REF = {
    "speech_rate": (180, 220, "字/分钟", "中文演讲舒适区"),
    "loudness": (-19, -16, "LUFS", "整体响度"),
}


def run_ffmpeg(args):
    """跑 ffmpeg 并返回 stderr（ffmpeg 的诊断信息走 stderr）"""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats"] + args,
                       capture_output=True, text=True, errors="replace")
    return p.stderr


def pauses(audio, noise_db=-32, min_dur=0.35):
    """静音段检测 —— 对应人讲话时的停顿"""
    err = run_ffmpeg([
        "-i", audio,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ])
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", err)]
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", err)]
    return starts, durs


def loudness(audio):
    """EBU R128 整体响度与动态范围"""
    err = run_ffmpeg(["-i", audio, "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    out = {}
    m = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", err)
    if m:
        out["integrated_lufs"] = float(m.group(1))
    m = re.search(r"LRA:\s*(-?[\d.]+)\s*LU", err)
    if m:
        out["lra_lu"] = float(m.group(1))
    return out


def verdict_speech_rate(v):
    lo, hi, _, _ = REF["speech_rate"]
    if v < lo:
        return "偏慢"
    if v > hi:
        return f"偏快约 {round((v - hi) / hi * 100)}%"
    return "在舒适区"


def verdict_loudness(v):
    lo, hi, _, _ = REF["loudness"]
    if v < lo:
        return "偏低（句尾易丢音）"
    if v > hi:
        return "偏高"
    return "正常"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    audio = os.path.abspath(sys.argv[1])
    jpath = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else None

    print("=" * 60)
    print("音频侧指标")
    print("=" * 60)

    starts, durs = pauses(audio)
    if durs:
        print(f"停顿（>{0.35}s @ -32dB）：{len(durs)} 处")
        print(f"  最长停顿：{max(durs):.2f}s")
        print(f"  平均停顿：{sum(durs) / len(durs):.2f}s")
        print(f"  停顿总时长：{sum(durs):.1f}s")
        print("  提示：段落之间应有 1.5~2s 留白；若最长停顿不足，说明缺少换气设计。")
    else:
        print("停顿：未检出明显停顿（可能全程无留白，或阈值需调整）")

    loud = loudness(audio)
    if "integrated_lufs" in loud:
        v = loud["integrated_lufs"]
        print(f"整体响度：{v} LUFS —— {verdict_loudness(v)}（参考 -19 ~ -16）")
    if "lra_lu" in loud:
        v = loud["lra_lu"]
        print(f"动态范围：{v} LU —— {'起伏偏大' if v > 9 else '正常'}")

    if not jpath:
        return

    print()
    print("=" * 60)
    print("文本侧指标")
    print("=" * 60)

    with open(jpath, encoding="utf-8") as f:
        data = json.load(f)
    segs = data["segments"]
    if not segs:
        print("逐字稿为空")
        return

    text = "".join(s["text"] for s in segs)
    no_punct = re.sub(r"[，。！？、,.!? \n\t]", "", text)
    spoken = segs[-1]["end"] - segs[0]["start"]

    print(f"分段数：{len(segs)}")
    print(f"讲话区间：{segs[0]['start']:.1f}s – {segs[-1]['end']:.1f}s，净讲话 {spoken:.1f}s（{spoken / 60:.2f} 分钟）")
    print(f"有效字数：{len(no_punct)} 字（不含标点）")

    rate = len(no_punct) / (spoken / 60)
    print(f"语速：{rate:.0f} 字/分钟 —— {verdict_speech_rate(rate)}")

    gaps = [round(segs[i + 1]["start"] - segs[i]["end"], 2) for i in range(len(segs) - 1)]
    gaps = [g for g in gaps if g > 0]
    if gaps:
        print(f"段间间隔 r>0.3s：{sum(1 for g in gaps if g > 0.3)} 处，最大 {max(gaps):.2f}s")

    print("\n高频口语词：")
    counts = [(w, text.count(w)) for w in FILLERS]
    for w, c in sorted(counts, key=lambda x: -x[1]):
        if c:
            print(f"  {w} × {c}")

    print("\n提示：用段落占比看结构。参考——汇报类场合「成果」应占 >50%，"
          "「困难/过程」占比过高是典型结构病。")


if __name__ == "__main__":
    main()
