---
name: html-prototype-smoke-test
description: 对单文件 HTML 应用（游戏原型、交互 Demo、仪表盘）做无头冒烟测试——用 DOM 桩 + node vm 直接加载页面里的脚本，断言协议流程、经济数值、状态机。当需要"验证我刚写的 HTML 原型真的能跑"或"证明某个数值 claim 成立"时使用。不依赖任何浏览器或 npm 依赖。
agent_created: true
---

# 单文件 HTML 应用的无头冒烟测试

## 何时用

- 写完了单文件 HTML 原型（无构建、无 npm），想验证逻辑而不装浏览器
- 需要断言具体数值 claim（"这条上限会生效"、"这个状态机会正确收敛"）
- 交付前想一次性排掉"语法过了但逻辑错"的问题

**不适用**：需要真实渲染 / 布局 / 像素判断的场景（那要真浏览器）。

## 核心思路

页面脚本通常把逻辑和 DOM 混在一个 `<script>` 里。用 **DOM 桩 + `vm`** 把它整体加载进 Node，
再把内部对象"导出"出来断言。**不重写逻辑、不复制代码**——测的就是即将交付的那份文件，避免测试与实现漂移。

## 步骤

### 1. 从 HTML 抽出脚本并导出内部对象

```js
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const src = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  + '\nglobalThis.__api = { host, S, CFG, resetAll };\n';
```

顶层 `const` / `class` 在 `vm` 里是脚本的词法作用域，**不会自动挂到 context 上**，
所以必须靠末尾追加的一行显式导出。按需要什么就导什么。

### 2. DOM 桩（够用就好，约 40 行）

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

**canvas 的 `getContext()` 用 Proxy 做万能空实现**，省得一个个补方法名：

```js
const ctx2d = new Proxy({}, {
  get(t, p){ return p in t ? t[p] : () => {}; },
  set(t, p, v){ t[p] = v; return true; },
});
```

### 3. 沙箱：**把引擎循环停掉**，换取测试可控性

```js
const store = Object.create(null);    // 存档测试要读回真实写入的字节，所以在沙箱外留个引用

const sandbox = {
  console, document: { querySelector: () => mkEl(), querySelectorAll: () => [], createElement: t => mkEl(t) },
  performance,
  requestAnimationFrame: () => 0,      // 不回调 → 游戏循环不跑，手动驱动
  cancelAnimationFrame: () => {},
  setTimeout: () => 0,                  // 不执行 → 动画/延迟逻辑不干扰断言，且进程不挂住
  localStorage: {                       // 页面若做持久化，缺这个桩会直接抛异常
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  },
  window: { addEventListener(){}, removeEventListener(){} },  // 页面若往 window 挂全局监听
  Math, JSON, Date, Array, Object, Number, String, Set, Map, Proxy,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'prototype.js' });
const { host, S, resetAll } = sandbox.__api;
```

**关键取舍**：`requestAnimationFrame` 设成 no-op、`setTimeout` 设成 no-op 之后，
循环由测试手动推进（直接调用 `host.active.report(...)` 这类公开出口）。这比等真实帧稳定得多。

### 4. 断言（自带计数器，别引测试框架）

```js
let pass = 0, fail = 0;
function ok(cond, label, extra) {
  if (cond) { pass++; console.log('  OK   ' + label); }
  else { fail++; console.log('  FAIL ' + label + (extra!==undefined ? '  → 实际 '+JSON.stringify(extra) : '')); }
}
process.exit(fail ? 1 : 0);
```

**每段断言前先 `resetAll()`**，否则前一段的污染会让后面全是假阳性。

## 必测的七类断言

| 类别 | 例子 |
|---|---|
| **流程走通** | 一次完整调用后，临时对象被回收 / 状态被置空 |
| **数值边界** | 上限是否真的封顶；截断量是否符合预期 |
| **幂等与兜底** | 重复调用、中途中断、异常路径是否安全 |
| **契约不含违规字段** | **运行时拦截**真实上报的载荷，检查键名（见下节，别用正则） |
| **曲线单调性** | 难度/数值参数是否随档位单调变化；防止后人改数值把曲线改平 |
| **耦合边界** | 上层代码里不该出现具体实现的名字（见下节） |
| **跨实现对账** | 同一批对局在两个实现上逐局同分（见 ⑦） |
| **结构自检** | 正则扫源码，拦掉 `push(null)` 之类的残留和调试尾巴 |

## 三件只有真跑才能验的事（本次实战补充）

### ① 契约字段：用运行时拦截，别用正则扫源码

**正则扫源码是弱断言，甚至常常是假阳性。** 下面是反面教材：

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

### ② 派生通道的准入校验：新通道 = 新后门

给协议加一条新通道（比如让子模块上报"自定义记录"）时，必须同时把**准入校验**写出来并测掉：

```js
host.active.report({ records: { bestStreak: 42, dt: 9999, coin: 5000 } });
ok(S.records.x.dt === undefined, '未声明的键被整键拒收（无法借新通道写货币）');
```

四类校验缺一不可：**键在白名单内 · 值是有限数值 · 在 [min,max] 区间 · 只增不减**（防用低值覆盖高值绕开）。

**判据：任何"从底层通往上层状态"的新路径，都必须有一条反向断言证明它写不进去。**

### ③ 持久化边界：漏存一个字段 = 一个漏洞

测持久化不是"存进去能读回来"，而是**模拟刷新，验证每个配额字段都没被重置**：

```js
const snap = { dtToday: S.dtToday, perfToday: S.perfToday, fp: JSON.stringify(S.firstPlayToday) };
S.dtToday = 0; S.perfToday = 0; S.firstPlayToday = {};   // 模拟刷新：内存清空，存储保留
loadHost();
ok(S.dtToday === snap.dtToday, '刷新后当日配额不归零（否则可无限刷）');
```

**存档清单的标准不是"哪些状态重要"，而是"哪些字段漏存会变成漏洞"。** 凡是限流用的计数器（当日配额、已领标记、兑换次数），漏存任何一个都是刷取路径。

### ④ 耦合边界：上层不该认识下层实现

模块化项目里，最容易被忽略的破窗是上层代码里的 `if (key === 'moduleX')` 分支。写成断言：

```js
'上层零实现名硬编码': !/e\.key\s*===\s*'/.test(html),
'走统一接口': /e\.Cls\.target\(tier\)/.test(html),
```

**只有接入一个"结构和前两个都不同"的新模块，才能真正验证可扩展性。** 前两个模块太像时，"零改动"可能只是没被检验过。

### ⑤ 单调性 ≠ 可行性：值域类断言

**只验"趋势对不对"是不够的，还要验"最坏情况能不能满足"。** 真实翻车案例：

```js
// 难度曲线单调递增 ✓ 三条断言全绿
tiers = [{w:110, gap:[70,130]}, {w:84, gap:[90,158]}, {w:64, gap:[110,186]}];
MAX_DIST = 210;   // ← 满力射程

// 但最坏情况下需求距离 = 最宽平台的一半 + 最大间距
// t3: 1.1×64/2 + 186 = 221.2 > 210  ← 存在物理上不可能通过的关卡
```

单调性断言只保证了"越来越难"，**没保证"难还能过"**。补一条值域可行性断言：

```js
const worst = tiers.map(t => 1.1 * t.w / 2 + t.gap[1]);
ok(worst.every(d => d <= MAX_DIST), '⛔ 最坏间距仍在能力射程内', worst);
```

配套判据：凡是"配置区间 + 能力上限"这类结构（射程/冷却/预算/容量 vs 需求），
都要用**最坏端点**验一次可行性，而不是只验中位数或趋势。

### ⑥ 反馈通道：区分"输入读数"与"输出答案"

玩法类原型要额外拦一类**设计级错误**——不是代码 bug，是设计决策本身把玩法废掉了。判据一句话：

> 这条信息说的是「**你刚才做了什么**」，还是「**你将会得到什么**」？

前者是反馈，帮助玩家建立心智模型；后者是答案，直接替代思考。典型反例：跳跃类游戏画出落点预测线，
玩家不需要建立"这段距离要按多久"的映射，只需看线对准松手 —— 技能停止生长，所有难度维度退化成反应速度。

源码级断言（这类错误一旦引入，后续怎么调数值都救不回来）：

```js
'无落点预测线绘制': !/setLineDash\s*\(/.test(html),
'档位不改物理常数': !/gap:\s*\[[^\]]+\],\s*window:/.test(html),   // 档位配置里不得出现物理参数
```

**档位只能改「目标」（评分标准、容错窗口），不能改「工具」（物理常数）。**
改了物理常数，玩家练熟的肌肉记忆升档即作废 —— 那不是"变难"，是换了个游戏。

### ⑦ 跨实现对账：把「同量级」升级成「逐局同分」

**当同一个玩法有两个实现**（如 JS 原型 + Python 模拟，或客户端 + 服务端），"两边数量级吻合"是一个
几乎无用的断言 —— 差 10%、差一倍都能叫"吻合"，而差异可能来自物理不一致、也可能只是采样噪声，
**分不清**。要做的是让两侧跑**同一批对局**：把随机源换成一个十几行的 LCG。

```js
// JS 侧复现 Python 的 x = (1103515245*x + 12345) & 0x7FFFFFFF
const lcgSeq = (seed, n) => {
  let x = seed >>> 0; const out = [];
  for (let i = 0; i < n; i++) {
    x = (Math.imul(1103515245, x) + 12345) & 0x7FFFFFFF;   // imul = 低 32 位，与 Python 全精度后取模等价
    out.push(SHAPES[x % SHAPES.length]);
  }
  return out;
};
```

**别用 `random.Random` / `mt19937`**：梅森旋转没法在 JS 里低成本逐位复现。对账脚本里
"两边拿得到同一个数"比"随机性更漂亮"重要得多。序列长度、投放上限两侧必须**同步**，
否则会在上限处出现假失败。

对账分三层，从强到弱，缺一层就会误判：

| 层 | 策略 | 能证明什么 |
|---|---|---|
| **A 物理** | 确定性「最左合法列」，× 所有朝向 | 坐标约定、下落起点、出生判定、消行补行位置一致 |
| **B 评估** | 同一序列跑贪心（带评估函数） | 评估口径、tie-break 方向、候选集过滤一致 |
| **C 分布** | 同一批 N 局 × 上限块数 | 端到端一致（含消行累积效应） |

**只做 C 会漏掉 A/B**：总分相同也可能是"错的地方互相抵消"。逐步 trace 比总分更早报警。
trace 里除了位置还要打**朝向序号**（`name@col#orient`）—— 同一列配不同朝向是两个局面，
不打朝向就没法归因。

**对账抓出来的四个坑，没有一个能靠"看代码"或"跑单局"发现：**

| # | 症状 | 根因 |
|---|---|---|
| ① | 首步读到 `J@0`，另一侧是 `I@0`，像物理不一致 | **注入确定性序列时没重置模块内部的游标**（`pieceIdx`）。初始化里已经生成过一块，只换序列＝整条错一位，对账出的"差异"全是假的 |
| ② | 24 个候选的评分表里只有 **1 格**不同 | **评估器漏算消行**：分数要在消行**后**的棋盘上取最高列。差一格就足以让贪心选错，60 块后总分拉开一倍 |
| ③ | 中心堆满、两侧空着也判负 | **出生判定只查中心列**：宽 4 的块要占 4 列，等于把死亡判定放大 4 倍。玩家读到的是"游戏乱判"。败因必须由棋盘状态决定 |
| ④ | `ReferenceError: Cannot access 'X' before initialization` | 常量声明在调用点之后（TDZ）。测试文件是**顺序执行**的，公共 helper 必须定义在第一次使用之前 |

**方法论（这条比上面任何一条都重要）**：

> **分数差一倍时，第一反应必须是"先证明我们在玩同一个游戏"，而不是怀疑机制。**
> 否则你会去改机制 —— 把正确的东西改坏。

配套做法：给评估器加一个 `DBG=1` 环境变量，打印**候选评分表 + 棋盘快照**。
两条实现各打一张，逐行 diff。只看"最终选了哪个"，永远分不清
"候选集不同"和"同一落法评分不同"。

## 数值校准：参数扫描取代拍脑袋

手感/难度/经济参数不要靠"感觉合适"来定，**先在脚本里跑参数扫描，用数据选**。真实流程：

1. 定义**玩家模型**（可调的能力参数，如操作误差 σ、决策速度）和**闭环模拟**（连玩 N 局，含难度调整逻辑）
2. 定义**目标函数**（如"调档次数最少 + 终态符合预期"或"高/低水平玩家的表现差距最大"）
3. 扫描候选参数网格，挑最优，并把**扫描过程写进注释**

```python
# 阈值扫描示例：8 组候选 × 5 类玩家 × 60 局闭环，按「总调档次数」排序
CAND = [(0.85,0.35,5), (0.90,0.55,5), (0.90,0.55,8), (0.92,0.55,5), ...]
for up, down, win in CAND:
    tot = sum(simulate(player, up, down, win) for player in PLAYERS)
```

扫描的最大价值是**暴露"参数之间不独立"**：以为只是调一个阈值，结果发现窗口大小能起同样的作用，
而两者的副作用完全不同（放大窗口是结构性稳健，抬高阈值只是提高门槛 → 玩家会觉得"打得好却不升级"）。

**同时要写出每个假设的自由参数**（如"玩家误差 σ"没有真人数据），
标明它只提供**校准框架与敏感度方向**，不是精确预测。

### 震荡类 bug 有两个独立成因

遇到"状态在两端反复横跳"的问题，别只修一个就收工：

| 成因 | 表现 | 修法 |
|---|---|---|
| **缺冷却** | 调整后立即重新累积，几局就再次触发 | 调整后清空评估窗口 |
| **滞回区间过窄** | 表现值**贴着阈值**的玩家随机波动触发调整 | 拉开双阈值间距，并加断言守住下限 |

第二个尤其隐蔽：它在平均值远离阈值时完全不出现，只有"能力恰好卡在阈值附近"的玩家才会暴露。
**扫描时要用覆盖各能力段的玩家模型，只测一个中等玩家会漏掉它。**


## 结构自检别漏

把"坏味道"也做成断言，一起拦在交付前：

```js
const smells = {
  '注册表条目数正确': (html.match(/implemented:/g) || []).length === 5,
  '无调试残留': !/console\.log\(|debugger|push\(null\)/.test(html),
  '宿上层零实现名硬编码': !/e\.key\s*===\s*'/.test(html),
  '走统一接口而非分支': /e\.Cls\.target\(tier\)/.test(html),
};
```

⚠️ **正则类断言只适合扫"某个字符串是否出现"，不要用它验证语段内部结构**（如 `Struct { field }` 里有哪些字段）——
标签、换行、注释都会让它静默失效成假阳性。碰到结构相关的判定，一律走运行时拦截。

## 实测收益

**这类测试最大的价值不是"证明能跑"，而是抓纸面推演看不出的 bug。** 两个真实例子：

1. **动态难度震荡**：只写了升降阈值、没写冷却，连续 3 局高分就跳满级、随即被压回，难度来回甩。
   语法检查和人工 review 都发现不了，跑一遍断言立刻暴露。
2. **难度曲线方向反了**：新模块照抄前两个模块的目标分公式（`base × (1 + 0.3 × (tier−1))`），
   但前两个模块的难度提升让**得分上升**，新模块的难度提升让**得分下降** —— 分子分母反向，
   档位一升玩家就再也不可能达标。**照抄品类惯例公式是这类错误的高发区**，写成单调性断言就能拦下。
3. **消行补空行补反了**：`board[0]` 是底行，消行后空行必须补在**数组末尾（顶部）**；
   补到底部等于每消一行把整座地形往上顶一格，堆高速度翻倍 → 100% 顶死、十几步即死、全体 0 分。
   表现是"游戏完全跑不起来"，但语法检查和 review 都看不出 —— 因为代码逻辑本身是自洽的。

**跨语言重写同一算法时，之前修过的 bug 会原样重现。** 上例 3 在 Python 模拟和 JS 原型里
各出现一次，两次表现完全相同。**做法：每修掉一个非平凡 bug，就立刻为它写一条断言。**
断言是唯一能跨语言、跨时间守住"这个坑我踩过"的东西 —— 记忆和注释都会失效，
而断言会在下次改坏时立刻报错。

**断言数量会随踩坑单调增长，这不是质量指标。** 同一个原型从 81 条涨到 117 条，
多出来的 36 条对应的全是具体翻车（身体列扫描、records 上限同步、朝向代数性质、
踢墙幅度、三层对账）。数字本身不代表更可靠，**每条断言背后的那次事故才代表**。
把"断言数"当 KPI 会写出大量同义反复的断言，反而稀释了真信号的可见度。

**别把"聚合数字"硬编码进断言。** 中位数、占比这类统计量会随策略微调而变，
写死只会变成下次的假证据（"测试过了"但其实是改坏了）。真正值得硬编码的是
**确定性黄金值**：无随机、无启发式的策略跑固定序列得到的逐步结果。
判断标准一句话 —— **这条期望值在"有意改动"时应该变吗？** 应该变 → 别硬编码，现场对账；
不该变 → 硬编码，它就是回归护栏。

## 运行（Windows 本机）

```bash
cd "<项目绝对路径>" && node _smoke.js
```

若 Bash 工具报 `dirname: command not found` / `ls: command not found`，说明启动时 PATH 被 shim 破坏，
需先显式修复再执行（按本机实际版本号调整）：

```bash
export PATH="/usr/bin:/bin:$HOME/.workbuddy/binaries/node/versions/<版本>:$PATH"
```

零依赖，`node` 自带 `vm`。命名建议 `_smoke.js`，放在页面同目录，跟着原型一起交付。
