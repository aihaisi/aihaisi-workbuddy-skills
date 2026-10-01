---
name: verify-responsive-layout-headless
description: 用本机无头 Chrome 验证网页在手机竖屏下的真实布局——精确指定视口宽度、判断元素是否横向出界、并出截图。覆盖三个高发误判：--window-size 被 Windows 最小窗口宽度钳到 512px、已移除的 --headless=old 会拉起 GUI 浏览器并挂住、从父窗口给 iframe 里的全局变量赋值不生效（词法绑定）导致"测的其实不是最坏情况"。当用户说"手机端样式错位""竖屏显示不对""做一下移动端适配""响应式有问题"时使用。
agent_created: true
---

# 用无头 Chrome 验证响应式布局

视觉问题**逻辑测试证明不了**。日志全绿 ≠ 版式正确。必须真渲染一遍，而且要和改动前对照。

## 0. 先别猜，先定位根因

**"整体偏移 / 边缘被切"几乎都是同一个根因**：元素实际宽度 > 视口宽度，而父容器是居中布局
（`display:flex; align-items:center` 或 `margin:auto`），于是溢出部分**向两侧均分滑出屏幕**——
左侧那半看不见，右侧那半也看不见，看起来就像"整块往左偏了"。

排查顺序：
1. 找**固定像素宽度**：`width: 400px`、`width: 80px` 这类。注意 `box-sizing` 不是 border-box 时，
   `width + padding + border` 才是真实占宽（`width:400px; padding:10px` ⇒ 实际 422px）。
2. 找**固定尺寸的横向排布**：`n × 单块宽 + (n-1) × gap` 是否超过视口。
3. 先上全局 `*, *::before, *::after { box-sizing: border-box }`——改动最小、收益最大。

## 1. ⚠️ 视口必须用 iframe 指定，`--window-size` 靠不住

Windows 下 Chrome 无头窗口有**约 512px 的最小宽度**。`--window-size=390,844` 会被钳到 512，
量出来的 `innerWidth` 是 512 而不是 390——三个手机尺寸会得到完全相同的结果，看起来"测了"其实没测。

正确做法：用 iframe 给内层文档一个精确视口。

```html
<iframe id="f" src="after.html" style="width:390px;height:844px;border:0"></iframe>
```

```bash
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --allow-file-access-from-files --window-size=900,1100 \
  --virtual-time-budget=3000 --dump-dom "file:///<harness.html>"
```

- 外层窗口开大一点（900×1100）无所谓，内层 iframe 才是被测视口。
- `--allow-file-access-from-files` 必需，否则父页面读不到 iframe 的 DOM（file:// 同源限制）。
- `--dump-dom` 会在跑完 JS 后输出 DOM，把测量结果写进 `<title>` 再 grep 出来，是最省事的回传通道。

## 2. ⚠️ `--headless=old` 已经没了，别用

新版 Chrome 移除了老无头模式。传 `--headless=old` 不会报错，而是**直接拉起 GUI Chrome 并挂住**，
命令一直不返回直到被超时杀掉。看到进程里出现 chrome.exe 记得 `taskkill //IM chrome.exe //F`。

## 3. ⚠️ 想控制页面内部状态，必须注入脚本，不能从父窗口赋值

被测页面里 `let plates = [...]` 这种顶层声明是**全局词法绑定**，不是 `window` 的属性。
从父窗口写 `iframeWin.plates = [...]` 只会新建一个 window 属性，页面函数读到的仍是原值——
**你以为在测最坏情况，其实测的是随机情况**。这种"测量本身是假的"最难发现。

正确做法：往 iframe 里 `appendChild` 一个 `<script>`，它和页面脚本同处一个 realm：

```js
var s = doc.createElement('script');
s.textContent = 'plates=[6,6,6,6,6]; renderBoard(); window.__len = plates.length;';
doc.body.appendChild(s);
```

**并且一定要在脚本内读回关键量（`__len`）自证生效**，把它打进度量结果里。
`盘数=5(脚本内读回 5)` 才有说服力；只写 `盘数=5` 可能是随机的。

## 4. 量什么（不要只量 body 直接子块）

`width:100%` 的容器永远不出界，**里面的子元素出界它也不会露马脚**。要量到元素本体：

| 指标 | 判据 |
|---|---|
| `doc.documentElement.scrollWidth > innerWidth` | 有横向滚动 ⇒ 出问题 |
| 每个关键元素的 `getBoundingClientRect()` | `left < 0` 或 `right > innerWidth` ⇒ 出界 |
| 子元素 `offsetTop` 去重后的个数 | 判断是否意外换行 / 内容挤成细长条 |
| 容器 `scrollWidth > clientWidth` | 容器内部溢出 |

## 5. 与改动前对照（最关键的一步）

```bash
git show HEAD:index.html > before-raw.html     # 沙箱内 node 起不了子进程，git 放 bash 侧
```

同一套 harness 跑 before / after，**用同一套指标**。报告格式用"改前 → 改后"成对呈现，
比单说"改好了"可信得多。别忘了**加一档桌面宽度（1440px）做回归对照**——
`clamp()` 的上限要刻意取回原值，才能保证桌面端版式不动。

## 6. emoji / 图标的宽度陷阱

图标字号不等于占宽：**emoji 的实际占宽约为字号的 1.17 倍**。
`62px` 宽的容器配 `font-size:15px`，按字号算"能放 2 个"，实际只放得下 1 个，
容器里 6 个图标会被排成 6 行、整体拉成细长条。

**判断依据只能是实测的 `offsetTop` 行数**，不能靠字号估算。缩到 `13px` 这类值再复测一遍。

## 7. 收尾

- 出两张截图（正常态 + 展开/交互态），人眼过一遍——测量说"没出界"不代表"不难看"
- 改完跑一次项目自带的逻辑验证器，确认样式改动没连带弄坏功能
- 临时 harness 全部放系统临时目录，别在项目里留探针文件；保留最终截图即可
