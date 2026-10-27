# -*- coding: utf-8 -*-
"""运动分布热力图 —— 回答「运动到底发生在画面的哪个位置」。

motion_profile.py 只给全片的标量统计；这个给出**逐像素的时间平均变化量**：
  对每一帧算 |frame_i - frame_{i-1}|，再沿时间取平均 ⇒ 一张与画面同尺寸的图。
  · 亮 = 这块区域常年变化
  · 黑 = 这块区域从不变化

🔴 关键物理事实：**平色区域无论怎么平移/缩放，逐帧差异都是 0。**
   所以热力图上的黑区，不是"动得慢"，是"这里没有能被察觉的高频结构"。
   典型症状：亮区只堆在画面中间、四个角落与四周大片纯黑
   ⇒ 约 30% 的画面**从来没变过** ⇒ 观众观感就是"像 PPT"。
   ⇒ 修法不是"加镜头推拉"，是放一层**覆盖全屏、有高频结构**的层。

用法: python motion_map.py <视频> <输出png> [标签]
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

W = 480


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    path, outp = sys.argv[1], sys.argv[2]
    tag = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(path)

    tmp = tempfile.mkdtemp(prefix="mm_")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path,
                    "-vf", f"fps=5,scale={W}:-1,format=gray",
                    os.path.join(tmp, "f%05d.png")], check=True)
    files = sorted(os.listdir(tmp))
    acc = None
    prev = None
    n = 0
    for fn in files:
        a = np.asarray(Image.open(os.path.join(tmp, fn)), dtype=np.float32)
        if prev is not None:
            d = np.abs(a - prev)
            acc = d if acc is None else acc + d
            n += 1
        prev = a
        os.remove(os.path.join(tmp, fn))
    os.rmdir(tmp)
    if acc is None:
        print("抽帧失败"); sys.exit(1)
    m = acc / max(1, n)
    print(f"【{tag}】逐像素平均变化量  fps=5  {n} 个帧对  {m.shape[1]}x{m.shape[0]}")
    print(f"  全局均值 {m.mean():.3f}   最大 {m.max():.2f}")
    for th in (0.2, 1.0, 3.0, 8.0):
        print(f"  平均变化 > {th:4.1f} 的像素占比 {float((m > th).mean())*100:5.1f}%")

    # 归一化存图（对比度拉满，便于看形状）
    vis = np.clip(m / max(1e-6, np.percentile(m, 99.5)) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(vis).save(outp)
    print(f"  热力图 -> {outp}")


main()
