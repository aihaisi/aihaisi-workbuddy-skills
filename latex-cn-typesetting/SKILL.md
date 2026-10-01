---
name: latex-cn-typesetting
description: 用 XeLaTeX 产出中文排版成品——简历 CV（单页压缩、照片、二维码）与 Beamer 双语幻灯片（帧标题色带几何、纵向溢出处理、shrink 语义），含编译两遍、Overfull 处理、pdftoppm/pdftotext 版面量化审计与交付前验证清单。覆盖八个高发误判：\includegraphics 不带扩展名会命中宏包树里的占位图（日志里看不到）；TikZ remember picture 与 hyperref 必须编译两次，只跑一遍会整页空白；转图后的文件体积就能判定 PDF 是不是废的；低 DPI 预览把主题深蓝误看成红色；LaTeX 的 qrcode 宏包靠 shell-escape、Overleaf 上必失败（改用 segno 生成 PNG + pyzbar 反解验证）；beamer 的 shrink 不是「按需缩放」，给全篇统一加会让每一页字号都变小、底部大片留白；给 frametitle 加负 \vspace 回收高度会把正文首行顶进色带；长链接二维码过密导致印出来扫不动（按模块物理尺寸 ≥0.3mm 反推宽度）。当用户说"套这个模板做简历""把简历内容搬到新模板""简历压到一页/改两页""改简历字号/行距""简历照片不对""作品集加二维码/扫码即玩""把学号去掉""做双语 PPT/幻灯片""标题被色带压住""文字被遮挡""满页帧溢出""正文压到页脚""字号莫名变小且底部大片留白"时使用。
agent_created: true
---

# 用 XeLaTeX 做中文排版（简历 CV / Beamer 幻灯片）

## 0. 工具链（两个形态共用）

本机（Windows）已验证可用的绝对路径：

```
XeLaTeX  : %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/xelatex.exe
pdftoppm : %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/pdftoppm.exe
pdftotext: %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64/pdftotext.exe
Python   : %LOCALAPPDATA%/Programs/Python/Python314/python.exe  （用系统 Python，不要下新的）
```

- 中文文档必须 **XeLaTeX**，不能用 pdfLaTeX：`\documentclass[a4paper,10pt,fontset=windows]{article}` + `\usepackage{ctex}` 依赖 XeTeX 的字体机制；`\setmonofont{Consolas}` / `\setsansfont{Arial}` 在 Windows 上可直接解析。
- ⚠️ **PyMuPDF(`fitz`) 通常没装**，别指望 `import fitz` 读 PDF —— 抽文本用 `pdftotext`、转图用 `pdftoppm`。
  （**例外**：`beamer` 分支的"开工前素材体检"确实用到 `fitz`，那一步先确认 `import fitz` 能用，不能就跳过该步改用别的判据。）
- ⚠️ **本机这版 `pdftoppm` 的 `-x -y -W -H` 裁剪不生效**（仍输出整页）。要按区域裁图请改用 PIL。
  下面的裁图命令在别的机器上有效，在本机需自行替换成 PIL。

## 1. 一律编译两遍

```bash
cd "<工程目录>" && \
"<xelatex>" -interaction=nonstopmode "xxx.tex" > b1.log 2>&1; \
"<xelatex>" -interaction=nonstopmode "xxx.tex" > b2.log 2>&1; \
grep -oE "Output written on.*" b2.log; \
echo "errors:";   grep -cE "^! " b2.log; \
echo "overfull:"; grep -cE "Overfull" b2.log
```

两遍各自不可省，但理由不同：

| 形态 | 第一遍写什么 | 只跑一遍的后果 |
|---|---|---|
| CV（TikZ `remember picture, overlay` 两栏侧边栏版式） | `.aux` 里的页面坐标 | **整页几乎空白**，只剩背景色块 —— 极易被误判成"编译失败"去查别的地方 |
| Beamer（页脚"当前页/总页数"） | `\inserttotalframenumber` | 总页数不对 |
| 两者（`hyperref`） | 链接与书签 | 链接写不对 |

## 2. 交付前验证（三个形态共用四件套）

```bash
# ① 页数与错误
grep -oE "Output written on.*" b2.log
grep -cE "^! "      b2.log     # 期望 0
grep -cE "Overfull" b2.log     # 期望 0（大段 Overfull \hbox 会破坏右对齐 / 穿出页面）

# ② 渲染没坏 —— 文件体积就是「PDF 是不是空白」的判据，比肉眼翻页快得多
"<pdftoppm>" -png -r 150 "xxx.pdf" "preview" && ls -la preview*.png
#   < 10 KB   → 基本是废的（内容丢失：宏包占位图 / TikZ 少跑一遍）
#   数百 KB   → 正常渲染

# ③ 关键内容确实在（旧词是否残留、新词是否生效）
"<pdftotext>" -layout "xxx.pdf" out.txt
grep -c "要保留的新词" out.txt
grep -c "该删掉的旧词" out.txt   # 期望 0
```

**判定配色、判定照片，一律 300dpi 裁图看，别看缩略图。** `#003366` / `#254665` 这类深蓝在 110~130 dpi 缩略图里，因为粗笔画 + 抗锯齿会被看成暗红/褐红，容易误判成"颜色错了"。

```bash
"<pdftoppm>" -png -r 300 -x 30 -y 30 -W 900 -H 220 "main-cn.pdf" "crop_name"
```

**抽文本时注意**：`pdftotext -layout` 对中文换行会拆词（"工作流"被拆成"工作/流"分两行），看到断词不要当成内容缺失。判断"最后一行有没有被切掉"看 `Overfull \vbox` 计数，比看文本更准。

---

# 分支 A：简历 CV

## A1. 坑：`\includegraphics{photo}` 不带扩展名会用到宏包里的占位图

graphicx 的默认扩展搜索顺序是 **`.pdf → .png → .jpg → ...`**，且会搜 TeX 的**整个搜索路径**（不只是当前目录）。MiKTeX 的 `pas-cv` 宏包带着一个占位图：

```
%LOCALAPPDATA%/Programs/MiKTeX/tex/latex/pas-cv/photo.png
```

所以模板写 `{photo}`、你本地放了 `photo.jpg` 时，**命中的是宏包树里那张占位图，本地 jpg 根本没被读取** —— 而且 XeLaTeX 日志里不一定打印被包含的图片名，`grep photo b2.log` 可能一无所获，光看日志查不出来。

**处置**：一律写全扩展名。

```latex
\includegraphics[width=0.9\linewidth]{photo.jpg}   % 不要写成 {photo}
```

**验证（唯一可靠的办法 —— 裁图看）**：A4 @300dpi 是 2480×3508 px，照片区用 §2 的 300dpi 裁图直接看。出现卡通占位图/默认头像即为命中宏包图。

## A2. 把内容压到一页

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

## A3. 二维码（作品集「扫码即玩」）

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

- **验证扫码用 `pyzbar`**（`pip install pyzbar`，Windows wheel 自带 zbar DLL，比 `opencv-python-headless` 小得多、也不会被沙箱中途杀掉）。既要解源 PNG，更要解 **`pdftoppm -r 300` 渲染出的整页 PNG** —— 后者才证明「印出来能扫」：

```python
from pyzbar.pyzbar import decode; from PIL import Image
print([d.data.decode() for d in decode(Image.open('page-1.png'))])
```

### A3.1 长链接（微信公众号文章等）→ 二维码变密，按模块尺寸反推显示宽度

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
- 可**精简**的链接：微信用 `__biz + mid + idx + sn` 四参形式（109 字符 → 49 模块，宽度可降到 ~1.6cm）。实测该形式会被微信接受（对非浏览器 UA 返回验证码页 = 机器人拦截，而非链接失效）。**但若无法确证正文可打开，就编完整链接** —— 二维码扫不开的代价远大于版面占位。
- 定案后**务必**用 A3 的 `pyzbar` + 300dpi 整页渲染反解一次，解出完整 URL 才算通过。

## A4. 两页版式：别让节标题孤立在页底

内容落在 1.3~1.6 页时（用户允许交两页），`奖项与荣誉` 这类短节的**标题会单独留在页底、内容翻到次页**。在 `\cvsection` 开头加 `needspace`（Overleaf 默认可用）：

```latex
\usepackage{needspace}
\newcommand{\cvsection}[2][]{\needspace{5\baselineskip}\bigskip ...}
```

---

# 分支 B：Beamer 双语幻灯片

## B0. 开工前预检（3 分钟，能省掉后面半小时）

本分支的多数坑，**都不是难在修，而是难在"发现得太晚"**。动手写内容之前先做这三项：

### ① 素材健康度抽检（做"整篇论文翻译"类 deck 时必做）

不要拿到 PDF 就开始逐图裁剪。先抽 3–5 张图做体检：

```python
import fitz                                   # PyMuPDF —— 用前先确认本机装没装
from PIL import Image, ImageStat
doc = fitz.open('paper.pdf')
# ① 该页到底有没有栅格图元？
for pno in [2, 3, 5]:
    page = doc[pno]
    print(pno, len(page.get_images(full=True)), len(page.get_drawings()))
# ② 渲染后测墨迹率：< 5% 基本可判定"图是空的"
im = Image.open('crop.png').convert('L')
print('ink coverage = %.1f%%' % (100 - ImageStat.Stat(im).mean[0] / 255 * 100))
```

**关键判据**：`get_images()` 返回空 且 渲染后只剩文字标注 → 这张图在 PDF 里**根本没有内容**，不是你的裁切坐标错。此时继续重裁 10 次也没用。

已知案例：**arXiv 版的很多主图是空的**。解法是下载 e-print 源码包取原始矢量图：

```bash
curl -x http://127.0.0.1:7897 -L -o src.tar.gz https://arxiv.org/e-print/<arXiv-id>
tar xzf src.tar.gz -C src/          # 里面有 figs/*.pdf 原始矢量图 + sec_*.tex + *.bib
```

用 `figs/` 里的矢量图重渲染，清晰度比 PDF 裁切更好，还能顺便核对英文原文与文献条目。

### ② 影响范围大的参数，先单帧试跑

`shrink`、`\footnotesize→\scriptsize` 这类"一处改动全篇生效"的东西，**先在一个测试帧上编一遍看效果**，确认语义符合预期再批量套用。本分支里 `shrink` 的语义反直觉（见 B3 铁律），就是靠"先批量、后验证"付出了整册返工的代价。

### ③ 容量估算先行

拿到版面尺寸后（`\typeout{CUZDIM ...}`），先估每节内容大约占多少行 × 行高，超过 190pt 的**一开始就拆成两帧**，不要写完再补救。翻译整篇论文做双语 deck 时，内容量约为原文两倍 —— **按两倍量规划帧数**。

## B1. 骨架（可复用的最小结构）

```
<工程>/
├── main.tex                 # 只做 \input，不写正文
├── styles/<theme>.tex       # 主题/配色/页眉页脚/双语宏/代码风格
├── content/00-cover.tex     # 封面 + 目录
├── content/NN-*.tex         # 每章一个文件
└── figures/                 # 图示（优先 TikZ 内联，避免二进制素材）
```

| 项 | 值 | 理由 |
|---|---|---|
| 引擎 | `xelatex` | 中英混排要直接调用系统字体并正确断行 |
| 文档类 | `\documentclass[aspectratio=169,fontset=windows]{ctexbeamer}` | 16:9 原生参数；Windows 字体最稳 |
| 双语实现 | 宏封装，**两个参数必填** | 少写一个直接编译报错 → 结构上保证同页中英一一对应 |

```latex
\newcommand{\bframe}[2]{\frametitle{#1}\framesubtitle{#2}}      % 帧标题 + 英文副标题
\newcommand{\biitem}[2]{\item #1\par\vspace{-0.15em}{\footnotesize\color{gray}#2}\vspace{0.25em}}
\newcommand{\bipara}[2]{#1\par\vspace{0.25em}{\footnotesize\color{gray}#2}\par}
```

## B2. 帧标题色带几何（最容易翻车的地方）

中英双语标题 = **中文标题 + 英文副标题两行**，比单行标题高得多，必须显式控制色带尺寸：

```latex
\providecommand{\cuzTitleBandHt}{5.6ex}   % 基线以上高度：决定标题距色带顶的留白
\providecommand{\cuzTitleBandDp}{1.6ex}   % 基线以下高度：决定副标题距色带下沿的距离
\setbeamertemplate{frametitle}{%
  \nointerlineskip%
  \begin{beamercolorbox}[wd=\paperwidth,ht=\cuzTitleBandHt,dp=\cuzTitleBandDp,
                         leftskip=0.6cm,rightskip=0.6cm]{frametitle}%
    {\usebeamerfont{frametitle}\large\insertframetitle\par}%
    \vspace{0.2ex}%
    {\usebeamerfont{framesubtitle}\insertframesubtitle\par}%
  \end{beamercolorbox}%
  {\color{accent}\hrule height0.9pt}%
}
```

**必须知道的机制**：

- beamer 组装帧时按 **`ht + dp`** 扣减正文可用高度（`beamerbaseframe.sty` 中 `\advance\beamer@frametextheight by-\ht\beamer@frametitlebox` 之后还有 `-\dp` 与 `-frametopskip`）；色带的**绘制**高度同样是 `ht + dp`。
- 正文与色带下沿的**固有间距**只有：`0.9pt`（分隔线）+ `0.25em`（beamer 在标题模板后自动追加）≈ **3.6pt**。
- 增大 `ht`：标题整体**下移**（上留白变大），同时色带下沿与正文一起下移 → 正文可用高度减少（满页帧会从**底部**溢出）。
- 减小 `dp`：副标题更贴近色带下沿；**不影响**正文位置。

### 铁律：禁止在 `frametitle` 末尾用负 `\vspace` 回收高度

```latex
% ✗ 错误做法（会把正文顶进色带）
\end{beamercolorbox}
{\color{accent}\hrule height0.9pt}
\vspace{-1.9ex}%  “把多占的高度还回去”
```

负间距**只移动正文，不改变色带的绘制高度**。正文与色带下沿只有约 3.6pt 余量，上移超过这个值，正文首行就会钻到色带底下被盖住（表现为"每页第一条要点被切掉上半截"）。

**正确做法**：色带显得过高就调小 `ht`/`dp`；色带需要变高导致满页帧溢出，去**压紧那些帧自己的内容**：

```latex
% 满页帧里的表格：压紧行距（每 7 行约省 6–8pt）
{\small\renewcommand{\arraystretch}{0.92}
 \begin{tabular}{...} ... \end{tabular}}
```

### 封面不要用流式 `\vspace*` 定位标题

封面若用 `\vspace*{...}` + `\vfill` 排版，标题位置会随 `\vfill` 分配结果漂移，顶部装饰色带一旦高于标题起点就会压住标题。改为 **TikZ 绝对定位**：

```latex
\node[anchor=north,align=center,inner sep=0pt,text width=0.94\paperwidth]
  at ([yshift=-2.15cm]current page.north) { 题目 / 副标题 / 装饰线 };
\node[anchor=south,align=center,...] at ([yshift=1.64cm]current page.south) { 作者信息 };
```

色带高 `h cm`（如 1.7cm + 0.12cm 红线）时，题目顶端取 `h + 0.33cm` 左右即可稳定脱开。

## B3. 纵向溢出（`Overfull \vbox`）的正确处理顺序

双语帧的内容量约为纯中文的两倍，密集帧会超出正文区，表现为**正文穿过页脚、底部被页面裁切**。

先量清楚可用高度（在 `\begin{document}` 后临时插一行）：

```latex
\typeout{CUZDIM paperheight=\the\paperheight textheight=\the\textheight textwidth=\the\textwidth}
```

16:9 / 10pt 实测：`paperheight 256.07pt`、`textheight 244.43pt`、`textwidth 398.34pt`，扣除标题色带与页脚后**每帧正文可用高度约 190pt**。按这个数估算要砍掉多少。

**处理顺序（由粗到细，别跳步）**：

1. **全局收紧** —— 英文次级字号降一档（`\footnotesize → \scriptsize`）、统一压紧 `\itemsep`、给所有插图同时给 `width` 与 `height` 上限并开 `keepaspectratio`。
2. **真实减量** —— 把明显超长的帧**拆成两帧**（唯一不损伤可读性的办法）。图多的帧单独调小图高：**图片高度不随文字重排缩放**，所以图片帧只能压图，压不动字。
3. **逐帧兜底** —— 只给仍超长的帧加 `shrink=N`，`N` 由实测溢出量反推（`N ≈ 100·溢出/(190+溢出)` 再加 5% 余量）。
4. 横向溢出（`Overfull \hbox`）多为表格超宽 → 表格外套 `\resizebox{\linewidth}{!}{...}`。

### 铁律：绝不要给全篇统一加 `shrink=N`

`shrink` **不是「按需缩放」**。源码 `beamerbaseframesize.sty` 里 `\beamer@shrinkframebox` 中「仅当超长才缩」的判断（`\ifdim\@tempdima>\beamer@frametextheight`）**被注释掉了**，因此：

> 只要该帧写了 `shrink=N`，就**必然**缩到 `min(需要的比例, 1−N/100)`。内容按 `1/(1−N/100)` **加宽重排**后再整体缩放；本来就装得下的帧也会被缩满 `N%`。

后果：给全篇 48 帧统一加 `shrink=25` 虽然能把溢出清零，但**每一页字号都小 25%、底部大片留白**，整册看起来又小又空。所以 `shrink` 只能**逐帧**用在真正需要的那几帧上。

### 定位「哪一帧溢出」

工程里逐个对页码费力且易错，直接在 `\bframe` 里临时插标记：

```latex
\newcommand{\bframe}[2]{\typeout{CUZFRAME f=\insertframenumber\ T=#1}\frametitle{#1}\framesubtitle{#2}}
```

日志会按顺序输出「帧号 + 标题」。把每条 `Overfull \vbox` 归属到**它前面最近的一个 `CUZFRAME`**，就得到「帧 → 溢出量」映射，一次定位全部问题页；测完删掉这行标记。

### 复核留白：别靠肉眼

渲染全部页面（`pdftoppm -r 100 -png`），逐页测「正文墨迹底边」到正文区底边的间距。本册实测**中位数 13pt** 属正常；若某页 > 55pt 说明该帧留白过多，多半是 `shrink` 给大了或内容被拆得太散。

### 编译与验收命令

```bash
xelatex -shell-escape -interaction=nonstopmode -file-line-error -output-directory=build main.tex
xelatex -shell-escape -interaction=nonstopmode -file-line-error -output-directory=build main.tex
grep -cE "^!" build/main.log                  # 期望 0
grep -c "Overfull\|Underfull" build/main.log  # 期望 0
pdfinfo build/main.pdf | grep -i pages
```

## B4. 其他高频坑（都会静默出错或只报轻微警告）

| 现象 | 起因 | 解法 |
|---|---|---|
| 帧含代码块直接编译失败 | `lstlisting` 是 verbatim 内容，与 beamer 预读冲突 | 该帧加 `[fragile]` |
| **每帧恒定**溢出同一个值（如 56.9pt） | 页脚用多个 `beamercolorbox` 拼宽度，宽度和略超纸宽 | 改单个 `\hbox to\paperwidth{...\hfill...}` |
| 帧标题下的 `\rule{\paperwidth}` 触发溢出 | 规则线宽度算法与页脚叠加 | 改 `\hrule` |
| TikZ 相对定位（`right=of x`）**静默失效**、节点全叠在一起 | 未加载 `positioning` 库，**不报错** | `\usetikzlibrary{positioning,calc,fit,backgrounds}` |
| TikZ 全屏覆盖层与正文文字重叠 | overlay 层与帧正文在同一布局区 | 覆盖层只做背景填充，文字改回普通居中排版 |

## B5. 版面审计：三项自动检测（不要靠肉眼）

遮挡量级常常只有几个 pt，**肉眼会漏**（曾经出现"某页看着没问题、实测首行已在色带下方 0.4pt"）。用 `pdftoppm` + `pdftotext -bbox` 逐页量化：

```bash
"<python>" scripts/layout_audit.py main.pdf 200      # 逐页数据 + 三项判定
"<python>" scripts/band_geometry.py <png> <dpi>      # 量单页色带上下边界（标定参数时用）
```

输出逐页数据与三项判定（阈值均为 2pt）：

| 检查项 | 判据 | 通过标准 |
|---|---|---|
| 上遮挡 | 正文首行 `yMin` − 色带下沿 | ≥ 2pt（健康值 8–9pt） |
| 下压页脚 | 页脚文字 `yMin` − 正文最大 `yMax` | ≥ 2pt |
| 页顶裁切 | 色带最上 3 行内是否出现文字像素 | 无 |

最后仍需**一次全篇缩略图目视**（把 N 页缩略图拼成网格看一遍），确认层级与风格统一。

## B6. 经验条目

- 判定"页数达标"时，封面/目录/章节分隔页/致谢页**不计入**有效内容页；各章要有分隔页与本章小结页。
- 英文次级文字用 `\footnotesize` 而不是 `\small`：显著降低英文折行率，从源头减少帧体撑高。内容特别密（双语逐节翻译整篇论文）时再降到 `\scriptsize`，并用 `\scriptsize` 承载区块/题注文字。
- 中英双语的排版改动要**一处宏改动、全篇生效**，不要逐页手调（否则 40+ 页必然风格漂移）。
- 翻译整篇论文做双语 deck 时，内容量约为原文的两倍：**先把每节拆成 2–3 帧**再填内容，比事后补救溢出省力得多；「一帧一个论点」比「一帧塞完一节」更稳。
- 页码/总页数与章节分隔页要对得上：目录条目数应与 `\sectionslide` 数量一致，改章节结构后记得同步目录。
- 交付前做一次"删空中间产物重建"，确认源码可独立编译；更严格的验收是**把交付 zip 解到空目录再编一遍**（能暴露漏打包的图片与样式文件）。

---

## 交付约定（本项目/本用户）

- 命名分两种：**作业/课程提交**用 `学号-姓名-简历`；**对外求职简历**用 `姓名-简历`，**不带学号**。换模板做新版时加 `-新模版` 后缀，**不覆盖旧版**。用户说「把学号去掉」时先 grep 正文 —— 学号通常只在**文件名/目录名**里，正文没有，改目录名 + 输出 PDF 名即可。
- 交付物：`*.tex` + `*.pdf` + 素材（`photo.jpg` / `qr*.png`）+ `README.md`，**以散文件形式留在工程目录，不打包 zip**（用户 2026-09-26 明确要求「以后不用压缩」）。
- 原始下载网页 / 原始模板文件保持**未改动**，填充后的版本另存为新文件。
- 临时文件（`*.aux` `*.log` `*.out`、预览 png、构建日志、临时 Python 脚本）交付前删干净。
- 用系统 Python 跑打包/提取脚本（写文件再执行，不要 heredoc）。
