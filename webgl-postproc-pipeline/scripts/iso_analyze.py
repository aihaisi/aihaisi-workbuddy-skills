# -*- coding: utf-8 -*-
"""把逐变体截图按「硬边程度」排序，定位画面异常出自哪一环。

    python iso_analyze.py <截图目录> [x0 x1 y0 y1] [文件名前缀]

文件名约定：<前缀><变体名>.png（例如 iso_noGlitch.png）。
第 6 个参数给前缀，用来从混放其他产物的目录里只挑变体截图。

针对画面里疑似"块/带/条纹"的区域，算三个指标：

  vee    竖向边缘能量 —— 列与列之间的平均亮度差。硬边会把它拉高。
  steps  列均值剖面上的「硬台阶」数 —— 相邻列的均值跳变超过阈值的个数。
         这是单变量判定硬边来源最直接的指标。
  flat   列均值剖面的总起伏（max-min）。

注意事项（都踩过）：
  * 裁剪区要避开 UI 叠层（对比分割线、角落 HUD），否则它们会是最大的"硬边"，
    把真正的异常盖掉。本机实测：2px 的白色分割线会在列剖面上产生 ±190 的跳变。
  * 颗粒/噪点会让列均值本身抖动 1~3，阈值取 1.2 以下就纯属噪声了。
  * 单看 steps 容易被噪点主导，一定要连 vee 和最大值位置一起看。
"""
import glob
import os
import statistics
import sys

from PIL import Image

THRESH = 1.2          # 相邻列均值跳变阈值（0-255）


def analyze(path, x0, x1, y0, y1):
    im = Image.open(path).convert('L')
    px = im.load()
    prof = []
    for x in range(x0, x1):
        col = [px[x, y] for y in range(y0, y1, 3)]
        prof.append(statistics.mean(col))

    d = [abs(prof[i] - prof[i - 1]) for i in range(1, len(prof))]
    vee = statistics.mean(d) if d else 0.0
    steps = sum(1 for v in d if v > THRESH)
    flat = (max(prof) - min(prof)) if prof else 0.0

    worst = 0
    if d:
        k = max(range(len(d)), key=lambda i: d[i])
        worst = x0 + k + 1
    return vee, steps, flat, worst, prof


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    d = sys.argv[1]
    prefix = sys.argv[6] if len(sys.argv) >= 7 else ''
    box = [int(v) for v in sys.argv[2:6]] if len(sys.argv) >= 6 else None

    files = sorted(glob.glob(os.path.join(d, prefix + '*.png')))
    files = [f for f in files if not os.path.basename(f).startswith('_')]
    if not files:
        print('no png in %s' % d)
        return 1

    if box is None:
        im = Image.open(files[0])
        w, h = im.size
        # 默认：取中间偏下的区域（多数画面异常出现在下半部），并避开最外圈边框
        box = [int(w * 0.28), int(w * 0.72), int(h * 0.45), int(h * 0.92)]
    x0, x1, y0, y1 = box
    print('裁剪区 x %d..%d  y %d..%d\n' % (x0, x1, y0, y1))

    rows = []
    for f in files:
        name = os.path.basename(f)[:-4]
        im = Image.open(f)
        if im.size[0] < x1 or im.size[1] < y1:
            # 目录里混进了别的东西（拼图、缩略图…），直接跳过而不是崩掉
            print('skip %-22s 尺寸 %dx%d 小于裁剪区' % (name, im.size[0], im.size[1]))
            continue
        vee, steps, flat, worst, prof = analyze(f, x0, x1, y0, y1)
        rows.append((name, vee, steps, flat, worst, prof))

    if not rows:
        print('没有可用截图（都被尺寸检查跳过了）')
        return 1

    rows.sort(key=lambda r: -r[2])
    print('%-22s %8s %7s %7s %8s' % ('variant', 'vee', 'steps', 'flat', 'worst_x'))
    print('-' * 58)
    for n, v, s, fl, wx, _ in rows:
        print('%-22s %8.2f %7d %7.1f %8d' % (n, v, s, fl, wx))

    print('\nsteps 最多的是 %s —— 它是嫌疑最大的那一环。' % rows[0][0])
    print('若把某个 pass 关掉后 steps 明显下降，异常就出自那个 pass；')
    print('若全关到只剩最上游仍然存在，说明异常来自素材或输入，不在管线里。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
