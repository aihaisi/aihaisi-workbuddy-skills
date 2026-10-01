---
name: webgl-postproc-pipeline
description: 用单个 HTML 文件搭一条 WebGL2 后处理管线（多 pass ping-pong、半分辨率 bloom 辅助 RT、着色器逐 pass 编译隔离），并把它接成一个"AI 只输出参数配方、GPU 做实时渲染"的演示程序。当需要写实时滤镜/调色管线、把 LLM 输出映射成 uniform、做零依赖的单文件 GPU 演示、或用无头 Chrome 真机验证着色器是否真的能编译出图时使用。
agent_created: true
---

# WebGL2 后处理管线（单文件 + AI 参数配方）

## 这个技能解决什么

把"自然语言 → 结构化参数 → GPU 实时渲染"做成一个可交付的东西。典型场景：

- 简历/作品集里要展示"我接入了 AI"，但**不想**做成文生图（出静态像素、不可调、不进实时管线）。
- 需要一条能跑在浏览器里的多 pass 后处理链（调色 / bloom / 色差 / 半调 / 颗粒 / 暗角）。
- 需要无外部依赖、无 key、双击即开的单文件交付物。
- 需要**真机验证**着色器不是"看起来对"而是真的编译通过并出了图。

核心论点一句话：**AI 只输出配方（JSON 参数），渲染由 GPU 执行。** 配方可复现、可调、可动画、可进实时管线——这是文生图做不到的。

---

## 架构：声明式 pass 注册表

不要写"依次调用 8 个函数"的命令式管线。每个 pass 只**声明**四件事，执行器只认三种 kind：

```js
const PASS_DEFS = [
  { id:'grade',      kind:'full', fs:'grade',      enabled:true },
  { id:'bloomBright',kind:'aux',  fs:'bright',     enabled:true, readFrom:'',      writeTo:'bloomA', scale:0.5 },
  { id:'bloomBlurH', kind:'aux',  fs:'blur',       enabled:true, readFrom:'bloomA',writeTo:'bloomB', scale:0.5, dir:[1,0] },
  { id:'bloomBlurV', kind:'aux',  fs:'blur',       enabled:true, readFrom:'bloomB',writeTo:'bloomA', scale:0.5, dir:[0,1] },
  { id:'edge',       kind:'full', fs:'edge',       enabled:true },
  { id:'aberration', kind:'full', fs:'aberration', enabled:true },
  { id:'halftone',   kind:'full', fs:'halftone',   enabled:true },
  { id:'composite',  kind:'final',fs:'composite',  enabled:true },
];
```

- `full`：乒乓 RT，读一个写另一个。
- `aux`：半分辨率辅助 RT（bloom 专用），显式声明 `readFrom` / `writeTo`。
- `final`：直接画到屏幕。

执行器：

```js
let read = this.rt[0].tex; let wi = 1; this.bloomTex = null;
for (const p of this.passes) {
  if (!p.enabled || !p.program) continue;
  const d = p.def;
  if (d.kind === 'full') {
    const dst = this.rt[wi]; this._draw(p, read, dst, recipe, time);
    read = dst.tex; wi ^= 1; n++;
  } else if (d.kind === 'aux') {
    const src = d.readFrom === 'bloomA' ? this.auxA.tex
              : d.readFrom === 'bloomB' ? this.auxB.tex : read;
    const dst = d.writeTo === 'bloomB' ? this.auxB : this.auxA;
    this._draw(p, src, dst, recipe, time);
    if (d.writeTo === 'bloomA') this.bloomTex = dst.tex;
    n++;
  } else { this._draw(p, read, null, recipe, time); n++; }
}
```

**为什么值得这么做**：加一个 pass = 加一行声明 + 一个 FS，不用碰执行器；UI 的 pass 开关列表、滑块条数、JSON 面板都从这张表生成，三处不会漂移。

**乒乓铁律**：`read` 和 `dst` 永远不能是同一张 RT。一旦相同就是采样自己，出反馈纹或黑屏，而且不会报错。

---

## 六个高发坑

### 1. 屏幕空间尺寸必须按像素算，不能按 UV

`floor(vUV * scale * 900.0)` 这种写法在 Canvas 变宽/变密之后格子就小于一个像素，`floor()` 开始跳格采样，噪点退化成**规则网格摩尔纹**。

```glsl
uniform vec2 uRes;   // 画布像素尺寸，每帧更新
// ✗ float g = hash(floor(vUV * uGrainScale * 900.0));
// ✓
float g = hash(floor(vUV * uRes / max(uGrainScale, 0.5)) + vec2(uTime*61.0, uTime*37.0));
```

同类问题也出现在半调网点（halftone）、扫描线（scanline）上。判据：**任何"格子/条纹/网点"类效果，尺寸的基准单位要么是 px，要么是物理常量，绝不能是 UV 乘以一个无量纲放大系数。**

先按 UV 写完再改成 px 的代价：这个 bug 在逻辑断言里完全看不见（数值不变、方向不错），**只有截图能发现**。

### 2. Patch 语义必须统一：anchor 是绝对值，modifier 是增量

风格配方由两种 patch 混出来：
- **anchor**（赛博朋克/胶片/水墨…）= 绝对目标值，比如 `gamma: [1.06,1.00,0.94]`。
- **modifier**（再暗一点/更饱和）= 加性增量。

一旦 anchor 里混进增量写法，叠加就会**静默翻倍**。曾出现 `gamma: [1.707,1.667,1.627]`——64 条断言全绿，因为断言只查相对方向，不查绝对值。**唯一发现渠道是渲染截图**。

正确的混法（加权平均 + 残差保护）：

```js
function blendAnchors(entries) {
  const list = entries.slice();
  let sum = 0; list.forEach(e => { sum += e.k; });
  if (sum > 1) { list.forEach(e => { e.k = e.k / sum; }); sum = 1; }  // 必须先归一化
  const residual = Math.max(0, 1 - sum);
  const base = baseRecipe(); const out = baseRecipe();
  (function walk(node, baseNode, prefix) {
    Object.keys(node).forEach(key => {
      if (key === 'name') return;
      const path = prefix ? prefix + '.' + key : key;
      const nv = node[key]; const bv = baseNode ? baseNode[key] : undefined;
      if (typeof nv === 'number') {
        const b = (typeof bv === 'number') ? bv : 0;
        let acc = b * residual;
        list.forEach(e => { const v = deepGet(e.patch, path);
          acc += e.k * ((typeof v === 'number') ? v : b); });   // 缺失字段默认取 base
        node[key] = acc;
      } else if (Array.isArray(nv)) { /* 逐分量同样处理 */ }
      else if (nv && typeof nv === 'object') { walk(nv, bv, path); }
    });
  })(out, base, '');
  return out;
}
```

**回归断言（必须加）**：任意 anchor **单独**应用后，每个数值都必须已经落在它注册的 `RANGES` 区间内，且不能触发 clamp。这条断言专治语义混用。

### 3. 源图比画布大得多时，缩采样必须开 mipmap

原图 4000px、画布 730px，`LINEAR` 采样直接丢像素，整体亮度会漂移，看起来像"你的调色算错了"。

```js
gl.bindTexture(gl.TEXTURE_2D, this.srcTex);
gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, source);
gl.generateMipmap(gl.TEXTURE_2D);                       // 关键
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
```

`texImage2D` 之后必须显式 `generateMipmap`，WebGL 不会自动生成。

### 4. 一个 pass 编译失败不能拖垮整条管线

着色器编译失败时，如果构造函数直接抛，整个程序连 UI 都起不来，而且用户看不到是哪一段 GLSL 坏了。

```js
passes.forEach(p => {
  try { p.program = makeProgram(gl, FS[p.def.fs]); p.loc = {}; }
  catch (e) {
    p.program = null; p.broken = true; p.enabled = false;
    self.errors.push({ pass: p.def.id, message: e.message });   // 收集，不抛
  }
});
```

UI 侧把 `errors` 显示出来，坏的 pass 在列表里标灰跳过。**验证脚本要断言 `ERRORS.length === 0`**——否则"跑起来了"和"8 个 pass 有 3 个是死的"看起来一样。

### 5. 单文件构建会无声漂移

`src/*.js` 分段写、`build.py` 内联成 `index.html`，很容易改了 `src/` 忘了跑构建，于是在旧的 `index.html` 上验证。**改完 `src/` 立刻重跑构建并复核字节数**：

```
built index.html  85.6 KB  (4 scripts + 1 stylesheet inlined)
```

### 6. 一个渐变只能表达一个方向 —— 程序化素材的软边得自己切

要给程序化生成的素材（示例图、占位图、程序化贴图）画一条柔和的条带（灯光带、倒影、光束），最自然的写法是错的：

```js
// ✗ 只有纵向衰减，左右是刀切的直线
const g = ctx.createLinearGradient(0, horizon, 0, h);
g.addColorStop(0, 'rgba(255,214,156,0.50)');
g.addColorStop(1, 'rgba(255,150,90,0)');
ctx.fillStyle = g;
ctx.fillRect(sx - w * 0.022, horizon, w * 0.044, h - horizon);
```

问题不会在源图上暴露 —— 源图看着还行。**它在你把对比拉高之后才暴露**：调色 pass 一放大对比，那两条直边就变成刺眼的矩形亮斑，看起来像后处理链出了 bug，于是你会去查错地方。（实测来源：这条让我花了一个小时排查管线。）

一个 gradient 无法同时表达两个方向。做法是沿主轴切 N 条窄带，每条内部用垂直于主轴的软边渐变，带与带之间让 alpha 和宽度连续变化：

```js
const BANDS = 64, depth = h - horizon;
ctx.save();
ctx.beginPath(); ctx.rect(0, horizon, w, depth); ctx.clip();
for (let i = 0; i < BANDS; i++) {
  const t = (i + 0.5) / BANDS;
  const half = w * (0.014 + t * 0.030);        // 沿主轴变宽
  const a = 0.55 * Math.pow(1 - t, 1.5);       // 沿主轴衰减
  if (a < 0.004) continue;
  const g = ctx.createLinearGradient(sx - half, 0, sx + half, 0);   // ← 横向软边
  g.addColorStop(0.00, 'rgba(255,206,150,0)');
  g.addColorStop(0.50, 'rgba(255,222,172,' + a.toFixed(3) + ')');
  g.addColorStop(1.00, 'rgba(255,206,150,0)');
  ctx.fillStyle = g;
  ctx.fillRect(sx - half, horizon + t * depth, half * 2, depth / BANDS + 1);  // +1 防露缝
}
ctx.restore();
```

判据：**任何"从左到右看着均匀、只沿一个方向变化"的素材，都要先问一句"另一个方向的边界长什么样"。** 修复后该区域最大单列跳变从 +15.2 降到 +5.5。

---

## 画面出问题时的定位流程（比结论更值得抄）

看到可疑的块/带/条纹时，**不要读代码猜**。三步：

**① 先分清是源图自带还是管线产生。**
把除最上游一个 pass 之外的全部关掉（例如只留调色），异常还在 → 不在后处理链里，去查素材/输入。这一步通常就能排除掉一大半。

**② 单变量隔离 + 数值指标，而不是肉眼。**
写一个读 `location.hash` 决定关掉哪一项的驱动，对 N 个变体各截一张图；再用脚本给它们排序。

- 驱动模板：`assets/iso-driver.js`
- 排序脚本：`scripts/iso_analyze.py`
- 指标：**竖向边缘能量**（列间亮度差）、**列均值剖面上的硬台阶数**（相邻列跳变超阈值）

```bash
python _iso.py && python _iso_analyze.py
```

比"盯着代码想"快一个数量级，而且结论可复现。

**③ 改完立刻补断言，并证明断言有牙齿。**
用记录式 canvas 桩（见 `_smoke.js` 的 B7 组）把"画出来的形状"断言下来，再做变异测试：把代码改回旧写法，**必须看到断言失败**。改不挂的断言等于没写。

⚠️ **`uTime` 驱动的效果在测试里必须显式传时间。**
故障/闪烁类效果常按 `floor(uTime * 9.0)` 抖动。若测试里用 `performance.now()`，同一配方的两次抓取不可复现，隔离实验会得出随机结论。给验证钩子加一个"固定时间渲染"原语：

```js
grab: function (r, w, h, t) {
  if (r) applyRecipe(r);
  pipeline.render(recipe, (typeof t === 'number') ? t : 7.0);   // ← 固定时间
  /* ... 抓 w×h 亮度阵列 ... */
}
```

---

## 无头验证：证明着色器真的编译并出图

逻辑断言（node + vm 跑纯函数）**查不出几何/视觉 bug**。前面两个真 bug（gamma 翻倍、颗粒摩尔纹）都是靠真机渲染才发现的。所以必须补一层 GPU 验证。

用 `assets/gltest-driver.js` + `scripts/splice_gltest.py`：

1. `splice_gltest.py` 把驱动的 `<script>` 拼进单文件 HTML，产出 `_gltest.html`（含 `</script>` 转义）。
2. 无头 Chrome 打开它，页面自己跑断言，把结果写进 `document.title` / 一个 `<pre>`。
3. `--dump-dom` 取回结果——不需要 CDP、不需要 puppeteer、不需要 npm。

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu-sandbox --no-sandbox \
  --enable-unsafe-swiftshader --use-angle=swiftshader \
  --virtual-time-budget=8000 \
  --dump-dom "file:///D:/path/_gltest.html" > /tmp/dom.html
```

Windows 上两个必踩点：
- **`--screenshot=` 必须给绝对 Windows 路径**（`--screenshot=D:/proj/_out/shot.png`）。相对路径会报 *"Failed to write file ... 系统找不到指定的路径"*。
- `--headless=old` 已移除，写了会拉起 GUI 浏览器并**挂住**。用 `--headless=new`。

驱动里至少放四条断言：

| 断言 | 判据 | 抓什么 |
|---|---|---|
| `GL_OK` | 拿到 WebGL2 context | 环境/版本问题 |
| `ERRORS=[]` | 无 pass 编译失败 | 死 pass 混在管线里 |
| `NEUTRAL_IDENTITY` | 中性配方渲染结果 ≈ 原图（16×16 灰度签名，漂移 < 2/255） | 管线本身在偷偷改色 |
| `DISTINCT_MEANS` | N 个不同 prompt 产出 N 个不同结果 | 参数没真的接到 uniform 上 |

取签名时最容易犯的错：**对照图和渲染图必须用同一套裁剪**。曾经 `sourceSig()` 用 `drawCover(..., 16, 16)` 而 `sig()` 是对 GL 画布缩采样，两者裁的不是同一块画面，漂移 12.96，差点被误判成"着色器有 bug"。修正为在 `sourceSig()` 里复刻完全相同的 cover 裁剪后，漂移降到 0.25：

```js
const iw = sourceCanvas.width, ih = sourceCanvas.height;
const sa = iw / ih, ta = view.width / view.height;
let sx = 1, sy = 1;
if (sa > ta) sx = ta / sa; else sy = sa / ta;
const cw = iw * sx, ch = ih * sy;
x.drawImage(sourceCanvas, (iw - cw) / 2, (ih - ch) / 2, cw, ch, 0, 0, 16, 16);
```

---

## 关键词匹配层的两条防错（AI 解析侧）

把中文自然语言解析成配方时，字典匹配有两个静默错误：

- **长词优先 + 区间互斥**：`赛博朋克` 不能同时命中 `赛博`，否则权重翻倍。
- **字符位掩码**：程度词不能出现在关键词**内部**——`极简` 里的 `极` 不是"极（程度副词）"。给所有已命中的关键词区间打上 mask，程度词扫描时跳过被占用的位：

```js
const mask = new Array(text.length).fill(false);
hits.forEach(h => { for (let i = h.at; i < h.at + h.len; i++) mask[i] = true; });
```

---

## 交付形态约定

- 单文件 `index.html`，零外部请求、零 key、双击即开。
- `src/`（`styles.css` / `body.html` / 各 `.js`）+ `build.py` 内联构建。
- `_smoke.js` 逻辑断言 + `_gltest.html` 真机断言，两层都要跑。
- LLM 侧走 OpenAI 兼容协议，默认指向本地 `http://127.0.0.1:8080/v1`（llama.cpp，无需 key），并保留纯字典的离线回退——**演示不能依赖现场有网**。
- 系统提示词里必须明确写"**不是生成新图像**，只输出一个 JSON 对象"，并把所有可调参数的路径连同中性值列全，否则模型会自由发挥出不存在的字段。

## Resources

- `assets/gltest-driver.js` — 通用无头 GL 验证驱动模板，自动探测页面里的 `window.__XXX__` 钩子。
- `assets/iso-driver.js` — 单变量隔离驱动模板：读 `location.hash#v=<变体>`，套用"该配方但关掉一项"，供逐变体截图。
- `scripts/splice_gltest.py` — 把驱动拼进单文件 HTML 的脚本，处理 `</script>` 转义。
- `scripts/iso_analyze.py` — 把逐变体截图按"竖向边缘能量 / 列均值硬台阶数"排序，定位异常出自哪一环。

## 相关技能

- 单文件 HTML 原型的**交付期验证**（DOM 桩冒烟断言、无头 Chrome 真渲染布局、发布成分享链接）走 `html-prototype-verify-ship`，不要在本技能里重复造。
- **玩法/算法层**的可计算验证（这个玩法有没有决策空间、AI 是不是真的最优）、以及断言失效模式（恒真式／空集恒真／统计抽样／过拟合钉实现细节）与变异测试纪律，走 `gameplay-design-verification`。
