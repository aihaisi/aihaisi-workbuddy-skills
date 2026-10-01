# -*- coding: utf-8 -*-
"""Splice a headless-verification driver into a single-file HTML page.

    python splice_gltest.py <index.html> <driver.js> [out.html]

Defaults out.html to <index.html 同目录>/_gltest.html.
Keeps the original untouched so the driver can be re-injected after every rebuild.
"""
import io
import os
import sys


def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        return 2

    src = os.path.abspath(sys.argv[1])
    driver = os.path.abspath(sys.argv[2])
    dest = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 \
        else os.path.join(os.path.dirname(src), '_gltest.html')

    for p in (src, driver):
        if not os.path.exists(p):
            print('ERROR: not found: %s' % p)
            return 1

    html = read(src)
    js = read(driver)

    if '</body>' not in html:
        print('ERROR: </body> not found in %s' % src)
        return 1

    # 驱动脚本里的 </script> 会提前闭合标签，必须转义
    js = js.replace('</script>', '<\\/script>')

    html = html.replace('</body>', '<script>\n' + js + '\n</script>\n</body>')
    with io.open(dest, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)

    print('wrote %s' % dest)
    return 0


if __name__ == '__main__':
    sys.exit(main())
