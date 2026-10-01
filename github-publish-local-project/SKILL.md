---
name: github-publish-local-project
description: 把一个本地项目目录发布成 GitHub 上的新仓库（建仓 + README + 首次推送 + 远端核验）。覆盖本机五个高发误判：推送必弹 credential helper 窗（PortableGit 的 helper-selector 挂在系统级、且 credential.helper 是多值追加所以勾 Always 无效）、Clash 处于直连模式（端口在监听、经代理境内 200 但境外全 000，push 报 schannel handshake 失败）、Clash GUI 没开导致 gh 假报 token 失效、gh 走了通不了的 6040 代理、gh repo create 不支持 --add-topic；并澄清「取 gh token 不需要代理、访问 github.com 才需要」。当用户说"上传到 GitHub""推到 github""建个仓库公开""发布这个项目""写个 README 然后 push""推送时老弹窗"时使用。
agent_created: true
---

# 把本地项目发布到 GitHub 新仓库

> 只处理「**新仓库 + 首次推送**」。往已有的技能库 `~/.workbuddy/skills` 提交推送是另一件事，走 `workbuddy-skills-repo-sync`，别混用。

## 1. 环境前置

Bash 工具启动时 PATH 被 shim 破坏（`ls: command not found`），每条命令前必须显式修：

```bash
export PATH="/usr/bin:/bin:/c/Windows/System32:$HOME/.workbuddy/binaries/python/versions/3.13.12:$HOME/.workbuddy/binaries/node/versions/22.22.2-3:$PATH"
```

`cd` 写绝对路径并用 `&&` 串联（shim 会吞掉 `cd` 的目录参数）。**不要用 PowerShell 工具**（本机 stdout 捕获为空）。

网络操作一律加 `dangerouslyDisableSandbox: true`。

## 2. 网络预检（最容易误判的一步，先做）

```bash
netstat -ano | grep LISTENING | grep ':7897'            # 代理端口在不在
curl -s -o /dev/null -w "%{http_code}\n" --max-time 8 --noproxy '*' https://www.baidu.com   # 期望 200
curl -s -o /dev/null -w "%{http_code}\n" --max-time 8 --noproxy '*' https://github.com      # 期望 000
```

上面三条是**直连探测**（`--noproxy`）。再加一组**经代理探测**，两组一起看才能分清是"代理没开"还是"代理开了但不通"：

```bash
netstat -ano | grep LISTENING | grep ':7897'                                     # 端口在不在
curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 -x http://127.0.0.1:7897 https://www.baidu.com   # 经代理访问境内
curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 -x http://127.0.0.1:7897 https://github.com      # 经代理访问境外
```

**判据表（两种失效模式的症状完全不同，别混为一谈）**：

| `netstat` 7897 | 直连境内 | 直连境外 | 经代理境内 | 经代理境外 | 结论 |
|---|---|---|---|---|---|
| 无监听 | 200 | 000 | 连接失败 | 连接失败 | **代理没开** → 请用户启动 Clash Verge |
| 有监听 | 200 | 000 | 200 | **000** | **分流模式错（直连模式）或节点挂了** → 见下 |

⚠️ **别用进程名判断代理是否在跑**：`clash-verge-service.exe` 是后台服务，**Clash Verge 的 GUI 没启动时它照样在跑**，但混合端口 7897 根本不存在。
`netstat` 查不到 7897 就是没开 → **直接请用户启动 Clash Verge（规则模式）**，这是唯一需要用户动手的一步。

### 2.1 ⚠️ 端口在监听但境外仍 000 = 直连模式 **或 当前节点挂了**（2026-09-24 实测，两种都遇到过）

**这是与"代理没开"并列的第二种失效模式，极易误判**：端口在监听、`clash-verge.exe` 与 `verge-mihomo.exe` 都在进程表、经代理访问百度 200 —— 一切看着都正常，唯独境外全 000，
`git push` 报 **`schannel: failed to receive handshake, SSL/TLS connection failed`**（exit 128）。

**两个成因，症状完全一样，从外部无法区分**：

| 成因 | 说明 |
|---|---|
| (a) 分流模式设成 `direct`（直连） | 所有流量都不走节点，境外自然出不去 |
| (b) **节点本身挂了 / 未选中节点**（2026-09-24 实测遇到的正是这个） | 模式正常、规则正常，但出口节点不可用 |

**判别小技巧**：成因 (b) 时**境内域名经代理仍返回 200**（请求在代理内部被直连规则接住了），
而成因 (a) 理论上也是境内 200 —— 所以**光看 curl 结果区分不出来**。

✅ **统一处理：直接请用户在 Clash Verge 里「换一个节点 + 确认是规则模式」，然后复验。**
本次实测：用户换节点后 `curl -x 7897 https://github.com` **立刻从 000 变 200**，无需改动任何 git 配置。
**别在这上面改 git 配置 / hosts / DNS —— 问题 100% 在代理出口侧。**
这个判据是可复验的开关：切之前 000、切之后 200 就定论。

> 与此对照：如果 7897 **无监听**，那才是"代理没开"，也要请用户启动 Clash —— 但那是另一回事，别混。

- **别指望用 API 自动切模式**：`127.0.0.1:9090/configs`、`:9080/configs` 实测均无响应（Verge Rev 的 external-controller 未对外暴露）。
  直接让用户切，然后用上面的"经代理探测"复验 `github.com` 是否变 200，最快。
- 判据要写成**可复验的开关**：切之前 000、切之后 200，就确认是模式问题，不用再怀疑 DNS/hosts/凭据/token。

✅ **别急着断定"没有可用代理"——先逐个端口探测**（2026-09-24 实测有效，省掉一轮来回问用户）：
7897 不在监听时，本机仍可能有别的代理端口；而且 Clash 有时会在探测时自行起来。一轮 10 秒的扫描能直接定论：

```bash
netstat -ano | grep LISTENING | grep '127.0.0.1:' | awk '{print $2}' | sed 's/.*://' | sort -u
for p in $(netstat -ano | grep LISTENING | grep '127.0.0.1:' | awk '{print $2}' | sed 's/.*://' | sort -u) 7897; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 6 -x "http://127.0.0.1:$p" https://api.github.com)
  printf "  :%-6s -> %s\n" "$p" "${code:-timeout}"      # 200 = 这个端口能通 GitHub
done
```

判据：**只有能对 `api.github.com` 返回 200 的端口才是可用代理**（000/timeout 一律排除）。
拿到端口就 `export HTTPS_PROXY=http://127.0.0.1:<port>` 继续，不必再打断用户。

## 3. ⚠️ gh 的代理坑（本机高发，会浪费大量时间）

环境里被注入了 `HTTPS_PROXY/HTTP_PROXY=http://127.0.0.1:6040`，**这个代理通不了 GitHub**。后果具有极强的误导性：

| 症状 | 真相 |
|---|---|
| `gh auth status` 报 `The token in keyring is invalid.` | **token 是好的**，只是请求没到 GitHub |
| `gh api user` 报 `Bad Gateway` | 同上，6040 返回 502 |
| `git` 命令却正常 | `http.<host>.proxy` 配置优先级高于环境变量，git 走的是 7897 |

**验证 token 真伪（不依赖 gh）**：

```bash
TOK=$(gh auth token)
curl -sI --max-time 20 -x http://127.0.0.1:7897 -H "Authorization: Bearer $TOK" https://api.github.com/user \
  | grep -i '^x-oauth-scopes'      # 能看到 scope 列表 = token 有效
```

**解法——任何 gh 命令前显式改代理**：

```bash
export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897
gh auth status        # 此时应显示 ✓ Logged in，token scope 含 repo
```

`repo` scope 是建仓必需。若 token 确实过期，才让用户 `gh auth refresh -h github.com`。

## 3.5 ⚠️ 每次推送都弹「Select a credential helper」窗（2026-09-24 已修复）

**症状**：每次 `git push` 到 GitHub 都弹出 `Credential Helper` 选择框（`<no helper>` / `manager` / `wincred`），
用户勾了 `Always use this from now on` 也照弹。

**根因（两层，缺一不可，别只看到一层就动手）**：

1. **`credential.helper` 是多值追加配置，不是覆盖** —— git 会**按顺序执行链上每一个 helper**。
   用 `git config --show-origin --get-all credential.helper` 看，返回几条就说明有几条会被调用：

   ```
   file:.../PortableGit/.../etc/gitconfig     helper-selector                     ← 系统级，会被执行
   file:C:/Users/<user>/.gitconfig            !".../git-credential-manager.exe"   ← 用户级，也会被执行
   ```

2. **`helper-selector` 是个"选择器 UI"，不是真助手**。它在 PortableGit 的 `mingw64/bin/git-credential-helper-selector.exe`，
   由 PortableGit 预置在**系统级** gitconfig（`[credential] helper = helper-selector`），本身不提供任何凭据、只负责弹窗让你挑一个。
   ⇒ **`Always use this from now on` 治不了它** —— 那个勾只写入用户级 `[credential "helperselector"] selected = manager`
   （**给选择器看的一份备忘**），根本没把它从 helper 链上摘掉。勾多少遍都无效。

**正解：用 git 的空值 reset 语义，在 host 作用域切断继承**：

```bash
cp ~/.gitconfig ~/.gitconfig.bak-$(date +%Y%m%d)          # 先备份
git config --global --replace-all credential.https://github.com.helper ""
git config --global --add credential.https://github.com.helper "C:/Users/<user>/ghcred.cmd"
```

`helper = ""`（**空字符串**）是 git 的官方语义：**reset 掉该作用域继承来的整条链**。
结果 github 作用域的链变成 `["", "ghcred.cmd"]`，系统级的 `helper-selector` 被排除；全局链不动，不影响其它 host。

**⚠️ 验证方式 —— 光看配置文件不算证明，必须证明「实际没被调用」**：

配置写对 ≠ 生效。用探针脚本挂在 helper 位置，记录 git 真正调用了谁：

```bash
cat > /tmp/probe.sh <<'EOF'
#!/bin/bash
echo "PROBE-CALLED action=$1" >> /tmp/helper-calls.log
exec "C:/Users/<user>/ghcred.cmd" "$@"
EOF
chmod +x /tmp/probe.sh
git config --global --replace-all credential.https://github.com.helper ""
git config --global --add credential.https://github.com.helper "/tmp/probe.sh"
printf 'protocol=https\nhost=github.com\n\n' | GIT_TERMINAL_PROMPT=0 git credential fill
cat /tmp/helper-calls.log     # 期望：只有 PROBE-CALLED 一行，没有 helper-selector
```

判据：`helper-selector` 是个真实进程，若仍在链上被调用，它同样会留下痕迹（弹窗）。
**日志里只有探针自己 ⇒ 链确已切断**。验证完记得把探针换成正式的 `ghcred.cmd`。
（`git credential fill` 在**管道/stdin 非交互**时 `helper-selector` 会静默退出不弹窗，
所以**必须靠探针记录调用**，不能靠"我这里跑 fill 没弹窗"就下结论。）

## 3.6 「取 gh token」不需要代理，「访问 github.com」才需要 —— 两件事别混

用户常问「gh token 是不是必须挂代理？我记得刚配 gh 时没挂代理就能用」。**那个记忆是对的**，因为这是两个环节：

| 环节 | 需要代理 | 原因 |
|---|---|---|
| 取 gh token | ❌ | token 存 Windows 凭据管理器（本地密钥环），`gh auth git-credential` 是**纯本地读取** |
| 访问 github.com | ✅ | 校园网 DNS 解析不了 github.com，国内直连不通 |

实测证据（可直接复现）：

```bash
unset HTTPS_PROXY HTTP_PROXY
echo "protocol=https
host=github.com
" | cmd //c "C:\\Users\\<user>\\ghcred.cmd get"      # 仍返回 username + password=token（exit 0）
git -c http.https://github.com.proxy= ls-remote https://github.com/OWNER/REPO.git refs/heads/main
# → fatal: Could not resolve host: github.com（exit 128）
```

⇒ **「gh 配好了」≠「能推送了」**。前者是本地凭据，后者是网络可达性，两者因都叫 "GitHub" 而极易混淆。
回答这类疑问时要把环节拆开讲，别笼统说"要梯子"。

## 4. 本地准备

### 4.1 `.gitignore` 必须先写

**项目数据目录不进公开仓库**，尤其 `.workbuddy/`（记忆、技能缓存）：

```gitignore
.workbuddy/
.vscode/
.idea/
.DS_Store
Thumbs.db
node_modules/
*.log
```

### 4.2 README 写作要求

公开仓库的 README 是**对外交付物**，不是内部笔记。最低标准：

- 一句话说清**这是什么 + 从哪来**（若源自某题/某论文，给出来源链接，并**先实测链接可访问**）
- **快速开始**（怎么跑起来，几条命令）
- 核心内容的**可验证结论**（不是营销话术：给数字、给公式、给表格）
- 若有验证脚本：写出**跑一次的命令**和**覆盖了哪几层**
- 项目结构、License
- ⚠️ **别把内部调试过程、待办、临时路径写进去**；`.workbuddy/memory` 里的内容不外泄

### 4.3 提交前自查

```bash
cd <项目目录> && git status --short          # 确认敏感目录未被纳入
git ls-files                                 # 逐条看一遍
```

## 5. 建仓 + 绑定远端

```bash
export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897
gh repo view <owner>/<name> --json name 2>&1   # 先查重名，避免误判失败原因
gh repo create <owner>/<name> --public --description "一句话描述"
```

⚠️ **`gh repo create`（2.97）没有 `--add-topic` 参数** —— 传了会**打印帮助文本并失败**（exit 0，很容易误以为成功）。topic 必须单独加：

```bash
gh repo edit <owner>/<name> \
  --add-topic game-theory --add-topic verification ...
gh api repos/<owner>/<name>/topics --jq '.names'    # 核验
```

**远端一律显式用 HTTPS**（SSH 在本机解析不了 `github.com`，且 `insteadOf` 只覆盖 `ssh://`/`git+ssh://`，**不覆盖 `git@github.com:` 这种 scp 写法**）：

```bash
git remote remove origin 2>/dev/null
git remote add origin https://github.com/<owner>/<name>.git
```

## 6. 推送

```bash
cd <项目目录>
export GIT_TERMINAL_PROMPT=0
timeout 240 git push -u origin main > /tmp/push.log 2>&1; echo "exit=$?"; cat /tmp/push.log
```

⚠️ **不要写 `git push ... 2>&1 | tail -8`**：命令一旦被 timeout SIGTERM，管道缓冲丢失，你会看到「**零输出的莫名失败**」，然后误判成认证问题。**一律重定向到文件再读**。

⚠️ **不要把「curl 探测」和「git push」串在同一条 Bash 命令里**（2026-09-24 实测踩坑）：`curl` 15s + `push` 180s 会超过工具默认 120s 前台超时，
整条命令被 SIGTERM（工具报 `Signal: SIGTERM`），此时 **push 的结果不可知** —— 看起来像推送失败，实际可能已经推成功或推了一半。
**拆成两条命令**：先单独探测，确认 200 后再单独 push，push 那条显式给足超时（`timeout: 300000`）。

`GIT_TERMINAL_PROMPT=0` + `timeout` 是必备护栏，否则凭据提示会让命令挂到超时。

## 7. 核验（必须做，不能只看 push 输出）

```bash
cd <项目目录>
LOCAL=$(git rev-parse HEAD)
# 首选：走 GitHub API 读远端真实 HEAD（ls-remote 不可靠，见下）
gh api repos/<owner>/<name>/commits/main --jq '.sha[0:7] + "  " + (.commit.message | split("\n")[0])'
echo "local=$(git rev-parse --short HEAD)"
[ "$(git rev-parse HEAD)" = "$(gh api repos/<owner>/<name>/commits/main --jq .sha)" ] \
  && echo "✓ 提交一致" || echo "✗ 不一致"

gh api repos/<owner>/<name>/git/trees/main?recursive=1 --jq '.tree[] | "\(.type)\t\(.size // "-")\t\(.path)"'
gh api repos/<owner>/<name> --jq '"\(.visibility) / \(.default_branch) / \(.size)KB"'
```

⚠️ **`git ls-remote` 单次读数可能是旧值，不要拿它判定"推送失败"（2026-09-24 实测踩坑）**：
一次 `push` 被 SIGTERM 打断后，`git ls-remote origin refs/heads/main` 仍报**旧 sha**，
看起来像没推上去；但紧接着 `git push` 却回 **`Everything up-to-date`** ——
再查一次才发现远端**其实早已更新**（那次被打断的 push 实际成功了）。
**判据优先级：`gh api .../commits/main` > 重新 `git push` 的返回 > `git ls-remote` 单次读数。**
遇到"远端没更新"和"up-to-date"互相矛盾时，先重新查一次再下结论，别急着重推或排查认证。

最后用 WebFetch 打开 `https://github.com/<owner>/<name>`，确认 **README 真的渲染出来了**、文件列表正确 —— 这是唯一能证明"对外可见且可读"的一步。

## 8. 失败对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| `gh auth status` 说 token invalid | 走的 6040 代理通不了 GitHub | `export HTTPS_PROXY=http://127.0.0.1:7897` |
| `gh repo create` 打印一大段帮助 | 用了该版本不支持的参数（如 `--add-topic`） | 去掉，或改用 `gh repo edit` |
| `create_repository`（GitHub MCP）返回 403 `Resource not accessible by integration` | MCP 集成令牌**无建仓权限** | 改用 `gh` CLI；MCP 只用于读取类接口 |
| push 无任何输出就失败 | 管道 + SIGTERM 吞了日志 | 重定向到文件 |
| push 挂在凭据提示 | 未设 `GIT_TERMINAL_PROMPT=0` | 补上 + `timeout` |
| push 报 `Failed to connect to github.com:443 over proxy 127.0.0.1` | 指定的代理端口当前没在监听（Clash GUI 又退了） | 先做上面的端口扫描，换到返回 200 的端口；别去改 DNS/hosts |
| push 报 `schannel: failed to receive handshake, SSL/TLS connection failed` | 端口在监听、经代理境内 200 但境外 000 ⇒ **Clash 处于直连模式**（或节点挂） | 请用户切**规则模式**，复验 `curl -x 7897 https://github.com` 变 200 |
| push 整条命令报 `Signal: SIGTERM` / 前台超时，结果不明 | 探测 + push 串在一条命令里，超了工具默认 120s | 拆成两条命令；push 单独跑并给足超时 |
| 想用 GitHub MCP 的 `push_files` 绕过网络推送 | 能推但会产生**与本地不同的 commit SHA**，本地/远端起分叉，还要 merge/rebase | 能用 git 就用 git；MCP 只做读取与建仓 |
| `Could not resolve hostname github.com` | 走了 SSH | 显式 HTTPS URL。**本机 SSH 推 GitHub 是死路**：校园网 DNS 解析不了境外域名，SSH 不走 HTTP 代理，7897 也帮不上 |
| `ls-remote` 报远端仍是旧 sha，但 `push` 回 `Everything up-to-date` | **`ls-remote` 单次读数过期**；被打断的那次 push 其实已成功 | 重查一次，或改用 `gh api repos/<owner>/<name>/commits/main --jq .sha`；**别急着重推或排查认证** |
| push 命令报 `Signal: SIGTERM` / `interrupted`（用户中断或前台超时） | 命令被打断，**推送结果不可知** | 先核验远端 sha 再决定是否重推，**不要假设失败** |

## 9. 收尾

- 提醒用户：**公开仓库一旦推送，历史里的敏感信息无法靠后续提交消除**（需 `git filter-repo` + 强推）。所以第 4 步的 `.gitignore` 和自查必须在**第一次 commit 之前**做好。
- 把「项目已发布」写进该项目的 `MEMORY.md`（远端地址、可见性、README 里哪些数字需要随逻辑改动同步更新）。
