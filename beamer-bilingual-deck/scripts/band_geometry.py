# -*- coding: utf-8 -*-
"""量某一页“帧标题色带”的上下边界与高度（单位 pt），用于标定 ht/dp 参数。

用法：
  # 先渲染某一页
  pdftoppm -png -r 300 -f 30 -l 30 main.pdf /tmp/pg30
  python band_geometry.py /tmp/pg30-30.png 300

  # 或直接给 PDF + 页码，脚本自己渲染
  python band_geometry.py main.pdf 30 --dpi 300

输出：色带 top / bottom / 高度（pt）。色带 top 通常为 0（贴页面顶边），
      bottom 即 beamer 中 ht + dp 的实际绘制结果，可用来反推参数是否合适。
"""
import os
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:
    sys.exit('需要 Pillow：pip install pillow')

DEFAULT_BAND_RGB = (22, 50, 79)      # 深藏青 #16324F，按自己主题改
TOL = 30
COVERAGE = 0.8


def measure(png, dpi, band_rgb=DEFAULT_BAND_RGB, coverage=COVERAGE):
    sc = 72.0 / dpi
    im = Image.open(png).convert('RGB')
    w, h = im.size
    px = im.load()
    rows = []
    for y in range(h):
        hit = 0
        for x in range(0, w, 4):
            r, g, b = px[x, y]
            if abs(r - band_rgb[0]) < TOL and abs(g - band_rgb[1]) < TOL and abs(b - band_rgb[2]) < TOL:
                hit += 1
        if hit > (w / 4) * coverage:
            rows.append(y)
    print('png=%s  size=%s  dpi=%s' % (png, im.size, dpi))
    if not rows:
        print('  未检测到该颜色的色带（检查 --band 颜色值或该页是否无色带）')
        return None
    top, bottom = rows[0] * sc, rows[-1] * sc
    print('  色带 top    = %6.2f pt' % top)
    print('  色带 bottom = %6.2f pt' % bottom)
    print('  色带高度    = %6.2f pt  (= ht + dp 的绘制结果)' % (bottom - top + sc))
    return top, bottom


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    a = sys.argv[1]
    if a.lower().endswith('.pdf'):
        page = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
        dpi = 300
        if '--dpi' in sys.argv:
            dpi = int(sys.argv[sys.argv.index('--dpi') + 1])
        tmp = tempfile.mkdtemp(prefix='band_geom_')
        subprocess.run(['pdftoppm', '-png', '-r', str(dpi), '-f', str(page), '-l', str(page),
                        a, os.path.join(tmp, 'p')], capture_output=True)
        pngs = [f for f in os.listdir(tmp) if f.endswith('.png')]
        if not pngs:
            sys.exit('渲染失败')
        measure(os.path.join(tmp, pngs[0]), dpi)
    else:
        dpi = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
        measure(a, dpi)


if __name__ == '__main__':
    main()
