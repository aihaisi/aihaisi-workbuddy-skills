#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验收：章节尾部的 hold 段**是不是真的在动**（还是整帧冻结）。

为什么需要它：hold 段最容易写成冻结，而冻结 = 肉眼可察的死区。
看单张静帧看不出来，必须比较相邻帧的像素差。

判据（实测基线）：
    源帧平移 1px    ⇒ MAD ≈ 0.8367
    H.264 压缩噪声  ⇒ MAD ≈ 0.005
⇒ 有意义的下限取 **0.05**；低于它基本可判「冻结」。

════════════════════════════════════════════════════════════════════════════
🔴🔴 有全屏动态背景时，**必须只在「内容区」上量**（不是扣基线，也不是看全帧）

① 全帧读数会失效：纯背景自身的逐帧 MAD 就有 ≈2.15，
   成片 hold 段读数从 0.08–0.27 被抬到 1.46–2.12
   ⇒ **某个资产真的冻结了也照样"通过"**。检测器不再有效。

② 「扣掉背景基线」是**错的**（第一版就这么写错）：
   纯背景参考帧**全帧都是颗粒**（MAD 2.15），而成片里大片被不透明内容盖住、
   颗粒根本看不见 ⇒ 成片读数天然更低，相减出来全是负数（实测 −0.03 ~ −0.69）。
   负残差说明的不是"没动"，而是**减错了** —— 这个信号本身就是修法错误的证据。

✅ 正确做法：**只在内容像素上测**。内容像素上颗粒被内容遮住
   ⇒ 量到的就是纯粹的资产运动，不需要减任何东西。
       内容掩码 = |成片帧 − 纯背景帧| > 阈值（内容明显亮于背景）
       净运动   = 掩码内相邻帧差的均值

   🔴 **掩码必须向内腐蚀几个像素**（这里取 4px）。否则掩码的**边界环**全是
      「半覆盖」的抗锯齿像素 —— 那里背景颗粒露在外面照样在动，
      会被算成"内容运动"，把真冻结顶到阈值以上。
      实测（已知冻结样本，内容块完全不动）：
          未腐蚀的掩码 ⇒ 净运动 0.0776   ← 会被误判为"通过"
          腐蚀 4px 后 ⇒ 净运动 0.0010   ← 正确判出冻结（白块内部仅 0.0001）
      边界环只占掩码的 ~10%，却贡献了全部读数的 ~98%。

   纯背景帧的生成：背景若设计成**全局帧号的确定性函数**（如 canvas 里
   `drawBackground(ctx, W, H, f)`），同一帧号可精确复现一张纯背景图
   ⇒ 用你管线的截图工具渲染一批同名帧即可（本项目为 `render-bg.js` + `bgonly.html`）。
   ⚠️ 背景帧必须用**全局帧号**渲染；传章内帧号会在每章开头跳回去。

⚠️ 无颗粒/无动态背景的旧片用 `--no-bg`（此时全帧读数仍然可信）。
════════════════════════════════════════════════════════════════════════════

用法:
    python check_motion.py <mp4> <帧号,逗号分隔> [--bg-dir <纯背景帧目录>] [--no-bg]

        --bg-dir 目录里应有 f%05d.png（如 f00420.png），覆盖所有需要的帧号
        --no-bg  跳过背景掩码，直接看全帧（仅适用于静态背景的片子）
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

THRESH = 0.05           # 有意义运动的下限（1px 位移 ≈ 0.8367，压缩噪声 ≈ 0.005）
WINDOW = 5              # 每个检查点看连续 5 帧
MASK_DELTA = 16         # 判定「内容像素」的亮度差阈值（灰阶）
MASK_MIN = 0.005        # 内容占比低于 0.5% ⇒ 该章本来就没内容，无法判定
ERODE = 4               # 掩码向内腐蚀像素数（见上文：边界环是最大污染源）

try:
    from scipy import ndimage
    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False

args = [a for a in sys.argv[1:] if not a.startswith('--')]
BG_DIR_ARG = None
if '--bg-dir' in sys.argv:
    i = sys.argv.index('--bg-dir')
    if i + 1 < len(sys.argv):
        BG_DIR_ARG = sys.argv[i + 1]
        if BG_DIR_ARG in args:
            args.remove(BG_DIR_ARG)
USE_MASK = ('--no-bg' not in sys.argv) and bool(BG_DIR_ARG)

if len(args) < 2:
    print(__doc__); sys.exit(2)

V = args[0]
FRAMES = [int(x) for x in args[1].split(',')]
NEEDED = sorted({f for end in FRAMES for f in range(end - WINDOW, end)})

print(f'{V}')
print(f'检查点 {len(FRAMES)} 处，共需 {len(NEEDED)} 帧'
      + ('（内容区掩码模式）' if USE_MASK else '（--no-bg，看全帧）') + '\n')

if not USE_MASK and '--no-bg' not in sys.argv:
    print('⚠️ 未提供 --bg-dir ⇒ 退回「看全帧」模式。')
    print('   若该片有全屏动态背景，读数会被背景放大，结论不可用。\n')

# ── 1. 读纯背景参考帧 ──
bgf = {}
if USE_MASK:
    for f in NEEDED:
        q = os.path.join(BG_DIR_ARG, f'f{f:05d}.png')
        if os.path.exists(q):
            bgf[f] = np.asarray(Image.open(q).convert('RGB'), dtype=np.int16)
    if not bgf:
        print(f'⚠️ {BG_DIR_ARG} 里没有匹配 f%05d.png ⇒ 退回「看全帧」模式（仅供参考）\n')
        USE_MASK = False

# ── 2. 抽成片帧（一次解码取全部需要的帧）──
# 🔴 别对每个帧号单独跑一次 ffmpeg select=eq(n,f)：每次都从头解码，
#    几十个检查点会到分钟级甚至被外层超时杀掉。一次解码 + select 多帧即可。
tmp = tempfile.mkdtemp(prefix='cm_')
expr = '+'.join(f'eq(n\\,{f})' for f in NEEDED)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', V,
                '-vf', f'select={expr}', '-vsync', '0',
                os.path.join(tmp, 'f%05d.png')], check=False)
# select 按顺序输出 ⇒ 第 k 个文件对应排序后 NEEDED 的第 k 个帧号
got = sorted(x for x in os.listdir(tmp) if x.startswith('f') and x.endswith('.png'))
film = {}
if len(got) == len(NEEDED):
    for k, f in enumerate(NEEDED):
        film[f] = np.asarray(Image.open(os.path.join(tmp, got[k])).convert('RGB'),
                             dtype=np.int16)
else:
    # 数量对不上（丢帧/滤镜行为异常）⇒ 退回逐帧取，慢但可靠
    print(f'⚠️ 批量抽帧得到 {len(got)} 帧，期望 {len(NEEDED)} 帧 ⇒ 退回逐帧抽取')
    for f in NEEDED:
        q = os.path.join(tmp, f'single_{f}.png')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', V,
                        '-vf', f'select=eq(n\\,{f})', '-vframes', '1', q], check=False)
        if os.path.exists(q):
            film[f] = np.asarray(Image.open(q).convert('RGB'), dtype=np.int16)

# ── 3. 逐点判定 ──
worst, worst_full = 1e9, 1e9
n_ok = n_bad = n_skip = 0

for end in FRAMES:
    idx = [f for f in range(end - WINDOW, end) if f in film]
    if len(idx) < 2:
        print(f'  帧 {end - WINDOW}..{end - 1}  抽帧失败，跳过')
        n_skip += 1
        continue

    full = [float(np.abs(film[idx[i + 1]] - film[idx[i]]).mean()) for i in range(len(idx) - 1)]
    full_max = max(full)
    worst_full = min(worst_full, full_max)

    # 掩码用**窗口中间那一帧**与背景参考比 —— 内容像素 = 明显亮于背景的像素
    mid = idx[len(idx) // 2]
    if USE_MASK and mid in bgf and bgf[mid].shape == film[mid].shape:
        mask = np.abs(film[mid] - bgf[mid]).max(axis=2) > MASK_DELTA
        if _HAS_SCIPY and ERODE > 0:
            mask = ndimage.binary_erosion(mask, iterations=ERODE)
        frac = float(mask.mean())
        if frac < MASK_MIN:
            print(f'  帧 {end - WINDOW}..{end - 1}   内容占画面 {frac*100:.2f}%  '
                  f'⇒ 该章几乎没内容，无法判定（跳过）')
            n_skip += 1
            continue
        vals = [float(np.abs(film[idx[i + 1]][mask] - film[idx[i]][mask]).mean())
                for i in range(len(idx) - 1)]
        mx = max(vals)
        ok = mx > THRESH
        line = (f'  帧 {end - WINDOW}..{end - 1}   内容占画面 {frac*100:5.1f}%   '
                f'**内容区净运动 {mx:7.4f}**   （全帧读数 {full_max:6.3f}）')
    else:
        mx = full_max
        ok = mx > THRESH
        line = (f'  帧 {end - WINDOW}..{end - 1}   '
                f'**净运动 {mx:7.4f}**（未扣背景，全帧）')

    worst = min(worst, mx)
    n_ok += ok; n_bad += (not ok)
    print(line + ('   OK ' if ok else '   ❌ 疑似冻结'))

print(f'\n最弱的一处「净运动」= {worst:.4f}   （阈值 {THRESH}）')
if USE_MASK:
    print(f'（不掩码的全帧读数最弱是 {worst_full:.3f} —— 背景颗粒把它抬高到阈值以上，'
          f'所以全帧读数已不可用）')
print(f'通过 {n_ok} / 冻结 {n_bad} / 跳过 {n_skip}')
print('结论:', '全部有运动 ✓' if n_bad == 0 and n_ok > 0 else '存在冻结段 ✗')
sys.exit(0 if n_bad == 0 and n_ok > 0 else 1)
