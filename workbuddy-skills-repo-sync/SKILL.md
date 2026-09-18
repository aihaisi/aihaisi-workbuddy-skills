---
name: workbuddy-skills-repo-sync
description: 提交并推送 WorkBuddy 个人技能库（~/.workbuddy/skills，远端 aihaisi-workbuddy-skills）到 GitHub。包含发布级脱敏扫描、密钥扫描、嵌套仓库卫生检查、以及在本机校园网下绕开失效的 SSH pushurl 走 HTTPS 代理推送的完整流程。当用户说"技能仓库提交推送""把技能库同步一下""推一下 skills""技能库归档"时使用。
agent_created: true
---

# WorkBuddy 技能库提交与推送

## 0. 先认清是哪个仓库（最容易错的一步）

| 仓库 | 路径 | 远端 | 分支 | 说明 |
|---|---|---|---|---|
| ✅ **本技能库** | `~/.workbuddy/skills` | `github.com/aihaisi/aihaisi-workbuddy-skills.git` | `main` | **要操作的是这个** |
| ❌ D 盘旧库 | `D:\aihaisi-skill-hub` | `github.com/aihaisi/aihaisi-skill-hub.git` | `master` | 另一个仓库，**不要碰** |

用户说"你自己那个技能库"时，100% 指 `~/.workbuddy/skills`。D 盘那个是历史遗留，容易混。

## 1. 环境前置（Windows / 本机 shell 必做）

Bash 工具启动时 PATH 被 shim 破坏（`ls: command not found`、`dirname: command not found`），**每条命令前都要显式修**。用 `$HOME` 而非写死用户名：

```bash
export PATH="/usr/bin:/bin:/c/Windows/System32:$HOME/.workbuddy/binaries/python/versions/3.13.12:$HOME/.workbuddy/binaries/node/versions/22.22.2-3:$PATH"
cd "$HOME/.workbuddy/skills" && git status --short
```

`cd` 用绝对路径并与后续命令用 `&&` 串联（shim 会丢掉 `cd` 的目录参数）。**不要用 PowerShell 工具**（本机 stdout 捕获为空，取不到数据）。

## 2. 发布级脱敏（仓库硬约定，推送前必做）

这是仓库创建者（用户本人）确立的规则：**公开仓库里不得出现本机用户名/绝对路径**。

```bash
cd "$HOME/.workbuddy/skills"
git ls-files -z | xargs -0 grep -ln "17876" 2>/dev/null
git ls-files -z | xargs -0 grep -ln 'C:\\Users' 2>/dev/null
```

命中就改，替换对照表：

| 原样 | 替换为 |
|---|---|
| `C:\Users\<用户名>\.dsh\...` | `%USERPROFILE%\.dsh\...` |
| `C:\Users\<用户名>\AppData\Roaming\npm\...` | `%APPDATA%\npm\...` |
| 写死的 venv / node 绝对路径 | `$HOME/.workbuddy/binaries/.../<版本>` |
| 脚本里的 Python 调用 | `WORKBUDDY_PYTHON` 环境变量 + 托管 venv 自动探测 |
| 工作区绝对路径 | `<工作区>` 占位 |

MSYS 环境下路径转换会被禁用，脚本里改用 **`cygpath` 显式转换**。

⚠️ **给文档写命令示例时也要遵守** —— 别在技能自身的说明里留 `C:/Users/<用户名>`，用 `$HOME` 代替，否则下次扫描会命中自己。

⚠️ **两个已知的假阳性 / 陷阱**

| 现象 | 说明 |
|---|---|
| 扫描命令命中**它自己** | 命令串里就含 `17876`，属预期，忽略 |
| `_skillhub_meta.json` 里的 `iconLocalPath` | **真实泄露**。带图标的技能（marketplace 安装）会多这个字段，值是本机绝对路径，须改成 `%USERPROFILE%\...`。该文件由 WorkBuddy 自动生成、**可能被重新写回绝对路径**，所以每次推送前都要复扫，不要以为改过一次就永久干净 |

## 3. 密钥扫描（公开前必做）

```bash
git ls-files -z | xargs -0 grep -lniE "sk-[a-z0-9]{16,}|ghp_|gho_|github_pat_|AKID|password\s*[:=]|api[_-]?key\s*[:=]" 2>/dev/null
```

有命中就**停下来问用户**，不要自作主张删除或提交。

## 4. 嵌套仓库卫生（本库反复出现的问题）

**症状**：`git status` 长期显示某个技能目录 `modified (untracked content)`，长格式提示 `(commit or discard the untracked or modified content in submodules)`。

**诊断**：

```bash
# 找带 .git 的技能目录
for d in */; do [ -e "$d/.git" ] && echo "NESTED: $d"; done
git ls-files -s <目录名>              # 是否被记为 gitlink(160000)
cat .gitmodules 2>/dev/null || echo "(无)"   # 真 submodule 必有此文件
```

gitlink 存在但**无 `.gitmodules`** = 误入的嵌套仓库，不是 submodule。

**处理原则**：

1. **先判断是不是用户自己的代码** —— 看内层 `git remote -v`。远端不是 `aihaisi/*` 就是第三方。
2. **查上游是否已包含本地所有提交**（最关键的判据）：
   ```bash
   git -C <目录> rev-parse HEAD
   GIT_TERMINAL_PROMPT=0 git ls-remote "https://github.com/<上游>.git" refs/heads/main
   ```
   **两者相同 → 本地无独有内容 → 摘除不丢任何东西。**
3. **查许可**：无 `LICENSE` 文件 = 默认保留全部权利 = **不要再分发**（不要 vendor 进公开仓库）。
4. **推荐处理：只登记来源，不转发代码**
   ```bash
   git rm --cached <目录>     # 只动索引，磁盘文件完好（务必事后核对文件数）
   ```
   然后写进 `.gitignore`，并在 `README.md`「外部来源技能」表格登记上游地址 + 版本号 + 重装命令。

**为什么不用 submodule**：本库定位是「克隆即可直接复制技能目录使用」的纯内容库，submodule 让克隆多一步 `--recursive`，且上游删库会留下悬空引用。

**顺带检查**：`git ls-files | grep -E "__pycache__|\.pyc$"` —— 编译产物若被误跟踪，一并 `git rm --cached`。

## 5. 提交

```bash
cd "$HOME/.workbuddy/skills"
git add -A
git -c core.quotepath=false diff --cached --stat   # 复核
git -c core.quotepath=false commit -q -F - <<'MSG'
<中文提交信息：先说问题，再说处理，再说为什么这么选>
MSG
```

提交信息写**判断依据**（改了什么、为什么这样改），不写"update files"。

## 6. 推送（本机关键坑）

### 坑：`origin` 的 push URL 是 SSH，在本机网络上推不动

校园网 DNS（10.1.2.1）解析不了 `github.com`，SSH 不走代理 → `ssh: Could not resolve hostname github.com`。而且 **`git ls-remote origin` 走的也是 SSH，同样失败**，连远端状态都查不到。

### 可靠推法：绕开 pushurl，显式用 HTTPS URL

必须加 `dangerouslyDisableSandbox: true`（沙箱内 DNS/443 被拦），并设 `GIT_TERMINAL_PROMPT=0` 防凭据提示挂起：

```bash
cd "$HOME/.workbuddy/skills"
GIT_TERMINAL_PROMPT=0 timeout 180 \
  git push "https://github.com/aihaisi/aihaisi-workbuddy-skills.git" main
```

HTTPS 走全局 `http.<host>.proxy` → `127.0.0.1:7897`（Clash 混合端口，**必须规则模式**）。前提：Clash 正在运行。

### 坑：推送成功后 `git status` 仍显示 "ahead by N commits"

因为 fetch 也走 SSH 而失败，`refs/remotes/origin/main` 是**过期的**，ahead/behind 判断失真。

修正（用 HTTPS 显式拉一次追踪引用）：

```bash
GIT_TERMINAL_PROMPT=0 timeout 180 \
  git fetch "https://github.com/aihaisi/aihaisi-workbuddy-skills.git" main:refs/remotes/origin/main
```

## 7. 核验（必须做，不能只看 push 输出）

```bash
URL="https://github.com/aihaisi/aihaisi-workbuddy-skills.git"
git rev-parse HEAD
GIT_TERMINAL_PROMPT=0 git ls-remote "$URL" refs/heads/main    # 两者必须一致
git ls-tree --name-only origin/main | grep <新增目录>          # 新内容确实上去了
git status -sb                                                # 应显示 ## main...origin/main 无分叉
```

## 8. 收尾

- 新增/修改技能时，**同步 `_skillhub_meta.json` 与迁移标记**（WorkBuddy 会生成，一并提交）。
- 每次操作后更新长期记忆（`~/.workbuddy/MEMORY.md`）里的「技能库 git 仓库」段——当前网络事实会变。

## 本机常量速查

| 项 | 值 |
|---|---|
| 仓库根 | `~/.workbuddy/skills` |
| 分支 | `main` |
| 远端 | `aihaisi/aihaisi-workbuddy-skills.git` |
| 代理 | `127.0.0.1:7897`，Clash 规则模式，需 `dangerouslyDisableSandbox` |
| pushurl 现状 | SSH —— **本机不可用**，一律显式 HTTPS URL |
| 推送前置 | 脱敏扫描 → 密钥扫描 → 嵌套仓库检查 → `GIT_TERMINAL_PROMPT=0` |
