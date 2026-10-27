---
name: find-skills
slug: find-skills
displayName: 技能发现·Find Skills
description: 不知道装什么技能？想让 AI 自己找到最合适的技能？技能发现·Find Skills 是场景驱动+关键词双模式的技能发现工具（skill discovery / skill finder / install skills）：用自然语言描述场景/需求（如"我想做一个海报""帮我分析股票""找个薅羊毛技能"），或明确说"安装技能/find skills/找个skill/有没有做XX的技能"时，自动从官方内置、本地已安装、SkillHub、虾评、GitHub、ClawHub 六层联合搜索并推荐最合适的技能，支持一键安装。已完全替代官方原 find-skills 插件。触发词：找技能、安装技能、技能推荐、技能发现、find skills、skill discovery、install skill。
version: "1.7.0"
---
# find-skills（场景技能匹配器）

## Overview

本技能用于**场景驱动的技能发现引擎**——用户用自然语言描述需求，系统自动理解意图，联合搜索并推荐最合适的技能。

**与官方原 `find-skills` 插件的关系**：
- 官方原 `find-skills` 插件的 description 已被标记为 DEPRECATED，不会主动触发
- 本技能已完全覆盖其所有能力，并新增了官方内置扫描 + 本地已安装扫描 + 场景语义理解 + 推荐理由输出

---

## 核心流程

### Step 1：理解用户场景

从用户的自然语言描述中提取：
1. **任务意图**：用户想做什么？
2. **领域标签**：属于哪个领域？
3. **搜索关键词**：中英文都要（用于远程搜索）

**示例**：
- "我想做一个海报" → 意图：设计/制图；领域：内容创作；关键词：poster, design, 海报, 设计
- "帮我分析今天的大盘" → 意图：股票分析；领域：金融；关键词：stock, A股, 大盘, 分析

---

### Step 2：三层联合搜索

#### 2.1 第一层：官方内置技能（WorkBuddy 自带，无需安装）

扫描官方内置技能目录，读取每个技能的 `name` 和 `description`：

```bash
ls /Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/
```

用 `Read` 工具读取每个技能的 `SKILL.md` YAML frontmatter，与用户场景做**语义匹配**。

**匹配规则**（按优先级）：
1. 用户场景关键词直接出现在技能 description 中 → 高分
2. 技能 name 与用户意图高度相关 → 高分
3. 技能 description 与用户领域相关 → 中分

---

#### 2.2 第二层：本地已安装技能

扫描以下两个位置的已安装技能：

```bash
# 用户级技能
ls ~/.workbuddy/skills/

# 项目级技能（当前工作区）
ls .workbuddy/skills/ 2>/dev/null || echo "无项目级技能"
```

用 `Read` 工具读取每个技能的 `SKILL.md` YAML frontmatter，提取 `name` 和 `description`，与用户场景做**语义匹配**。

> **注意**：如果本地已安装技能在 Step 2.1 官方内置中也出现，去重，只保留最高优先级的记录。

---

#### 2.3 第三层：远程技能市场（完全替代 `find-skills` 的搜索能力）

**先检查本地 marketplace 缓存**（原 `find-skills` Step 5 逻辑）：

```bash
ls ~/.workbuddy/skills-marketplace/skills 2>/dev/null
```

如果缓存目录中存在与用户需求匹配的技能，直接复制安装，无需远程下载：

```bash
cp -r ~/.workbuddy/skills-marketplace/skills/<skill-folder-name> ~/.workbuddy/skills/<skill-folder-name>
```

---

**远程搜索**（原 `find-skills` Step 2/2b 逻辑）：

如果本地缓存无结果，则按以下顺序搜索远程技能市场：

---

**① SkillHub 官方市场**（主要来源，优先搜索）：
```bash
curl -s "https://lightmake.site/api/v1/search?q=<URL-encoded 中文关键词>&limit=10"
curl -s "https://lightmake.site/api/v1/search?q=<URL-encoded English keywords>&limit=10"
```

过滤 `score < 0.05` 的低相关结果。

---

**② 虾评技能市场**（中文技能重点来源）：

虾评 API Base URL：`https://xiaping.coze.com`（注意：不是 `coze.site`）

**搜索技能**：
```bash
# 搜索技能（按关键词）
curl -s "https://xiaping.coze.com/api/skills/search?q=<URL-encoded 关键词>&limit=10"

# 获取技能详情
curl -s "https://xiaping.coze.com/api/skills/<skill-id>"

# 获取技能下载链接
curl -s "https://xiaping.coze.com/api/skills/<skill-id>/download"
```

**需要先加载 `虾评指南` 技能**（路径：`~/.workbuddy/skills/虾评指南/SKILL.md`），按其中 §1.1 + §1.2 的规范执行搜索和下载。

> **重要**：虾评是中文技能的核心来源，对于中文场景的技能搜索，虾评的结果往往比 SkillHub 更相关。

---
**③ GitHub 技能仓库**（开源技能来源）：

搜索 GitHub 上包含 WorkBuddy / Claw 技能的文件。

> **认证说明**：GitHub 搜索 API 需要认证。如果环境变量 `GITHUB_TOKEN` 已设置，自动带上认证（5000次/小时）；否则使用匿名访问（60次/小时，可能不够用）。

```bash
# 如果有 GitHub Token，带上认证
if [ -n "$GITHUB_TOKEN" ]; then
  AUTH_HEADER="-H \"Authorization: Bearer $GITHUB_TOKEN\""
else
  AUTH_HEADER=""
fi

# 搜索包含 SKILL.md 的代码
curl -s $AUTH_HEADER "https://api.github.com/search/code?q=filename:SKILL.md+<关键词>&per_page=10"

# 搜索技能相关仓库
curl -s $AUTH_HEADER "https://api.github.com/search/repositories?q=<URL-encoded 关键词>+skill+in:name,description&per_page=10"
```

> **注意**：GitHub Code Search API 的 `filename:SKILL.md` 搜索需要认证才能使用。如果没有 `GITHUB_TOKEN`，退化为只搜索 repositories（仓库搜索匿名可用）。

**安装方式**：
```bash
# 从 GitHub 克隆技能仓库
git clone "https://github.com/<user>/<repo>.git" <target-skills-dir>/<skill-name>/

# 验证安装
ls <target-skills-dir>/<skill-name>/SKILL.md
```

> **注意**：GitHub 搜索结果需要人工判断是否为有效技能（检查是否包含 `SKILL.md`），因为是代码搜索，可能返回非技能文件。

---
