# -*- coding: utf-8 -*-
"""动效密度画像 —— 用「相邻帧差异」的分布，量化回答「为什么这条片像 PPT」。

思路：把视频按 5fps 抽帧、缩到 320 宽灰度，算相邻帧的平均绝对差（MAD）。
  · 中位数高    = 画面**常年**在变化（元素持续运动）
  · 只有少数尖峰 = 偶尔换一屏，其余时间静止（= PPT 的节奏）
  · p10 极低    = 有大量"几乎没动"的帧
  · 静止比高    = 近静止帧（MAD < 0.20 灰阶）占比大

🔴 必须和对标作品**并排跑**才有意义 —— 单独一个数不能下结论，要靠横比定标尺。
   同风格赛道实测：均值 ≥2.0、p90 ≥4.0、p10 ≥0.13、近静止比 ≤13%。

用法: python motion_profile.py <视频> [<视频> ...]
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

FPS = 5
W = 320


def profile(path):
    tmp = tempfile.mkdtemp(prefix="mp_")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path,
                    "-vf", f"fps={FPS},scale={W}:-1,format=gray",
                    os.path.join(tmp, "f%05d.png")], check=True)
    files = sorted(os.listdir(tmp))
    if len(files) < 3:
        return None
    prev = None
    d = []
    for fn in files:
        a = np.asarray(Image.open(os.path.join(tmp, fn)), dtype=np.int16)
        if prev is not None:
            d.append(float(np.abs(a - prev).mean()))
        prev = a
        os.remove(os.path.join(tmp, fn))
    os.rmdir(tmp)
    return np.array(d)


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    print(f"{'视频':<40} {'时长':>6} {'中位':>7} {'均值':>7} {'p10':>7} {'p90':>7} {'静止比':>7}")
    print("-" * 86)
    for p in sys.argv[1:]:
        d = profile(p)
        if d is None or len(d) == 0:
            print(f"{os.path.basename(p):<40}  抽帧失败"); continue
        dur = len(d) / FPS
        # 「近静止比」= 相邻帧 MAD < 0.20 灰阶的帧占比。
        # 320px 灰度下，真正静止的两帧（仅 H.264 噪声）实测 MAD < 0.15 ⇒ 这个阈值安全。
        still = float((d < 0.20).mean())
        print(f"{os.path.basename(p):<40} {dur:6.0f}s {np.median(d):7.3f} "
              f"{d.mean():7.3f} {np.percentile(d,10):7.3f} {np.percentile(d,90):7.3f} "
              f"{still*100:6.1f}%")


main()
