# aihaisi-workbuddy-skills

个人 AI 技能库 —— WorkBuddy / CodeBuddy 的 AgentSkills（SKILL.md）合集。每个技能是一个自包含目录：一份 `SKILL.md`（触发条件 + 方法论 + 排障），可选 `scripts/`（可直接执行的管线）和 `references/`（深水区文档）。

## 亮点技能

| 技能 | 说明 |
|---|---|
| [`douyin-media-download`](douyin-media-download/) | 抖音视频/图文/实况图下载管线：Chrome headless 渲染 → 特征抽签名直链 → 即取即下 → ffprobe 断言 → palettegen 转 GIF。附一键脚本 `dy_fetch.sh`，产物按 `video/<作品ID>.mp4` + `gif/<作品ID>.gif` 归档 |
| [`latex-cn-typesetting`](latex-cn-typesetting/) | 用 XeLaTeX 做中文排版成品：简历 CV（单页压缩、照片、二维码、长链接按模块尺寸反推宽度）+ Beamer 双语幻灯片（帧标题色带几何与负 `\vspace` 铁律、`shrink` 非直觉语义、纵向溢出处理顺序）。两者共用的编译两遍、Overfull 处理与 pdftoppm/pdftotext 版面量化审计写在统一章节（`scripts/layout_audit.py` / `scripts/band_geometry.py`） |
| [`html-prototype-verify-ship`](html-prototype-verify-ship/) | 单文件 HTML 原型的验证与发布三段式：① DOM 桩 + node vm 逻辑冒烟 ② 无头 Chrome + iframe 精确视口查横向出界 ③ 发布成「点开即玩」的分享链接（发布源目录隔离 + 一致性断言 + 上线后泄漏专检）。深挖内容在 `references/` |
| [`gameplay-design-verification`](gameplay-design-verification/) | 玩法设计的可计算验证：设计期用四层策略（随机/贪心/规划/全知）测规划增益、技能表达与 UX 体检，十条判据判「有没有决策空间」；实现期用暴力博弈树 DP 逐状态验证 AI 最优性并做自对弈对账。含统一的断言纪律与变异测试 |
| [`self-improving-agent`](self-improving-agent/) / [`self-improving`](self-improving/) | Agent 自进化：错误捕获 → 学习沉淀 → 技能迭代 |
| [`proactive-agent`](proactive-agent/) | 从被动执行到主动预判的 Agent 行为模式 |
| [`skill-creator`](skill-creator/) | 技能本身的创建 / 校验 / 打包工具链 |
| `*-qcc` 系列 | 企查查数据驱动的投研尽调技能集（工商、股权、失信、供应链等） |

## 技能设计原则

- **特征定位，不写死索引** —— 目标系统的数据位置会变，按内容特征找才可复现
- **断言进脚本，不靠人肉** —— 每个下载产物过 ffprobe，每条管线出口有校验
- **骨架固定，关节判别** —— 确定性流程写死，易变环节按现场特征分支
- **先验证，后动手** —— 影响面大的参数先在单点上试跑，外部素材先做健康度抽检；证伪成本要排在动作之前，不要推到下游返工
- **公开前扫密钥** —— 模式匹配全库扫描 token/key 后才推送

## 外部来源技能（只登记，不纳入本仓库）

以下技能来自第三方仓库，本仓库不转发其代码，仅登记来源与当时的版本，便于重装与追溯。它们被 `.gitignore` 排除，克隆本仓库后需单独安装。

| 技能 | 上游 | 登记版本 | 说明 |
|---|---|---|---|
| `ginger_wechat_portrait` | [Jiang59991/ginger_wechat_portrait](https://github.com/Jiang59991/ginger_wechat_portrait) | `ad24938` | 微信聊天记录分析（Claude Code Skill）。上游无 LICENSE 文件，不作再分发；且要求 macOS + Mac 微信客户端 |

```bash
# 重装示例（装到自己的 Agent 技能目录下）
git clone https://github.com/Jiang59991/ginger_wechat_portrait.git <你的技能目录>/ginger_wechat_portrait
```

**为什么不直接 git submodule？** 本仓库的定位是「克隆后即可直接复制技能目录使用」的纯内容库，submodule 会让克隆多一步 `--recursive`，且上游一旦删库就会留下悬空引用。第三方技能的正确备份位置是上游自己的仓库。

## 使用方式

技能是纯 Markdown + 脚本，拷贝单个目录到你的 Agent 技能目录即可生效（兼容 Claude Code / WorkBuddy / OpenClaw 等读 SKILL.md 的运行时）。

```bash
git clone https://github.com/aihaisi/aihaisi-workbuddy-skills.git
cp -r douyin-media-download <你的技能目录>/
```

---
_个人使用配置，随用随更。第三方技能版权归原作者。_
