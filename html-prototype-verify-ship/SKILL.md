---
name: html-prototype-verify-ship
description: 单文件 HTML 原型（小游戏 / 交互 Demo / 仪表盘）的三段式验证与交付——① 无头逻辑冒烟（DOM 桩 + node vm，零依赖，断言协议流程、数值边界、状态机）② 真渲染布局验证（无头 Chrome + iframe 精确视口，查元素横向出界）③ 发布成"点开即玩"的分享链接（专用发布目录 + 一致性断言 + 上线后泄漏专检）。覆盖七个高发误判：--window-size 被 Windows 最小窗口宽度钳到 512px（三个手机尺寸量出同一结果，"测了"其实没测）；已移除的 --headless=old 会拉起 GUI 浏览器并挂住；从父窗口给 iframe 里的顶层 let 赋值不生效（词法绑定）导致测的不是最坏情况；正则扫源码验契约字段是假断言；直接拿项目根目录当发布源会把 .workbuddy/.env 变成公开 URL；发布源是副本时会漂移导致线上跑旧版本；--dump-dom 抓值时首行紧跟 <pre> 标签、正则会漏掉（静默缺失会掩盖真实失败）。当用户说"验证我刚写的 HTML 原型真的能跑""证明这个数值 claim 成立""手机端样式错位""竖屏显示不对""响应式有问题""别人一点就能玩""给我个链接""发个能玩的地址""分享给同学玩""部署上线"时使用。
agent_created: true
---

# 单文件 HTML 原型：验证与发布

## 0. 三个阶段，以及哪一步不能跳

| 阶段 | 手段 | 能证明 | **不能证明** |
|---|---|---|---|
| ① 逻辑冒烟 | DOM 桩 + node `vm`，零依赖 | 协议流程、数值边界、状态机收敛 | 任何**渲染 / 布局 / 像素**问题 |
| ② 真渲染布局 | 无头 Chrome + iframe 精确视口 | 手机竖屏下有没有横向出界 | 逻辑对不对（要回阶段 ①） |
| ③ 发布 | 专用发布目录 + 上线核验 | 别人点开真能玩、没泄漏 | 前三者的任何一条 |

**核心纪律：视觉问题逻辑测试证明不了，逻辑问题截图看不出来。** 两段都要跑，而且阶段 ② 必须和改动前对照。

深度细节（断言失效模式、数值校准、真实翻车案例）：见 `references/smoke-assertions.md`
发布后的运营管理与留痕排查：见 `references/publish-ops.md`

---

# 阶段 ①：逻辑冒烟（node + vm）

## 1.1 核心思路

页面脚本通常把逻辑和 DOM 混在一个 `<script>` 里。用 **DOM 桩 + `vm`** 把它整体加载进 Node，再把内部对象"导出"出来断言。**不重写逻辑、不复制代码** —— 测的就是即将交付的那份文件，避免测试与实现漂移。

```js
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const src = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  + '\nglobalThis.__api = { host, S, CFG, resetAll };\n';
```

顶层 `const` / `let` / `class` 在 `vm` 里是脚本的词法作用域，**不会自动挂到 context 上**，必须靠末尾追加的一行显式导出。按需要什么就导什么。

## 1.2 DOM 桩（够用就好，约 40 行）

```js
function mkEl(tag = 'div') {
  const el = {
    tagName: tag, children: [], dataset: {}, style: {}, textContent: '', _html: '',
    width: 620, height: 400,
    classList: {
      _s: new Set(),
      add(...c){ c.forEach(x=>this._s.add(x)); },
      remove(...c){ c.forEach(x=>this._s.delete(x)); },
      contains(c){ return this._s.has(c); },
      toggle(c){ this._s.has(c)?this._s.delete(c):this._s.add(c); },
    },
    addEventListener(){}, removeEventListener(){},
    appendChild(c){ this.children.push(c); return c; },
    remove(){}, focus(){},
    querySelector(){ return mkEl(); },
    querySelectorAll(){ return []; },
    getContext(){ return ctx2d; },
    getBoundingClientRect(){ return { left:0, top:0, width:620, height:400 }; },
  };
  Object.defineProperty(el, 'innerHTML', { get(){return el._html;}, set(v){el._html=v;} });
  return el;
}
```

canvas 的 `getContext()` 用 Proxy 做万能空实现，省得一个个补方法名：

```js
const ctx2d = new Proxy({}, {
  get(t, p){ return p in t ? t[p] : () => {}; },
  set(t, p, v){ t[p] = v; return true; },
});
```

⚠️ **记录式桩的读写字段必须一致**：若要断言"画出来的形状"，桩要记录 `fillRect` 的参数与当前 `fillStyle`。**写走 `fillStyle`、读却读私有 `_fs`，会静默记成 `undefined`** —— 断言于是空集恒真（见 1.5）。

## 1.3 沙箱：**把引擎循环停掉**，换取测试可控性

```js
const store = Object.create(null);    // 存档测试要读回真实写入的字节，所以在沙箱外留个引用

const sandbox = {
  console, document: { querySelector: () => mkEl(), querySelectorAll: () => [], createElement: t => mkEl(t) },
  performance,
  requestAnimationFrame: () => 0,      // 不回调 → 游戏循环不跑，手动驱动
  cancelAnimationFrame: () => {},
  setTimeout: () => 0,                 // 不执行 → 动画/延迟逻辑不干扰断言，且进程不挂住
  localStorage: {                      // 页面若做持久化，缺这个桩会直接抛异常
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  },
  window: { addEventListener(){}, removeEventListener(){} },
  Math, JSON, Date, Array, Object, Number, String, Set, Map, Proxy,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'prototype.js' });
```

**关键取舍**：`requestAnimationFrame` 与 `setTimeout` 设成 no-op 之后，循环由测试**手动推进**（直接调 `host.active.report(...)` 这类公开出口）。这比等真实帧稳定得多，且是**完全确定性**的。

## 1.4 断言（自带计数器，别引测试框架）

```js
let pass = 0, fail = 0;
function ok(cond, label, extra) {
  if (cond) { pass++; console.log('  OK   ' + label); }
  else { fail++; console.log('  FAIL ' + label + (extra!==undefined ? '  → 实际 '+JSON.stringify(extra) : '')); }
}
process.exit(fail ? 1 : 0);
```

**每段断言前先 `resetAll()`**，否则前一段的污染会让后面全是假阳性。

必测的七类断言：

| 类别 | 例子 |
|---|---|
| **流程走通** | 一次完整调用后，临时对象被回收 / 状态被置空 |
| **数值边界** | 上限是否真的封顶；截断量是否符合预期 |
| **幂等与兜底** | 重复调用、中途中断、异常路径是否安全 |
| **契约不含违规字段** | **运行时拦截**真实上报的载荷，检查键名（**不要用正则扫源码**） |
| **曲线单调性 + 值域可行性** | 难度参数随档位单调变化，**且最坏端点仍在能力射程内** |
| **耦合边界** | 上层代码里不该出现具体实现的名字 |
| **跨实现对账** | 同一批对局在两个实现上逐局同分 |

## 1.5 ⚠️ 假断言的三种形态（写断言前必读）

比 bug 更危险的是**通过了的假断言**。**通用判据一句话**：

> **「如果被测的东西完全坏掉／或者压根没接线，这条断言会不会照样过？」**
> 会过 ⟹ 它不是断言，是**装饰**。

| 坑 | 形态 | 修法 |
|---|---|---|
| **空集恒真** | `list.filter(...).every(...)` 在 `list` 为空时恒真；录制桩漏字段 → 测试安静失效 | 同时断言"**确实录到了**"（`list.length > 0`） |
| **恒真统计量** | 比较键里混进了不该有的字段 ⟹ 判据恒成立 ⟹ 报出 100% | 进断言前先问「它**可能**不成立吗」，能构造一个让它是 0 的样本吗 |
| **没接线的仪表** | 断言"计数器不增长"，但从未验证它会增长 ⟹ 没接上也绿 | **先验仪表，再信读数**：先跑一次已知会触发它的路径，确认它会动 |
| **对照组选错** | 在"关卡全部来自缓存"的档位测"装载时会搜索" ⟹ 恒为 0 | 断言要选**该性质真的会发生**的样本 |

配套一条同样重要的：**统计量、比例、均值不进断言**（它们随样本池变化）；进断言的是**整数**和**由设计意图推出的不等式**。

⚠️ **正则类断言只适合扫"某个字符串是否出现"，不要用它验证语段内部结构。** 下面是反面教材：

```js
// 坏：HTML 里结构体定义常被 span 标签切开，这个正则在真实文件上根本匹配不到，永远返回 true
'ModuleResult 不含货币字段': !/ModuleResult\s*\{[^}]*\b(dt|coin)\b/i.test(html),
```

正确做法是**包一层导出函数，截获真实载荷**：

```js
let captured = null;
const orig = rewardSink.settle;
rewardSink.settle = function (pid, mid, r) {
  captured = JSON.parse(JSON.stringify(r));
  return orig.call(this, pid, mid, r);
};
host.startRound('moduleX');
host.active.report({ /* ... */ });
rewardSink.settle = orig;

ok(!Object.keys(captured).some(k => /coin|^dt$|reward|grant|price/i.test(k)),
   '真实上报载荷不含货币语义字段', Object.keys(captured));
```

前提是被包装的方法挂在**对象属性**上（不是闭包里的裸函数）。这点在设计被测代码时就该留好。

## 1.6 结构自检（廉价的那部分，留在 SKILL.md）

```js
const smells = {
  '注册表条目数正确': (html.match(/implemented:/g) || []).length === 5,
  '无调试残留': !/console\.log\(|debugger|push\(null\)/.test(html),
  '宿上层零实现名硬编码': !/e\.key\s*===\s*'/.test(html),
  '走统一接口而非分支': /e\.Cls\.target\(tier\)/.test(html),
};
```

**别把"聚合数字"硬编码进断言。** 中位数、占比这类统计量会随策略微调而变，写死只会变成下次的假证据。真正值得硬编码的是**确定性黄金值**：无随机、无启发式的策略跑固定序列得到的逐步结果。判断标准 —— **这条期望值在"有意改动"时应该变吗？** 应该变 → 别硬编码，现场对账；不该变 → 硬编码，它就是回归护栏。

**断言数量会随踩坑单调增长，这不是质量指标。** 同一个原型从 81 条涨到 117 条，多出来的 36 条对应的全是具体翻车。数字本身不代表更可靠，**每条断言背后的那次事故才代表**。把"断言数"当 KPI 会写出大量同义反复的断言，反而稀释了真信号的可见度。

**每修掉一个非平凡 bug，就立刻为它写一条断言。** 断言是唯一能跨语言、跨时间守住"这个坑我踩过"的东西 —— 记忆和注释都会失效，而断言会在下次改坏时立刻报错。

## 1.7 运行（Windows 本机）

```bash
cd "<项目绝对路径>" && node _smoke.js
```

若 Bash 工具报 `dirname: command not found` / `ls: command not found`，说明启动时 PATH 被 shim 破坏，需先显式修复再执行（按本机实际版本号调整）：

```bash
export PATH="/usr/bin:/bin:$HOME/.workbuddy/binaries/node/versions/<版本>:$PATH"
```

零依赖，`node` 自带 `vm`。命名建议 `_smoke.js`，放在页面同目录，跟着原型一起交付。

---

# 阶段 ②：真渲染布局（无头 Chrome）

## 2.0 先别猜，先定位根因

**"整体偏移 / 边缘被切"几乎都是同一个根因**：元素实际宽度 > 视口宽度，而父容器是居中布局（`display:flex; align-items:center` 或 `margin:auto`），于是溢出部分**向两侧均分滑出屏幕** —— 左侧那半看不见，右侧那半也看不见，看起来就像"整块往左偏了"。

排查顺序：

1. 找**固定像素宽度**：`width: 400px`、`width: 80px` 这类。注意 `box-sizing` 不是 border-box 时，`width + padding + border` 才是真实占宽（`width:400px; padding:10px` ⇒ 实际 422px）。
2. 找**固定尺寸的横向排布**：`n × 单块宽 + (n-1) × gap` 是否超过视口。
3. 先上全局 `*, *::before, *::after { box-sizing: border-box }` —— 改动最小、收益最大。

## 2.1 ⚠️ 视口必须用 iframe 指定，`--window-size` 靠不住

Windows 下 Chrome 无头窗口有**约 512px 的最小宽度**。`--window-size=390,844` 会被钳到 512，量出来的 `innerWidth` 是 512 而不是 390 —— **三个手机尺寸会得到完全相同的结果，看起来"测了"其实没测**。

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
- ⚠️ **`--dump-dom` 首行紧跟 `<pre>` 标签**，用 `^\s*KEY=(.*)$` 多行正则抓值时**首行会漏掉**。这种"静默缺失"会掩盖真实失败 —— 抓取函数里要对每个键断言 `!== '(missing)'`。

## 2.2 ⚠️ `--headless=old` 已经没了，别用

新版 Chrome 移除了老无头模式。传 `--headless=old` 不会报错，而是**直接拉起 GUI Chrome 并挂住**，命令一直不返回直到被超时杀掉。看到进程里出现 chrome.exe 记得 `taskkill //IM chrome.exe //F`。

## 2.3 ⚠️ 想控制页面内部状态，必须注入脚本，不能从父窗口赋值

被测页面里 `let plates = [...]` 这种顶层声明是**全局词法绑定**，不是 `window` 的属性。从父窗口写 `iframeWin.plates = [...]` 只会新建一个 window 属性，页面函数读到的仍是原值 —— **你以为在测最坏情况，其实测的是随机情况**。这种"测量本身是假的"最难发现。

正确做法：往 iframe 里 `appendChild` 一个 `<script>`，它和页面脚本同处一个 realm：

```js
var s = doc.createElement('script');
s.textContent = 'plates=[6,6,6,6,6]; renderBoard(); window.__len = plates.length;';
doc.body.appendChild(s);
```

**并且一定要在脚本内读回关键量（`__len`）自证生效**，把它打进度量结果里。`盘数=5(脚本内读回 5)` 才有说服力；只写 `盘数=5` 可能是随机的。

## 2.4 量什么（不要只量 body 直接子块）

`width:100%` 的容器永远不出界，**里面的子元素出界它也不会露马脚**。要量到元素本体：

| 指标 | 判据 |
|---|---|
| `doc.documentElement.scrollWidth > innerWidth` | 有横向滚动 ⇒ 出问题 |
| 每个关键元素的 `getBoundingClientRect()` | `left < 0` 或 `right > innerWidth` ⇒ 出界 |
| 子元素 `offsetTop` 去重后的个数 | 判断是否意外换行 / 内容挤成细长条 |
| 容器 `scrollWidth > clientWidth` | 容器内部溢出 |

## 2.5 emoji / 图标的宽度陷阱

图标字号不等于占宽：**emoji 的实际占宽约为字号的 1.17 倍**。`62px` 宽的容器配 `font-size:15px`，按字号算"能放 2 个"，实际只放得下 1 个，容器里 6 个图标会被排成 6 行、整体拉成细长条。

**判断依据只能是实测的 `offsetTop` 行数**，不能靠字号估算。

## 2.6 与改动前对照（最关键的一步）

```bash
git show HEAD:index.html > before-raw.html     # 沙箱内 node 起不了子进程，git 放 bash 侧
```

同一套 harness 跑 before / after，**用同一套指标**。报告格式用"改前 → 改后"成对呈现，比单说"改好了"可信得多。别忘了**加一档桌面宽度（1440px）做回归对照** —— `clamp()` 的上限要刻意取回原值，才能保证桌面端版式不动。

---

# 阶段 ③：发布成分享链接

## 3.0 先做方案取舍（国内用户必看）

| 方案 | 适用 | 关键限制 |
|---|---|---|
| **WorkBuddy 云端发布** | 要发给国内的人玩 | 首选。独立域名、国内直连、可下线 |
| GitHub Pages | 面向海外/技术读者 | **国内访问不稳**，发给同学大概率打不开。别默认选它 |

判断依据是**"谁会打开这个链接"**，不是"哪个更省事"。发给中国同学/老师 ⇒ 云端发布。

## 3.1 ⚠️ 发布源目录 ≠ 项目根目录（最重要的一步）

**根目录几乎一定包含不该公开的东西**，而静态发布会把目录里**所有**文件变成可访问 URL：

- `.workbuddy/`（项目记忆、daily log、MEMORY.md —— 里面有本机路径、代理端口等）
- `.env*`、`.git/`、依赖清单、内部笔记、验证脚本

**做法**：新建一个专用发布目录，里面**只放要发布的那一个文件**。

```bash
mkdir -p site && cp index.html site/index.html
```

好处不只是安全：`site/` 也成了明确的发布契约（谁看都知道线上跑的是哪个文件）。

## 3.2 副本会漂移 ⇒ 把「一致性」变成测试断言

发布源是副本，就有"改了根文件忘了同步、线上跑旧版"的风险。别靠记性，**靠断言**：

```js
import { readFileSync, existsSync } from 'node:fs';
const siteIndexPath = new URL('./site/index.html', import.meta.url);
if (existsSync(siteIndexPath)) {
  // 注意：不带 encoding 才拿到 Buffer，用 equals 比字节，避免 BOM/换行归一化误判
  if (!readFileSync(htmlPath).equals(readFileSync(siteIndexPath))) {
    fail('发布副本已过期：site/index.html 与 index.html 不一致 → cp index.html site/index.html');
  }
}
```

**必须做负向测试**：往副本追加几个字节，确认断言真的会让退出码变成 1。没验证过"能失败"的断言只是装饰。

## 3.3 发布

调 `workbuddy_sites_deploy`：`directory` 指向 `site/`，`language: "static"`，`appName` 用中文短名（≤12 字），`domainPrefix` 用同名英文 slug。**用户上一句没说要发布就先问**（发布 = 覆盖线上现有内容）。

## 3.4 上线后核验（看到"发布成功"不算完）

两件事必须实际请求一遍，不能只看返回 JSON：

```bash
B="https://<你的域名>"
curl -s -o /tmp/h.html -w "HTTP %{http_code} | %{size_download} bytes | %{time_total}s\n" --max-time 25 "$B/"
grep -o '<title>[^<]*</title>' /tmp/h.html          # 标题对不对
```

**① 内容真的是刚发布的那份**：字节数应与本地副本文件大小一致，`<title>` 正确。

**② 泄漏专项检查（逐步都要期望 4xx）**：

```bash
for p in "/.workbuddy/memory/MEMORY.md" "/.env" "/verify-ai.mjs" "/README.md" "/.git/config"; do
  printf "  %-34s -> %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$B$p")"
done
```

看到 200 就是真泄漏，立刻停下来处理（说明发布源选错了目录）。

## 3.5 收尾

- README 补「在线试玩」小节 + 项目结构树里加发布目录，并**说明为何不发根目录**
- `.gitignore` 加 `*.genie` / `.wbapp_*`（发布会写一个工具内部标记文件到项目根）
- 改完源码 → `cp index.html site/index.html` → 跑验证器 → 提交推送
- 阶段 ① 的验证器要跟着源码改动复跑一次，确认样式/布局调整没连带弄坏功能
- 临时 harness 全部放系统临时目录，别在项目里留探针文件；保留最终截图即可

发布后的运营（更新 / 下线 / 删除的区别）、本机留痕排查、`git push` 超时的处理：见 `references/publish-ops.md`
