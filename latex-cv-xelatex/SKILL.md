---
name: latex-cv-xelatex
description: 用 XeLaTeX 构建或改写中文简历（ctex 模板、单页压缩/两页版式、TikZ 定位、照片、二维码、hyperref）。覆盖六个高发误判：\includegraphics 不带扩展名会命中宏包树里的占位图；TikZ remember picture 必须编译两次否则整页空白；pdftoppm 转图后按文件体积就能判定 PDF 是不是空的；低 DPI 预览会把主题色深蓝误看成红色；用 LaTeX 的 qrcode 宏包（需 shell-escape）做二维码在 Overleaf 上会失败，应改用 segno 生成 PNG 并用 pyzbar 反解验证；短节的标题会孤立在页底（用 needspace 修）。当用户说"套这个模板做简历""把简历内容搬到新模板""简历压到一页/改两页""改简历字号/行距""简历照片不对""作品集加二维码/扫码即玩""把学号去掉"时使用。
agent_created: true
---

# 用 XeLaTeX 做中文简历

## 0. 先确认工具链

本机（Windows）已验证可用的绝对路径：

```
XeLaTeX  : %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/xelatex.exe
pdftoppm : %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/pdftoppm.exe
pdftotext: %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/pdftotext.exe
Python   : %LOCALAPPDATA%/Programs/Python/Python314/python.exe  （用系统 Python，不要下新的）
```

`fitz`/PyMuPDF 通常**没装**。不要指望 `import fitz` 读 PDF —— 用 `pdftotext` 抽文本、`pdftoppm` 转图。

## 1. 编译：简历模板一律跑两遍

```bash
cd "<工程目录>" && \
"<xelatex>" -interaction=nonstopmode "xxx.tex" > b1.log 2>&1; \
"<xelatex>" -interaction=nonstopmode "xxx.tex" > b2.log 2>&1; \
grep -oE "Output written on.*" b2.log; \
echo "errors:"; grep -cE "^! " b2.log; \
echo "overfull:"; grep -cE "Overfull" b2.log
```

**为什么必须两遍**：

- 含 TikZ `remember picture, overlay`（两栏侧边栏版式常用）→ 第一遍写 `.aux` 记页面坐标，第二遍才定位节点。**只跑一遍的后果是整页几乎空白**，只剩一点背景色块，极易被当成"编译失败"去查别的地方。
- `hyperref` 也要两遍才能写对链接与书签。

## 2. 四个必查的坑

### 坑 1（最隐蔽）：`\includegraphics{photo}` 不带扩展名会用到宏包里的占位图

graphicx 的默认扩展搜索顺序是 **`.pdf → .png → .jpg → ...`**，且会搜 TeX 的整个搜索路径（不只是当前目录）。

MiKTeX 的 `pas-cv` 宏包里带着一个占位图：

```
%LOCALAPPDATA%/Programs/MiKTeX/tex/latex/pas-cv/photo.png
```

所以模板写 `{photo}`、你本地放了 `photo.jpg` 时，**命中的是宏包树里那张占位图，本地 jpg 根本没被读取**——而且 XeLaTeX 日志里不一定打印被包含的图片名，`grep photo b2.log` 可能一无所获，光看日志查不出来。

**处置**：一律写全扩展名。

```latex
\includegraphics[width=0.9\linewidth]{photo.jpg}   % 不要写成 {photo}
```

**验证**（唯一可靠的办法 —— 裁图看）：A4 @300dpi 是 2480×3508 px，照片区可用 `-x -y -W -H` 直接裁：

```bash
"<pdftoppm>" -png -r 300 -x 1880 -y 140 -W 430 -H 500 "main-cn.pdf" "pz"
```

然后读 `pz-1.png`。出现卡通占位图/默认头像即为命中宏包图。

### 坑 2：转图后的**文件体积**就是 PDF 是否空白的判据

```bash
"<pdftoppm>" -png -r 150 "xxx.pdf" "preview"
ls -la preview*.png
```

- **< 10 KB** → 基本是废的（内容丢失，见坑 1 或 TikZ 少跑一遍）
- **数百 KB** → 正常渲染

这一条比肉眼翻 PDF 快得多，务必在交付前跑。

### 坑 3：低 DPI 预览会把深蓝误看成红色

`#003366` / `#254665` 这类深蓝在 110~130 dpi 缩略图里，因为粗笔画 + 抗锯齿，会被看成暗红/褐红，容易误判成"颜色错了"。

**判定配色一律用 300dpi 裁图看**，别看缩略图：

```bash
"<pdftoppm>" -png -r 300 -x 30 -y 30 -W 900 -H 220 "main-cn.pdf" "crop_name"
```

### 坑 4：中文字体与 `fontset=windows`

`\documentclass[a4paper,10pt,fontset=windows]{article}` + `\usepackage{ctex}` 依赖 XeTeX 的字体机制，**不能用 pdfLaTeX 编译**。`\setmonofont{Consolas}` / `\setsansfont{Arial}` 在 Windows 上可直接解析。

## 3. 把内容压到一页

简历默认应压到 1 页。**先动排版旋钮，别先删内容**。旋钮与量级（以 A4、单栏 CV 模板为基准）：

| 旋钮 | 典型改动 | 收益 |
|---|---|---|
| `\documentclass[...11pt...]` → `10pt` | 字号 −1pt | **最大**：行高与每行字数同时变，总高约 ×0.83 |
| `\renewcommand{\baselinestretch}{1.25}` → `1.12` | 行距 | 约 ×0.9 |
| `\geometry{top=1.8cm,bottom=1.8cm}` → `1.5/1.4cm` | 页边距 | 约 +0.6cm 文本高 |
| `\cvsection` 内 `\bigskip` → `\medskip` | 每节间距 | 7 节约省 1.5cm |
| `\cvevent` 结尾 `\smallskip` → `\vspace{1pt}` | 每条目间距 | 条目多时可观 |
| `enumerate[leftmargin=2.3em]` → `2.1em` | 列表缩进 | 少量 |

**经验换算**：11pt/1.25/1.8cm 下约 1.6 页的内容，同时上 10pt + 1.12 + 1.5cm + `\medskip` 后约落在 1.0~1.15 页；若仍差 3~5 行，再删**重复项**（同一奖项在"教育经历"和"奖项与荣誉"各出现一次、技能节与自我评价节互相覆盖）而不是删信息。

若用户明确要保留模板的宽松行距，就交 2 页版并在回复里说明"1 页需要压行距/删减"，让他选。

## 4. 交付前验证清单

```bash
# 1) 页数与错误
grep -oE "Output written on.*" b2.log
grep -cE "^! " b2.log          # 期望 0
grep -cE "Overfull" b2.log     # 期望 0（大段 Overfull \hbox 会破坏右对齐）

# 2) 关键内容确实在（旧词是否残留、新词是否生效）
"<pdftotext>" -layout "xxx.pdf" out.txt
grep -c "要保留的新词" out.txt
grep -c "该删掉的旧词" out.txt   # 期望 0

# 3) 渲染没坏
"<pdftoppm>" -png -r 150 "xxx.pdf" "preview" && ls -la preview*.png
```

**抽文本时注意**：`pdftotext -layout` 对中文换行会拆词（"工作流"被拆成"工作/流"分两行），看到断词不要当成内容缺失。判断"最后一行有没有被切掉"看 `Overfull \vbox` 计数，比看文本更准。

## 5. 二维码（作品集「扫码即玩」）

- **不要用 LaTeX 的 `qrcode` 宏包**：它靠 `\write18` 调 `qrencode` 二进制，需 `-shell-escape`，Overleaf 上直接失败（MiKTeX 本地能跑，但不可移植）。
- 用 Python `segno`（纯 Python，自带 PNG 编码器，不需要 PIL）生成 PNG 再 `\includegraphics`：

```bash
python -c "import segno; segno.make('https://x/', error='m').save('qr.png', scale=10, border=2, dark='#003366', light='#ffffff')"
```

- 装 segno 到托管 venv：`$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install segno`。⚠️ pip 必须走 Clash 代理才通 PyPI：`HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897`（默认注入的 `127.0.0.1:5887` 沙箱代理与清华镜像都不通）。
- 版式（正文左、二维码右，垂直居中）：

```latex
\noindent
\begin{minipage}[c]{\dimexpr\linewidth-2.6cm}
在线演示：\href{URL}{url}\\
{\small 扫码或点击链接即可直接试玩}
\end{minipage}\hfill
\begin{minipage}[c]{2.2cm}\centering
\includegraphics[width=\linewidth]{qr.png}
\end{minipage}\par
```

- **验证扫码用 `pyzbar`**（`pip install pyzbar`，Windows wheel 自带 zbar DLL，比 `opencv-python-headless` 小得多、也不会被沙箱中途杀掉）。既要解源 PNG，更要解 `pdftoppm -r 300` 渲染出的整页 PNG——后者才证明「印出来能扫」：

```python
from pyzbar.pyzbar import decode; from PIL import Image
print([d.data.decode() for d in decode(Image.open('page-1.png'))])
```

### 5.1 长链接（微信公众号文章等）→ 二维码变密，按模块尺寸反推显示宽度

微信公众号文章链接常带一堆跟踪参数（`chksm` / `mpshare` / `scene` / `srcid` / `sharer_shareinfo*` / `#rd`），整条可达 350 字符 → QR 会到 **version 14 / 81 模块**。此密度下必须**印够大**才扫得动：

**判据：模块物理尺寸 ≥ 0.3mm（≈300dpi 下 3.6px/模块）**。宽度 = 模块数 × 0.31mm，例如 81 模块 → **2.6cm**（少于此宽度手机扫不出）。

```python
import segno
q = segno.make(url, error='m'); print(q.version, q.symbol_size()[0])   # 先看密度再定宽度
```
```latex
\begin{minipage}[c]{\dimexpr\linewidth-3.0cm} ...条目文字... \end{minipage}\hfill
\begin{minipage}[c]{2.6cm}\centering
\href{URL}{\includegraphics[width=\linewidth]{qr_wx.png}}\par
{\scriptsize\color{main}扫码读公众号报道}
\end{minipage}
```

- ⚠️ **`\href` 的第一参数里 `#` 必须转义成 `\#`**（否则 `#rd` 被当宏参数报错）；`&` `=` `+` 不用转义，hyperref 能处理。
- 可**精简**的链接：微信用 `__biz + mid + idx + sn` 四参形式（109 字符 → 49 模块，宽度可降到 ~1.6cm）。实测该形式会被微信接受（对非浏览器 UA 返回验证码页 = 机器人拦截，而非链接失效）。**但若无法确证正文可打开，就编完整链接**——二维码扫不开的代价远大于版面占位。
- 定案后**务必**用 §5 的 `pyzbar` + 300dpi 整页渲染反解一次，解出完整 URL 才算通过。

## 6. 两页版式：别让节标题孤立在页底

内容落在 1.3~1.6 页时（用户允许交两页），`奖项与荣誉` 这类短节的**标题会单独留在页底、内容翻到次页**。在 `\cvsection` 开头加 `needspace`（Overleaf 默认可用）：

```latex
\usepackage{needspace}
\newcommand{\cvsection}[2][]{\needspace{5\baselineskip}\bigskip ...}
```

补充：本机这版 `pdftoppm` 的 `-x -y -W -H` **裁剪不生效**（仍输出整页），要裁图请改用 PIL。

## 7. 工程约定（本项目/本用户）

- 交付命名分两种：**作业/课程提交**用 `学号-姓名-简历`；**对外求职简历**用 `姓名-简历`，**不带学号**。换模板做新版时加 `-新模版` 后缀，**不覆盖旧版**。用户说「把学号去掉」时先 grep 正文——学号通常只在**文件名/目录名**里，正文没有，改目录名 + 输出 PDF 名即可。
- 交付物：`*.tex` + `*.pdf` + `photo.jpg` + `README.md`（有二维码时加 `qr*.png`），**以散文件形式留在工程目录，不打包 zip**（用户 2026-09-26 明确要求「以后不用压缩」——此前每版都打 zip 的时代已结束，别再生成 zip）。
- 原始下载网页 / 原始模板文件保持**未改动**，填充后的版本另存为新文件。
- 临时文件（`*.aux` `*.log` `*.out`、预览 png、构建日志）交付前删干净；临时 Python 脚本用完即删。
- 用系统 Python 跑打包/提取脚本（写文件再执行，不要 heredoc）。
