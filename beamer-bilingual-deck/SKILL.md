---
name: beamer-bilingual-deck
description: 用 XeLaTeX/ctexbeamer 制作或修复「同页中英双语」Beamer 幻灯片——主题与双语宏骨架、帧标题色带几何、纵向溢出（Overfull \vbox）的正确处理顺序与 shrink 陷阱、以及用 pdftoppm+pdftotext 做的逐页版面量化审计。当任务涉及做双语 PPT/幻灯片、Beamer 中文演示文稿、或出现「标题被色带压住 / 文字被遮挡 / 标题被页顶裁切 / 满页帧纵向溢出 / 正文压到页脚 / 字号莫名变小且底部大片留白」这类版式缺陷时使用。
agent_created: true
---

# 中英双语 Beamer 幻灯片的搭建与版面审计

## 何时用

- 要交付一份中文/双语 Beamer 演示文稿（课程作业、答辩、汇报）
- 已有 Beamer 工程，但出现版式缺陷：文字被标题色带遮挡、标题被裁、满页帧溢出、正文压页脚
- 需要**量化验收**版面（而不是"我看了一遍觉得没问题"）

## 〇、开工前预检（3 分钟，能省掉后面半小时）

本技能里的多数坑，**都不是难在修，而是难在"发现得太晚"**。动手写内容之前先做这三项：

### 1. 素材健康度抽检（做"整篇论文翻译"类 deck 时必做）

不要拿到 PDF 就开始逐图裁剪。先抽 3–5 张图做体检：

```python
import fitz                                   # PyMuPDF
from PIL import Image, ImageStat
doc = fitz.open('paper.pdf')
# ① 该页到底有没有栅格图元？
for pno in [2, 3, 5]:
    page = doc[pno]
    print(pno, len(page.get_images(full=True)), len(page.get_drawings()))
# ② 渲染后测墨迹率：< 5% 基本可判定"图是空的"
im = Image.open('crop.png').convert('L')
s = ImageStat.Stat(im)
print('ink coverage = %.1f%%' % (100 - s.mean[0] / 255 * 100))
```

**关键判据**：`get_images()` 返回空 且 渲染后只剩文字标注 → 这张图在 PDF 里**根本没有内容**，
不是你的裁切坐标错。此时继续重裁 10 次也没用。

已知案例：**arXiv 版的很多主图是空的**。解法是下载 e-print 源码包取原始矢量图：

```bash
curl -x http://127.0.0.1:7897 -L -o src.tar.gz https://arxiv.org/e-print/<arXiv-id>
tar xzf src.tar.gz -C src/          # 里面有 figs/*.pdf 原始矢量图 + sec_*.tex + *.bib
```

用 `figs/` 里的矢量图重渲染，清晰度比 PDF 裁切更好，还能顺便核对英文原文与文献条目。

### 2. 影响范围大的参数，先单帧试跑

`shrink`、`\footnotesize→\scriptsize` 这类"一处改动全篇生效"的东西，
**先在一个测试帧上编一遍看效果**，确认语义符合预期再批量套用。
本技能里 `shrink` 的语义反直觉（见二-bis 铁律），就是靠"先批量、后验证"付出了整册返工的代价。

### 3. 容量估算先行

拿到版面尺寸后（`\typeout{CUZDIM ...}`），先估每节内容大约占多少行 × 行高，
超过 190pt 的**一开始就拆成两帧**，不要写完再补救。
翻译整篇论文做双语 deck 时，内容量约为原文两倍——**按两倍量规划帧数**。

## 一、骨架（可复用的最小结构）

```
<工程>/
├── main.tex                 # 只做 \input，不写正文
├── styles/<theme>.tex       # 主题/配色/页眉页脚/双语宏/代码风格
├── content/00-cover.tex     # 封面 + 目录
├── content/NN-*.tex         # 每章一个文件
└── figures/                 # 图示（优先 TikZ 内联，避免二进制素材）
```

关键选择：

| 项 | 值 | 理由 |
|---|---|---|
| 引擎 | `xelatex` | 中英混排要直接调用系统字体并正确断行 |
| 文档类 | `\documentclass[aspectratio=169,fontset=windows]{ctexbeamer}` | 16:9 原生参数；Windows 字体最稳 |
| 双语实现 | 宏封装，**两个参数必填** | 少写一个直接编译报错 → 结构上保证同页中英一一对应 |

双语宏示例（定义在主题文件里）：

```latex
\newcommand{\bframe}[2]{\frametitle{#1}\framesubtitle{#2}}      % 帧标题 + 英文副标题
\newcommand{\biitem}[2]{\item #1\par\vspace{-0.15em}{\footnotesize\color{gray}#2}\vspace{0.25em}}
\newcommand{\bipara}[2]{#1\par\vspace{0.25em}{\footnotesize\color{gray}#2}\par}
```

## 二、帧标题色带几何（最容易翻车的地方）

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

### 必须知道的机制

- beamer 组装帧时按 **`ht + dp`** 扣减正文可用高度（`beamerbaseframe.sty` 中
  `\advance\beamer@frametextheight by-\ht\beamer@frametitlebox` 之后还有 `-\dp` 与 `-frametopskip`）；
  色带的**绘制**高度同样是 `ht + dp`。
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

负间距**只移动正文，不改变色带的绘制高度**。正文与色带下沿只有约 3.6pt 余量，
上移超过这个值，正文首行就会钻到色带底下被盖住（表现为"每页第一条要点被切掉上半截"）。

**正确做法**：色带显得过高就调小 `ht`/`dp`；色带需要变高导致满页帧溢出，去**压紧那些帧自己的内容**：

```latex
% 满页帧里的表格：压紧行距（每 7 行约省 6–8pt）
{\small\renewcommand{\arraystretch}{0.92}
 \begin{tabular}{...} ... \end{tabular}}
```

### 封面不要用流式 `\vspace*` 定位标题

封面若用 `\vspace*{...}` + `\vfill` 排版，标题位置会随 `\vfill` 分配结果漂移，
顶部装饰色带一旦高于标题起点就会压住标题。改为 **TikZ 绝对定位**：

```latex
\node[anchor=north,align=center,inner sep=0pt,text width=0.94\paperwidth]
  at ([yshift=-2.15cm]current page.north) { 题目 / 副标题 / 装饰线 };
\node[anchor=south,align=center,...] at ([yshift=1.64cm]current page.south) { 作者信息 };
```

色带高 `h cm`（如 1.7cm + 0.12cm 红线）时，题目顶端取 `h + 0.33cm` 左右即可稳定脱开。

## 二-bis、纵向溢出（`Overfull \vbox`）的正确处理顺序

双语帧的内容量约为纯中文的两倍，密集帧会超出正文区，表现为**正文穿过页脚、底部被页面裁切**。

先量清楚可用高度（在 `\begin{document}` 后临时插一行）：

```latex
\typeout{CUZDIM paperheight=\the\paperheight textheight=\the\textheight textwidth=\the\textwidth}
```

16:9 / 10pt 实测：`paperheight 256.07pt`、`textheight 244.43pt`、`textwidth 398.34pt`，
扣除标题色带与页脚后**每帧正文可用高度约 190pt**。按这个数估算要砍掉多少。

**处理顺序（由粗到细，别跳步）**：

1. **全局收紧**——英文次级字号降一档（`\footnotesize → \scriptsize`）、
   统一压紧 `\itemsep`、给所有插图同时给 `width` 与 `height` 上限并开 `keepaspectratio`。
2. **真实减量**——把明显超长的帧**拆成两帧**（唯一不损伤可读性的办法）。
   图多的帧单独调小图高：**图片高度不随文字重排缩放**，所以图片帧只能压图，压不动字。
3. **逐帧兜底**——只给仍超长的帧加 `shrink=N`，`N` 由实测溢出量反推
   （`N ≈ 100·溢出/(190+溢出)` 再加 5% 余量）。
4. 横向溢出（`Overfull \hbox`）多为表格超宽 → 表格外套 `\resizebox{\linewidth}{!}{...}`。

### 铁律：绝不要给全篇统一加 `shrink=N`

`shrink` **不是「按需缩放」**。源码 `beamerbaseframesize.sty` 里
`\beamer@shrinkframebox` 中「仅当超长才缩」的判断
（`\ifdim\@tempdima>\beamer@frametextheight`）**被注释掉了**，因此：

> 只要该帧写了 `shrink=N`，就**必然**缩到 `min(需要的比例, 1−N/100)`。
> 内容按 `1/(1−N/100)` **加宽重排**后再整体缩放；本来就装得下的帧也会被缩满 `N%`。

后果：给全篇 48 帧统一加 `shrink=25` 虽然能把溢出清零，
但**每一页字号都小 25%、底部大片留白**，整册看起来又小又空。
所以 `shrink` 只能**逐帧**用在真正需要的那几帧上。

### 定位「哪一帧溢出」

工程里逐个对页码费力且易错，直接在 `\bframe` 里临时插标记：

```latex
\newcommand{\bframe}[2]{\typeout{CUZFRAME f=\insertframenumber\ T=#1}\frametitle{#1}\framesubtitle{#2}}
```

日志会按顺序输出「帧号 + 标题」。把每条 `Overfull \vbox` 归属到**它前面最近的一个 `CUZFRAME`**，
就得到「帧 → 溢出量」映射，一次定位全部问题页；测完删掉这行标记。

### 复核留白：别靠肉眼

渲染全部页面（`pdftoppm -r 100 -png`），逐页测「正文墨迹底边」到正文区底边的间距。
本册实测**中位数 13pt** 属正常；若某页 > 55pt 说明该帧留白过多，
多半是 `shrink` 给大了或内容被拆得太散。

## 三、其他高频坑（都会静默出错或只报轻微警告）

| 现象 | 起因 | 解法 |
|---|---|---|
| 帧含代码块直接编译失败 | `lstlisting` 是 verbatim 内容，与 beamer 预读冲突 | 该帧加 `[fragile]` |
| **每帧恒定**溢出同一个值（如 56.9pt） | 页脚用多个 `beamercolorbox` 拼宽度，宽度和略超纸宽 | 改单个 `\hbox to\paperwidth{...\hfill...}` |
| 帧标题下的 `\rule{\paperwidth}` 触发溢出 | 规则线宽度算法与页脚叠加 | 改 `\hrule` |
| TikZ 相对定位（`right=of x`）**静默失效**、节点全叠在一起 | 未加载 `positioning` 库，**不报错** | `\usetikzlibrary{positioning,calc,fit,backgrounds}` |
| TikZ 全屏覆盖层与正文文字重叠 | overlay 层与帧正文在同一布局区 | 覆盖层只做背景填充，文字改回普通居中排版 |

## 四、验收：三项自动检测（不要靠肉眼）

遮挡量级常常只有几个 pt，**肉眼会漏**（曾经出现"某页看着没问题、实测首行已在色带下方 0.4pt"）。
用 `pdftoppm` + `pdftotext -bbox` 逐页量化：

```bash
PY=$WORKBUDDY_PYTHON   # 或任意装了 Pillow 的 python
"$PY" scripts/layout_audit.py main.pdf 200
```

输出逐页数据与三项判定（阈值均为 2pt）：

| 检查项 | 判据 | 通过标准 |
|---|---|---|
| 上遮挡 | 正文首行 `yMin` − 色带下沿 | ≥ 2pt（健康值 8–9pt） |
| 下压页脚 | 页脚文字 `yMin` − 正文最大 `yMax` | ≥ 2pt |
| 页顶裁切 | 色带最上 3 行内是否出现文字像素 | 无 |

再用 `scripts/band_geometry.py <png> <dpi>` 量单页色带上下边界（改参数时用来标定）。

最后仍需**一次全篇缩略图目视**（把 N 页缩略图拼成网格看一遍），确认层级与风格统一。

## 五、编译与验收命令

```bash
xelatex -shell-escape -interaction=nonstopmode -file-line-error -output-directory=build main.tex
xelatex -shell-escape -interaction=nonstopmode -file-line-error -output-directory=build main.tex
grep -cE "^!" build/main.log          # 期望 0
grep -c "Overfull\|Underfull" build/main.log   # 期望 0
pdfinfo build/main.pdf | grep -i pages
```

连编两遍是必须的：`\inserttotalframenumber`（页脚"当前页/总页数"）第二遍才稳定。

## 六、经验条目

- 判定"页数达标"时，封面/目录/章节分隔页/致谢页**不计入**有效内容页；各章要有分隔页与本章小结页。
- 英文次级文字用 `\footnotesize` 而不是 `\small`：显著降低英文折行率，从源头减少帧体撑高。
  内容特别密（双语逐节翻译整篇论文）时再降到 `\scriptsize`，并用 `\scriptsize` 承载区块/题注文字。
- 中英双语的排版改动要**一处宏改动、全篇生效**，不要逐页手调（否则 40+ 页必然风格漂移）。
- 翻译整篇论文做双语 deck 时，内容量约为原文的两倍：**先把每节拆成 2–3 帧**再填内容，
  比事后补救溢出省力得多；「一帧一个论点」比「一帧塞完一节」更稳。
- 页码/总页数与章节分隔页要对得上：目录条目数应与 `\sectionslide` 数量一致，改章节结构后记得同步目录。
- 交付前做一次"删空中间产物重建"，确认源码可独立编译；
  更严格的验收是**把交付 zip 解到空目录再编一遍**（能暴露漏打包的图片与样式文件）。
