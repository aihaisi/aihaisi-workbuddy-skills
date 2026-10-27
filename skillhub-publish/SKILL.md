---
name: skillhub-publish
description: 把本地 Skill 发布到 SkillHub（skillhub.cn）市场时使用。覆盖官方 CLI 的必填 frontmatter 三件套（slug/version/displayName）、发布前包内自查与密钥扫描、打包规则与上传限额、--dry-run 预检、skh_ 个人 API Token 的获取入口与实名认证前置、Windows 下 PYTHONIOENCODING 编码坑、401/403/409/429 错误码判读，以及最容易搞错的一条——CLI 只能发「社区普通 Skill」，付费 Pay Skill 必须在网页控制台发布。当用户说"发布 skill""上架技能""发到 skillhub""把技能推到市场""更新已上架的技能""发布失败/被拒了"时使用。
agent_created: true
---

# 发布 Skill 到 SkillHub

## 0. 最先要知道的一条：有两条通道，别混

| 通道 | 产物 | 认证 | 操作位置 |
|---|---|---|---|
| **CLI** `skillhub publish` | 社区**普通** Skill（免费，源文件可下载） | `skh_` 个人 Token | 终端 / Agent |
| **网页控制台** | **付费 Pay Skill**（按次计费、进付费专区） | 网页登录态 + 实名 + 开通收款 | `https://skillhub.cn/dashboard/publish` |

**判定依据（两条独立证据，别凭印象）**：
1. CLI 的 publish 上传 payload **只有** `slug/version/displayName/summary/description/tags/license/homepage/changelog` —— 没有任何付费字段（可直接 `grep -niE "paid|pay_|price" ~/.skillhub/skills_store_cli.py` 复核）。
2. 官方使用指南第 4 章写明付费路径是「点『发布 Skill』→ 选『发布付费 Skill』→ 上传基本信息」。

⇒ **想按次收费的服务，CLI 发不出来。** 先把包备好，再引导用户走网页向导。
⚠️ 反向风险：用 CLI 以目标 slug 发了社区版后，再想发付费版可能撞 `409 slug 已被占用`。**目标明确是付费时，不要"先发个社区版试试"。**

## 1. 三条硬前置（缺任何一条都发不出去）

1. **frontmatter 三件套**：`slug` + `version` + `displayName`。
   - `slug` 正则 `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$`，长度 2–128，**全网唯一** → **建议带 handle 前缀**避免 409。
   - `version` 必须是合法 SemVer（`1.0.0`）。
   - 官方示例还建议 `summary` / `license`，但**不阻断发布**。
   - ⚠️ **WorkBuddy 本地技能通常只有 `name` + `description`**，直接发必报 `Error: SKILL.md 缺少 slug` —— 这是最常见的第一道坎。
   - ⚠️ CLI 的 frontmatter 解析器**只支持单行 `key: value` 与 `key: [a, b]`**（无 PyYAML）。`description` 必须保持一行。
2. **实名认证**：未实名**不能创建 API Token，也不能发布** → 报 `403 请先完成实名认证`。
3. **Token**：`https://skillhub.cn/dashboard/keys` → 左下角「创建 API key」→ **完整 token 只显示这一次**（丢了删掉重建即可）。必须 `skh_` 开头；旧的 `sk_pat_` / `sh_pat_` 体系已下线。被弹回首页 = 未登录（手机号 + 验证码，首次自动注册）。

## 2. 本机环境

```bash
# Bash 工具 PATH 被 shim 破坏，每条命令前显式修（详见 workbuddy-skills-repo-sync §1）
export PATH="/usr/bin:/bin:/c/Windows/System32:$HOME/.workbuddy/binaries/python/versions/3.13.12:$HOME/.workbuddy/binaries/node/versions/22.22.2-3:$PATH"
export SKILLHUB_PY="$HOME/.workbuddy/binaries/python/versions/3.13.12/python.exe"   # 绕开微软商店 python3 桩
export PYTHONIOENCODING=utf-8
```

- CLI 本体：`~/.skillhub/skills_store_cli.py`；启动器 `~/.local/bin/skillhub`（bash）与 `skillhub.cmd`（Windows 必须走这个）。
- 本机启动器已改为**实测可用性**探测解释器（原厂写死 `python3` 会撞商店桩）。
- ⚠️ **Windows 必设 `PYTHONIOENCODING=utf-8`**：SKILL.md 里有中文/emoji 时，不设会抛 GBK 编码错误。
- 建议每次加 `--skip-self-upgrade`，避免联网自更新拖慢或失败。

## 3. 标准流程

```bash
# ① 包内自查（务必先做，见 §4）
# ② 本地预检：只校验 metadata + 打包，不发 HTTP
skillhub --skip-self-upgrade publish <目录或.zip> --dry-run
#    看到 ✓ Dry-run passed: <slug>@<version> 才算过

# ③ 登录（token 不要回显、不要写进任何文件）
skillhub --skip-self-upgrade login --key skh_xxx --host https://api.skillhub.cn
skillhub --skip-self-upgrade auth whoami      # 应输出 userId / handle / role 三行

# ④ 正式发布
skillhub --skip-self-upgrade publish <目录或.zip> --changelog "首次发布"

# ⑤ 核验：✓ Published: skillId=xxx status=pending_review
#    再校验本机副本与平台签名一致（避免发布副本与本地源漂移）
skillhub --skip-self-upgrade verify <slug> --zip <zip路径> --json
```

- **更新**：`slug` 保持不变，改 `version`，`--changelog` 写本次变更。
- ⚠️ `--dir` 默认 `./skills`（相对当前目录），**只在 install 时相关**；publish 用位置参数指定路径。
- 发布成功 ≠ 立即可见：审核期间详情页会显示"未找到"，去「个人中心 → 我的 Skills」看实时状态。

## 4. 发布前包内自查（不可省）

**打包排除项**（CLI 自动排除，自己打 zip 时也要照做）：
目录 `.git` `.idea` `.vscode` `node_modules` `__pycache__`；后缀 `.pyc` `.DS_Store` `Thumbs.db`。

**平台限额**（网页向导）：≤200 个文件、≤10 MB。

**密钥扫描**（任何发布都是对外动作）：

```bash
grep -rnE "MIIE|BEGIN (RSA )?PRIVATE KEY|(api[_-]?key|token|secret|password)\s*[:=]\s*[A-Za-z0-9_-]{16,}|skh_[A-Za-z0-9]|sk-[a-z0-9]{16,}|ghp_" <包目录>
```

有命中就**停下来问用户**，不要自行删改。付费类 Skill 另需确认：包里**不含** `.env`、密钥、状态文件、`node_modules`。

**打 zip**（保持 `SKILL.md` 在根目录）：

```python
import zipfile, pathlib, os
src = pathlib.Path(r"<包目录>"); out = pathlib.Path(r"<输出>.zip")
EX_DIRS = {".git", ".idea", ".vscode", "node_modules", "__pycache__"}
EX_SUF = (".pyc", ".DS_Store", "Thumbs.db")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EX_DIRS]
        for f in sorted(files):
            if not f.endswith(EX_SUF):
                p = pathlib.Path(root, f); zf.write(p, p.relative_to(src).as_posix())
```

打完**用 `publish <zip> --dry-run` 反向验证 zip 结构**（比肉眼检查可靠）。

## 5. 错误码判读

| 现象 | 真因 | 处理 |
|---|---|---|
| `Error: SKILL.md 缺少 slug / version / displayName` | frontmatter 缺字段 | 补 §1 三件套 |
| `slug 不合法（必须 kebab-case 3-128 char）` | 含大写/下划线 | 改成小写 + 连字符 |
| `401 invalid api key` | Token 失效/撤销 | 重建 key 再 login |
| `403 请先完成实名认证` | 未实名 | 网页完成人脸核身 |
| `409 slug 已被其他用户占用` | slug 非唯一 | 换名（**已上线的 slug 不可改，更新时必须一致**） |
| `429 请求过于频繁` | 限频 | 等约 1 分钟后重试 |
| 发布成功但详情页"未找到" | 审核中 | 个人中心「我的 Skills」看状态 |
| `command not found: skillhub` | PATH | 用 `~/.local/bin/skillhub` 全路径，或新开终端 |

## 5.5 上架后怎么确认"真的上线了"（2026-10-03 补）

⚠️ **`skillhub search` 不能当上架证据。** 未索引的新技能会让检索**回退到通用榜单** —— 表现是**用几个毫不相关的关键词查，返回的却是同一批结果**。判据：多关键词同结果 ⇒ 未命中，不是"搜到了"。别把回退榜单里的同名近似技能当成自己的。

可靠的验收顺序（官方「五、上架后买家验证」）：
1. **Skill 详情页可访问**（"提交成功/预检通过"≠已上架，还要过审；审核期详情页显示"未找到"，状态在「个人中心 → 我的 Skills」）。
2. **真实买家验证**：用**与卖家不同的**支付宝账号，从 SkillHub 装**已上架版本**，按买家日常说法触发一次，核对「详情页展示价 = 付款前提示 = 实际账单金额」三者一致。
   - 沙箱测试与本地自测覆盖不到：上架版本的安装、Skill 触发、生产配置、真实支付体验。
   - ⚠️ 官方文档全程只说"支持加载 Skill 的 AI 编程助手"，**未点名任何客户端**；不要假定买家一定在某个特定 IDE 里。

**买家侧支付依赖**：`npx -y @alipay/agent-payment@latest install`（这是**安装器**，真 CLI 是 `alipay-bot`，装完可能不在 PATH）。买家侧流程 = 请求服务 → 402 账单 → 对话内确认付款（扫码）→ 携凭证重试 → 服务端验付 → 返回资源 + 履约回执。**全流程不跳站外页面。**

## 6. 诚实边界（本轮实测到哪一步）

**已实测（2026-10-02）**：`--dry-run` 对「目录」和「.zip」两种入参都通过；缺 `slug/version/displayName` 时确实报 "缺少 slug"（阴性对照，证明校验真的在跑）；CLI 源码中确认 publish payload 无付费字段。

**未实测**：`login` / `publish` 真实投递 / `verify` 签名比对 —— 本轮因**缺 `skh_` Token**（本地 `~/.skillhub/auth.json` 是 Sep-2 的 `sk_`/`rt_` 网页态 token，已过期且**不是 CLI 凭据**）而中止。首次真正发布后应回来补齐这一段的实际输出与状态流转。

**Agent 无法代劳的部分**：网页登录态、实名人脸核身、付费 Pay Skill 向导交互、上传 zip。能代劳的是：包内自查、元数据补齐、打 zip、dry-run、CLI 发布与核验。
