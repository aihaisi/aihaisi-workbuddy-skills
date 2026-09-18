# -*- coding: utf-8 -*-
"""Beamer 幻灯片版面审计（逐页量化，不靠肉眼）。

三项检测：
  A. 上遮挡   —— 正文首行 yMin 是否低于帧标题色带下沿（要求间距 >= 2pt）
  B. 下压页脚 —— 正文末行是否与页脚文字重叠（要求间距 >= 2pt）
  C. 页顶裁切 —— 色带最上 3 行内是否出现文字像素（标题上溢到页外）

原理：
  1) pdftoppm 渲染逐页 PNG，按“红色分隔线”颜色扫描出每页色带下沿的 y 坐标
  2) pdftotext -bbox 取每个词的包围盒（单位 pt，原点左上），按 yMin 归并成行
  3) 逐页做数值比对

依赖：poppler 的 pdftoppm / pdftotext / pdfinfo（MiKTeX 自带），Pillow。

用法：
  python layout_audit.py main.pdf
  python layout_audit.py main.pdf --dpi 200 --footer-key 浙江传媒学院
  python layout_audit.py main.pdf --rule 178,58,72 --band 22,50,79
  python layout_audit.py main.pdf --grid grid.png        # 额外输出全篇缩略总览
  python layout_audit.py main.pdf --clean                # 审计后删除渲染缓存
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:
    sys.exit('需要 Pillow：pip install pillow')


def _rgb(s):
    return tuple(int(v) for v in s.split(','))


def band_bottom(png_path, rule_rgb, tol, coverage=0.55, search=0.45):
    """返回该页“标题色带下沿”（红色分隔线**最下沿**）的 y 像素；无则 None。

    取最下沿是刻意保守：红线本身也属于色带的可视部分，
    正文压到红线同样算遮挡。只扫描页面顶部 `search` 比例的高度，
    避免把封面下方的短装饰线误判为色带。
    """
    im = Image.open(png_path).convert('RGB')
    w, h = im.size
    px = im.load()
    last = None
    for y in range(0, int(h * search)):
        hit = 0
        for x in range(0, w, 4):
            r, g, b = px[x, y]
            if abs(r - rule_rgb[0]) < tol and abs(g - rule_rgb[1]) < tol and abs(b - rule_rgb[2]) < tol:
                hit += 1
        if hit > (w / 4) * coverage:
            last = y
    return last


def top_clipped(png_path, band_rgb, tol, dark_ratio=0.6, rows=3, bright=170):
    """色带顶在页面顶边时：色带内前几行若出现“亮像素”说明有文字被裁到带内/页外"""
    im = Image.open(png_path).convert('RGB')
    w, h = im.size
    px = im.load()
    top = [px[x, 0] for x in range(0, w, 4)]
    dark = sum(1 for r, g, b in top if r < 100 and g < 100 and b < 100)
    if dark < len(top) * dark_ratio:
        return None                      # 页面顶部不是深色带（封面/分隔页等），跳过
    for y in range(0, rows):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r > bright and g > bright and b > bright:
                return True
    return False


def page_lines(pdf, page, workdir):
    """用 pdftotext -bbox 取该页文字行：[(yMin, yMax, text), ...] 按 yMin 升序"""
    out = os.path.join(workdir, 'bb.xml')
    subprocess.run(['pdftotext', '-bbox', '-f', str(page), '-l', str(page), pdf, out],
                   capture_output=True)
    if not os.path.exists(out):
        return []
    xml = open(out, encoding='utf-8', errors='ignore').read()
    words = [(float(a), float(b), float(c), float(d), e) for a, b, c, d, e in re.findall(
        r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', xml)]
    os.remove(out)
    words.sort(key=lambda x: x[1])
    lines = []
    for w in words:
        if not lines or w[1] - lines[-1][0] > 3.0:
            lines.append([w[1], w[3], w[4]])
        else:
            lines[-1][1] = max(lines[-1][1], w[3])
            lines[-1][2] += w[4]
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--dpi', type=int, default=200)
    ap.add_argument('--rule', default='178,58,72', help='红色分隔线 RGB（默认 #B23A48）')
    ap.add_argument('--band', default='22,50,79', help='色带底色 RGB（默认 #16324F）')
    ap.add_argument('--tolerance', type=int, default=30)
    ap.add_argument('--footer-key', default='', help='页脚识别关键字，用于“下压页脚”检测')
    ap.add_argument('--min-gap', type=float, default=2.0, help='判定阈值(pt)')
    ap.add_argument('--grid', default='', help='输出全篇缩略总览图路径')
    ap.add_argument('--clean', action='store_true', help='审计结束后删除渲染缓存')
    args = ap.parse_args()

    pdf = os.path.abspath(args.pdf)
    if not os.path.exists(pdf):
        sys.exit('找不到 PDF: %s' % pdf)
    rule, band = _rgb(args.rule), _rgb(args.band)
    sc = 72.0 / args.dpi
    tmp = tempfile.mkdtemp(prefix='beamer_audit_')

    subprocess.run(['pdftoppm', '-png', '-r', str(args.dpi), pdf, os.path.join(tmp, 'p')],
                   capture_output=True)
    pngs = sorted(f for f in os.listdir(tmp) if f.endswith('.png'))
    print('=== 版面审计 %s : %d 页  dpi=%d ===' % (os.path.basename(pdf), len(pngs), args.dpi))

    bad_top, bad_bot, bad_clip, min_top, min_bot = [], [], [], None, None
    for idx, fn in enumerate(pngs, 1):
        path = os.path.join(tmp, fn)
        lines = page_lines(pdf, idx, tmp)
        clipped = top_clipped(path, band, args.tolerance)
        if clipped:
            bad_clip.append(idx)

        bb = band_bottom(path, rule, args.tolerance)
        if bb is None:
            print('  p%02d  [未检测到标题色带]' % idx + ('   <== 页顶疑似裁切' if clipped else ''))
            continue

        bb_pt = bb * sc
        inside = [l for l in lines if l[0] < bb_pt - 0.5]
        body = next((l for l in lines if l[0] >= bb_pt - 0.5), None)
        gap = (body[0] - bb_pt) if body else None

        foot = next((l for l in lines if args.footer_key and args.footer_key in l[2]), None)
        bgap = None
        if foot:
            above = [l for l in lines if l[0] < foot[0] - 1]
            if above:
                bgap = foot[0] - max(l[1] for l in above)

        msg = '  p%02d 色带下沿=%6.2f 带内%d行 上间距=%s 下间距=%s' % (
            idx, bb_pt, len(inside),
            ('%.2f' % gap) if gap is not None else 'NA',
            ('%.2f' % bgap) if bgap is not None else 'NA')
        if len(inside) > 2 or (gap is not None and gap < args.min_gap):
            msg += '   <== 正文被色带遮挡'
            bad_top.append(idx)
        if bgap is not None and bgap < args.min_gap:
            msg += '   <== 正文压到页脚'
            bad_bot.append(idx)
        if clipped:
            msg += '   <== 页顶裁切'
        if gap is not None:
            min_top = gap if min_top is None or gap < min_top else min_top
        if bgap is not None:
            min_bot = bgap if min_bot is None or bgap < min_bot else min_bot
        print(msg)

    if args.grid:
        ims = [Image.open(os.path.join(tmp, f)) for f in pngs]
        if ims:
            w, h = ims[0].size
            cols = 6
            rows_n = (len(ims) + cols - 1) // cols
            cv = Image.new('RGB', (w * cols, h * rows_n), '#8a8a8a')
            for i, im in enumerate(ims):
                r, c = divmod(i, cols)
                cv.paste(im, (c * w, r * h))
            cv.save(args.grid)
            print('缩略总览:', args.grid, cv.size)

    print('=' * 60)
    print('上遮挡页:', bad_top or '无', '  (最小上间距 %s)' % ('%.2fpt' % min_top if min_top else 'NA'))
    print('下压页脚页:', bad_bot or '无', '  (最小下间距 %s)' % ('%.2fpt' % min_bot if min_bot else 'NA'))
    print('页顶裁切页:', bad_clip or '无')
    ok = not (bad_top or bad_bot or bad_clip)
    print('结论:', '全部通过' if ok else '存在问题，需按上面的页号排查')

    if args.clean:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print('（渲染缓存保留在 %s，可加 --clean 自动删除）' % tmp)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
