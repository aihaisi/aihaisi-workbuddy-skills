# aihaisi-workbuddy-skills

个人 AI 技能库 —— WorkBuddy / CodeBuddy 的 AgentSkills（SKILL.md）合集。每个技能是一个自包含目录：一份 `SKILL.md`（触发条件 + 方法论 + 排障），可选 `scripts/`（可直接执行的管线）和 `references/`（深水区文档）。

## 亮点技能

| 技能 | 说明 |
|---|---|
| [`douyin-media-download`](douyin-media-download/) | 抖音视频/图文/实况图下载管线：Chrome headless 渲染 → 特征抽签名直链 → 即取即下 → ffprobe 断言 → palettegen 转 GIF。附一键脚本 `dy_fetch.sh`，产物按 `video/<作品ID>.mp4` + `gif/<作品ID>.gif` 归档 |
| [`self-improving-agent`](self-improving-agent/) / [`self-improving`](self-improving/) | Agent 自进化：错误捕获 → 学习沉淀 → 技能迭代 |
| [`proactive-agent`](proactive-agent/) | 从被动执行到主动预判的 Agent 行为模式 |
| [`skill-creator`](skill-creator/) | 技能本身的创建 / 校验 / 打包工具链 |
| `*-qcc` 系列 | 企查查数据驱动的投研尽调技能集（工商、股权、失信、供应链等） |

## 技能设计原则

- **特征定位，不写死索引** —— 目标系统的数据位置会变，按内容特征找才可复现
- **断言进脚本，不靠人肉** —— 每个下载产物过 ffprobe，每条管线出口有校验
- **骨架固定，关节判别** —— 确定性流程写死，易变环节按现场特征分支
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
