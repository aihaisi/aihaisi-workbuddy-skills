---
name: code-rendered-video
description: 用代码渲染视频（"AI 做视频"的真实机制）——不是生成式模型出像素，而是写程序描述每一帧、由渲染器逐帧画出来。覆盖两条路线（Remotion 框架 / 裸 HTML+CDP 自建管线）的选择、完整跑批命令、加速渲染（拆阶段定位瓶颈 → 换中间帧格式 → 多进程切帧段，60 分钟降到 3 分钟）、以及本机（Windows + 校园网 + npmmirror）所有实测坑。当用户要"用 AI 做视频/动效视频/科普短片/数据可视化视频/产品演示片"，或问"Claude 怎么做视频""XX 视频是 AI 生成的吗"，或抱怨"渲染太慢/能不能用显卡加速/花了两小时"，或需要搭建、调试、提速逐帧渲染管线时使用。
agent_created: true
---

# 代码渲染视频（Code-as-Video）

## 一句话说清这件事

**"Claude 做的视频"不是模型生成像素，是模型写代码。** 代码描述"第 N 帧长什么样"，
渲染器按代码把几千帧逐帧画好，再编码成 MP4。Claude 演的是导演 + 程序员，
真正"出图"的是浏览器和编码器。

证据级别最高的一条：Remotion 官方维护 Claude Code 插件
（`remotion.dev/docs/ai/claude-code-plugin`），这是框架方自己做的，不是博客转述。

⚠️ **Anthropic 官方从未声称任何 Claude 模型具备视频生成能力。**
官方模型规格里输入输出 profile 是 `text + images → text`，没有视频输出。
"Claude 做视频"是社区行为 + 内容创作者叙事，别当官方能力宣传。

## 何时用这条路（以及何时别用）

| 要做的内容 | 这条路 | 原因 |
|---|---|---|
| 信息图 / 数据可视化 / 科普讲解 | ✅ 最佳 | 文字锐利、数值精确、可校验 |
| 动效排版（kinetic typography） | ✅ 最佳 | 每个元素的坐标和时间都是确定的 |
| 产品演示 / UI 走查 | ✅ 好 | 界面可用代码复刻，比拍屏可控 |
| 数学 / 几何动画 | ✅ 好 | Manim 就是为此而生 |
| 写实人物 / 实拍空镜 / 电影感氛围 | ❌ 别用 | 代码里没有你的厨房。要走生成式视频模型 |
| 需要"一条提示词自动出片" | ❌ 做不到 | 审美判断和节奏仍是人的活 |

🔴 **最关键的判据**：看成品里**有没有清晰文字和精确数字**。
有 ⇒ 一定是代码渲染（生成式模型画字必然是扭曲的鬼画符，这是原理决定的，不是调参能解决）。
没有、全是写实画面 ⇒ 可能是生成式。

## 两条路线怎么选

| | Remotion | 裸 HTML + CDP 逐帧截图 |
|---|---|---|
| 本质 | React 组件 = 视频，官方渲染器 | 自己写 Canvas/SVG，用 Chrome DevTools Protocol 截图 |
| 上手 | 装包即用，有官方 agent skills | 零依赖，但要自己写导出器 |
| 参数校验 | ⭐ zod schema，渲染前拦截，Studio 自动生成表单 | 自己写 JSON Schema + 校验脚本 |
| 预览 | ⭐ Remotion Studio，可实时改 props 看效果 | 要自己起页面 |
| 排版 | DOM/CSS（渐变文字容易） | Canvas 2D（要自己算 measureText） |
| 依赖重量 | 152+ 个包 | 只要 Node + Chrome |
| 适用 | 正规项目、要长期维护 | 一次性、极致可控、不想装依赖 |

**两者共用同一套核心纪律**（见下），视觉配方可以直接互搬 —— 已在 bar-chart 上验证过。

## 铁律（两条路线都一样，违反任何一条成片不可用）

1. **一切由帧号驱动，零 CSS 动画 / 零挂钟时间。**
   所有视觉状态必须是帧号的纯函数。CSS 的 `transition`/`animation`/rAF 时间基准是挂钟时间，
   逐帧截图无法保证「第 f 帧 == 第 f 个时间片」。

2. **随机必须种子化且预生成。**
   `Math.random()` 会让每次导出结果不同 = 不可复现。用 `mulberry32(seed)` 之类的可复现 PRNG。

3. **字体必须等就绪再开始渲染。**
   裸 HTML 要在 `document.fonts.ready` + `fonts.load()` 之后才置 ready 标志；
   否则前若干帧字体回退、字重字距全变。Remotion 用 `@remotion/google-fonts` 或 `delayRender()`。

## 路线 A：Remotion 跑批（本机已实测通过）

### 环境（2026-10-09 实测，Windows）

| 依赖 | 本机状态 |
|---|---|
| Node | v22.22.2（`%USERPROFILE%\.workbuddy\binaries\node\versions\22.22.2-6\node.exe`） |
| npm registry | `registry.npmmirror.com`（**已配好，直连 1.1 秒**） |
| Remotion | 4.0.534 |
| ffmpeg | 8.1.1（winget 装的 gyan.dev full build） |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` |

### 最小工程骨架

```
my-video/
├─ package.json          # remotion + @remotion/cli + react + react-dom + zod
├─ src/index.ts          # registerRoot(RemotionRoot)
├─ src/Root.tsx          # <Composition id durationInFrames fps width height schema defaultProps/>
├─ src/schema.ts         # zod schema —— 参数契约
└─ src/MyComp.tsx        # 组件：useCurrentFrame() + interpolate()
```

### 命令

```bash
cd remotion-lab
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy    # 必须！见坑 1

# 渲染（必须带 --browser-executable，见坑 2）
./node_modules/.bin/remotion render src/index.ts BarChart out/barchart.mp4 \
  --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"

# 预览（Studio，可实时改 props）
./node_modules/.bin/remotion studio src/index.ts

# 只出一张静帧（调试排版最快）
./node_modules/.bin/remotion still src/index.ts BarChart out/frame.png --frame=75

# 外部传参
./node_modules/.bin/remotion render src/index.ts BarChart out/x.mp4 --props=props.json
```

## 路线 B：裸 HTML + CDP 逐帧截图

见本项目 `library/tools/cdp.js`（共享 CDP 客户端）与 `sample-5s/tools/export-frames.js`。

```bash
node <tools>/export-frames.js <html绝对路径> <输出目录> [帧数] [宽] [高] [query]
```

页面必须暴露导出契约：

```js
window.__sample = {
  frames, fps,
  setFrame(f){ /* 渲染第 f 帧 */ },
  ready: false        // 字体就绪后才置 true
};
```

## 🔴 本机实测坑（全部踩过，别重推）

### 坑 1：环境变量里的代理会毒害 npm

Bash 环境被注入了 `HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:2450`，**这个代理不可靠**
（实测 npmjs 直连 000、走它就是超时）。而 `registry.npmmirror.com` 直连只要 1.1 秒。

⇒ **装包前一律 `unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy`**，
并确认 `npm config get registry` 是 `registry.npmmirror.com`。
必要时 `npm config set proxy null && npm config set https-proxy null`。

### 坑 2：Remotion 默认要下载自己的 Chrome Headless Shell

国内网络下这个下载会卡死。**必须传 `--browser-executable` 指向系统 Chrome。**
或写进 `remotion.config.ts`：

```ts
import { Config } from "@remotion/cli/config";
Config.setBrowserExecutable("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe");
```

### 坑 3：esbuild 的 postinstall 在 Windows 上报错，但**不影响使用**

症状：`npm install` 退出码非 0，报 `spawnargs: [...esbuild, '--version']` + `pid: 0`。
真因：postinstall 校验脚本 spawn 无扩展名的 Node shim，Windows 上执行不了。

**判据（别急着回滚）**：`node_modules/@esbuild/win32-x64/esbuild.exe --version` 能打印版本
⇒ 二进制是好的，Remotion 用的是 esbuild 的 **JS API** 不是 CLI，**照常能渲染**。
实测：报错后 `remotion render` 依然成功产出 MP4。

### 坑 4：`--pixel-format=yuv420p` 实测**未生效**（颜色范围是独立参数）

输出仍是 `yuvj420p`。**关键认知：`yuvj420p` 不是另一种像素格式，它是「yuv420p 且
`color_range=pc`（全范围）」的旧别名** —— 所以只写 `-pix_fmt yuv420p` 根本管不到范围，
范围得单独用 `-color_range tv`（再配合 `-vf scale=...,out_range=tv` 真正转换）来管。

多数播放器能放，但若要严格 yuv420p（某些平台上传要求），得转一道：

```bash
ffmpeg -y -i in.mp4 -c:v libx264 -pix_fmt yuv420p -color_range tv \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -crf 18 -c:a copy out.mp4
```

⚠️ **自建管线里还有一个对称的入口**：**输入**是 JPEG 序列时同样会得到
`yuvj420p` / `color_range=pc`（JPEG 本身就是全范围，ffmpeg 原样继承）—— 见下面
「加速渲染」一节的「换 JPEG 之后必须同步修色彩范围」。两处是同一个病：**颜色范围没被显式管过**，
一处出在编码器输出端，一处出在输入源。**凡是切换输入/输出格式，都要回头 diff 一次
`ffprobe -show_streams`，别假设"只是换了压缩算法"。**

### 坑 5：CDP 路线的四个陷阱

见 `library/README.md`「已知坑」表 —— 其中最隐蔽的是**输出目录传相对路径**
⇒ `--user-data-dir` 变相对路径 ⇒ Chrome 静默不写 stderr 的 DevTools 行
⇒ 表现为「等待端口超时」，会被误判成 Chrome 起不来。**一律转绝对路径。**

## 加速渲染：60 分钟 → 3 分钟（约 19 倍，2026-10-12 实测）

### 🔴 第一步永远是「拆阶段」，不是「换硬件」

写个基准脚本，把一个「渲染一帧」拆成三段**分别计时**：① 页内 JS 绘制 + 等两轮 rAF；
② 截图编码（含编码 + base64 + WebSocket 传输）；③ 落盘。

1920×1080、带全屏颗粒背景的一帧实测：

| 阶段 | 耗时 | 占比 |
|---|---|---|
| JS 绘制 + 光栅化 | 36ms | **5%** |
| 截图编码 + 传输 | 707ms | **95%** |
| 合计 | 743ms | |

⇒ **瓶颈是编码器，不是光栅化。** 不看这个数字就买显卡、换框架、上云，方向必错。

三段计时的骨架（任何 CDP 管线都能套，关键是**分开累加、不要只记总时长**）：

```js
let tA = 0, tB = 0, tC = 0;
for (let i = 0; i < N; i++) {           // 先跑 8 帧预热（首帧要编译 / 铺背景）
  let t = Date.now();
  await evalJs(`(async()=>{ setFrame(${f});
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); })()`);
  tA += Date.now() - t;                 // A: 绘制 + 两轮 rAF

  t = Date.now();
  const shot = await send('Page.captureScreenshot',
    { format: 'png', fromSurface: true, captureBeyondViewport: false,
      clip: { x:0, y:0, width:W, height:H, scale:1 } });
  tB += Date.now() - t;                 // B: 编码 + base64 + WebSocket 传输

  t = Date.now();
  fs.writeFileSync(p, Buffer.from(shot.data, 'base64'));
  tC += Date.now() - t;                 // C: 落盘
}
console.log(tA/N, tB/N, tC/N);          // 三个数一出来，方向就定了
```

同时**换格式做对照**：把 `format` 依次设成 `jpeg`（quality 100 / 95）、`webp`，
各跑 N 帧，顺带记体积、并用 `ffmpeg -lavfi psnr` 算相对 PNG 的偏差 —— 一次就把
「哪个格式值得换」和「换掉之后差多少」同时问清。

### GPU 是错的方向（实测只值 11%）

删掉 `--disable-gpu`，加 `--use-angle=d3d11 --use-gl=angle --enable-gpu-rasterization --enable-zero-copy`：

| 光栅后端 | 绘制 | 整帧 |
|---|---|---|
| 软件 SwiftShader（默认） | 36.1ms | 743ms |
| GPU（ANGLE / D3D11） | 12.4ms | 658ms |

绘制确实快了 3 倍，但整帧只省 **11%** —— 因为绘制本来就只占 5%。

⚠️ 两个附带事实：headless 下 ANGLE 默认挑的是**核显**（实测 AMD Radeon 610M），不是独显
（RTX 5060），要指定得另设系统图形首选项；而且引入 GPU 就多出「核显/独显切换 + 驱动版本」
两个新的不可复现变量。**为一个 11% 不值当。**

### 真正的两个杠杆

**① 换掉 PNG：5～7 倍**

| 格式 | 一帧体积 | 编码耗时 |
|---|---|---|
| png | 2099KB | 687ms |
| **jpeg q100** | 1073KB | **139ms** |
| jpeg q95 | 462KB | 94ms |
| webp q95 | 258KB | 217ms |
| webp q100 | 1785KB | **1121ms（比 PNG 还慢 —— WebP 是陷阱）** |

🔴 **为什么「有损」的 JPEG 中间帧等于无损（已证）**：成片最终要过 h264 CRF18，而**这一步自身**
对源帧的误差就有 **39.6dB**；jpeg q100 对源帧的误差是 **53.5dB** —— 高出 14dB，**被彻底淹没**。
实测：两条链路（PNG 入 / JPEG 入）各编一遍 h264 互比 41.9dB；各自 vs 原始无损帧是
40.0 vs 39.6dB —— **JPEG 那条甚至略好**（差异是 x264 码率分配噪声）。
⇒ 判据不是「有损没损」，而是「**中间环节的误差是否显著小于最终编码自身的误差**」。

**② 多进程按帧号切段：2.7 倍**

帧与帧完全独立（都是「全局帧号 → 画面」的纯函数），所以把帧区间均分成 N 段、
每段一个独立浏览器进程，是**安全**的（进程间不共享状态）。

实测（420 帧，jpeg q100）：

| 进程数 | 耗时 | 加速比 |
|---|---|---|
| 1 | 1.1 分钟 | 1.0× |
| **4** | 0.4 分钟 | **2.7×** |
| 8 | 0.4 分钟 | 2.6× |
| 12 | 0.5 分钟 | 2.1×（**反而变慢**） |

⇒ **甜点是 4–6 进程。** 受内存带宽和浏览器启动开销限制，不是核越多越好
（本机 32 逻辑核，12 进程已经亏）。
⚠️ 注意区分：这里说的是**刻意启动多个渲染进程**；另有一条纪律是
**渲染期间不要再并行跑别的浏览器任务**（会把单进程速率拖慢一倍）。

### 🔴 换 JPEG 之后必须同步修色彩范围（否则元数据静默变样）

JPEG 是**全范围**（pc, 0–255）。ffmpeg 读 JPEG 序列时会**原样继承** ⇒ 成片变成
`yuvj420p` / `color_range=pc`，还会捎带一个 JPEG 的 **ICC Profile** side data。
后果：不同播放器解出的亮度不同，而且和 PNG 链路口径不一致（同一工程两套规格，且现场看不出来）。

修法是显式压到 limited(tv) —— 这条对 png（RGB 全范围）和 jpg（yuvj420p）**都成立**，
所以两条链路可以共用一个编码命令：

```bash
ffmpeg -framerate 30 -i "f%05d.$EXT" \
  -vf "scale=in_range=auto:out_range=tv,format=yuv420p" \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 18 -r 30 \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  out.mp4
```

（与上面「坑 4」是同一类问题的两个入口：那条是编码器输出端，这条是输入源。）

### 端到端结果（4830 帧 / 161 秒成片）

| 配置 | 耗时 |
|---|---|
| png 单进程（旧默认） | ~60 分钟 |
| png + GPU 光栅 | 53 分钟 |
| jpeg q100 单进程 | 11 分钟 |
| **jpeg q100 + 6 进程** | **3～5 分钟** |

### 命令与配套纪律

```bash
# ① 先量清楚（改任何配置之前都先跑，别凭感觉）
node tools/bench-render.js  <剧本.json> [镜头id] [采样帧数] [--gpu]   # 阶段分解
node tools/fmt-compare.js   <剧本.json> <镜头id> <章内帧号>          # 体积/耗时/PSNR 对照

# ② 正式渲染
node tools/render-shot.js <剧本.json> all <输出目录> 1920 1080 \
  --workers 6 --fmt jpeg --quality 100
```

- 🔴 **`--gpu` 开关必须显式写出来**（开或关都写）。不写时 headless 的默认行为会随浏览器
  版本变（有时自动选 GPU、有时退回软件），等于把「可复现」赌在版本上。
- 🔴 中间帧落盘约为 PNG 的一半，4800 帧约 3–5GB，排盘时算进去。
- 🔴 参数变了之后要**重新跑一遍质检**（帧数断言 / hold 冻结检测），别默认「换个格式不影响画面」——
  色彩范围这个坑就是换格式带出来的。

## 交付前验证清单（管线层）

本技能只管**"管线跑得对不对"**。管**"成品好不好看、看不看得懂、发到哪去"**的量化验收，
走技能 **`motion-video-quality`** —— 那里有动效密度画像、运动分布热力图、
hold 段冻结检测（含内容区掩码的修法）和发布落点判据。

管线层必查：

1. **帧数对得上**：`ffprobe -show_entries stream=nb_frames` == 预期帧数
2. **时长对得上**：`duration` == 帧数 / fps，精确到小数位
3. **每章 `duration` == 资产 `frames`** —— 不一致 ⇒ 超出的部分钳到最后一帧 ⇒ **尾段整帧冻结**
4. **抽帧目视**：至少抽首帧 / 中段 / 末帧三张，确认不是黑帧、不是字体回退
5. **重复渲染一致性**：渲染两次，比对文件哈希或逐帧像素差 —— 这是"确定性"的唯一硬证据

⚠️ **别把机器渲染时间算成人力时间。** 按默认加速配置（jpeg q100 + 6 进程）是
**25 帧/秒**量级，4800 帧 ≈ 3～5 分钟；哪怕退回保守配置（png 单进程）也只是 3 帧/秒、
4800 帧 ≈ 25 分钟。两种情况都是机器在跑，不是人力工时。

## 参考来源（分级）

**A 级 · 官方一手，可自行打开验证**
- `anthropic.com/claude-opus-5-5` —— 官方发布文（**通篇没提视频**）
- `remotion.dev/docs/ai/claude-code-plugin` —— Remotion 官方插件（可自证）
- `remotion.dev/docs/ai/skills` —— 12 个 agent skills 清单
- `remotion.dev/docs/`（任意页加 `.md` 拿原始 Markdown，专为 AI agent 优化）

**B 级 · 有署名第三方**
- InfoQ《Claude Opus 5.5 并不会"生成"视频：一文拆解代码视频的五步流水线》

**C 级 · ⚠️ 别当证据**
- 搜"Claude 视频生成"排前面的多半是 SEO/营销博客，措辞高度雷同，
  且多家自己在卖"AI 视频工具"。只能当线索。

## Remotion 官方 12 个 skill 清单（供对照，不必逐个装）

`remotion-best-practices`（路由）/ `create` / `markup`（排版动画核心）/
`studio` / `render` / `captions` / `maps` / `saas` / `interactivity` /
`docs` / `upgrade` / `multimedia`

安装（需要能访问 GitHub，本机需代理）：
```bash
npx skills add remotion-dev/skills
```

## 最后的判断

**这条路没有护城河。** Remotion 官方给 Claude Code 做插件，意味着全世界都在用同一套工具链。
差别在**选题、节奏、审美判断** —— 不在"能不能做出来"。
代码能写对是及格线，难的是知道什么节奏好看、哪一章该停几秒。

📌 **开工前先看一眼 `motion-video-quality`** —— 它给的是"做出来好不好"的量化验收标准
（动效密度验收线、hold 冻结判据、手机尺度验证、发布落点）。
本技能解决"能不能做出来"，那份解决"做出来行不行"。
