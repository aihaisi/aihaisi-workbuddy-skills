# -*- coding: utf-8 -*-
"""Parse a uiautomator dump XML and list labeled nodes with bounds/center.

Usage:
    python ui_nodes.py <dump.xml> [out.txt]

Why a script instead of grep: uiautomator dumps are a single enormous line,
so line-based grep returns the whole file. This walks <node> tags instead.

Note: on this machine the PowerShell tool does not relay stdout, so always
pass an output file and read it back with the Read tool.
"""
import re
import sys


def attr(tag, name):
    m = re.search(name + r'="([^"]*)"', tag)
    return m.group(1) if m else ""


def center(bounds):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not m:
        return ""
    x1, y1, x2, y2 = (int(g) for g in m.groups())
    return f"center=({(x1 + x2) // 2},{(y1 + y2) // 2})"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None

    xml = open(src, encoding="utf-8", errors="replace").read()

    lines = []
    for m in re.finditer(r"<node\b[^>]*?/?>", xml):
        tag = m.group(0)
        text = attr(tag, "text")
        desc = attr(tag, "content-desc")
        if not (text or desc):
            continue
        bounds = attr(tag, "bounds")
        cls = attr(tag, "class").split(".")[-1]
        lines.append(
            "{:24} {:18} click={:5} {:12} text={!r} desc={!r}".format(
                bounds, center(bounds), attr(tag, "clickable"), cls, text, desc
            )
        )

    lines.append("")
    lines.append("labeled nodes: %d" % (len(lines) - 1))
    out = "\n".join(lines)

    if dst:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
