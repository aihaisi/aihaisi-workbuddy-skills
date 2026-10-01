---
name: publish-html-prototype-share-link
description: 把本地原型（单文件 HTML 小游戏/工具）发布成一个"点开即玩"的公开分享链接，并验证上线后没有泄露开发侧文件。覆盖两个高频陷阱：直接把项目根目录当发布源会把 .workbuddy/.env 等内部文件变成公开 URL；发布源是副本时会与源文件漂移导致线上跑旧版本。当用户说"别人一点就能玩""给我个链接""发个能玩的地址""分享给同学玩""部署上线"时使用。
agent_created: true
---

# 把原型发布成分享链接

## 0. 先做方案取舍（国内用户必看）

| 方案 | 适用 | 关键限制 |
|---|---|---|
| **WorkBuddy 云端发布** | 要发给国内的人玩 | 首选。独立域名、国内直连、可下线 |
| GitHub Pages | 面向海外/技术读者 | **国内访问不稳**，发给同学大概率打不开。别默认选它 |

判断依据是**"谁会打开这个链接"**，不是"哪个更省事"。发给中国同学/老师 ⇒ 云端发布。

## 1. ⚠️ 发布源目录 ≠ 项目根目录（最重要的一步）

**根目录几乎一定包含不该公开的东西**，而静态发布会把目录里**所有**文件变成可访问 URL：

- `.workbuddy/`（项目记忆、daily log、MEMORY.md —— 里面有本机路径、代理端口等）
- `.env*`、`.git/`、依赖清单、内部笔记、验证脚本

**做法**：新建一个专用发布目录，里面**只放要发布的那一个文件**。

```bash
mkdir -p site && cp index.html site/index.html
```

好处不只是安全：`site/` 也成了明确的发布契约（谁看都知道线上跑的是哪个文件）。

## 2. 副本会漂移 ⇒ 把「一致性」变成测试断言

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

**必须做负向测试**：往副本追加几个字节，确认断言真的会让退出码变成 1。
没验证过"能失败"的断言只是装饰。

## 3. 发布（静态站）

调 `workbuddy_sites_deploy`：`directory` 指向 `site/`，`language: "static"`，
`appName` 用中文短名（≤12 字），`domainPrefix` 用同名英文 slug。
**用户上一句没说要发布就先问**（发布=覆盖线上现有内容）。

## 4. 上线后核验（看到"发布成功"不算完）

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

## 5. 收尾

- README 补「在线试玩」小节 + 项目结构树里加发布目录，并**说明为何不发根目录**
- `.gitignore` 加 `*.genie` / `.wbapp_*`（发布会写一个工具内部标记文件到项目根）
- 改完源码 → `cp index.html site/index.html` → 跑验证器 → 提交推送

## 6. 发布之后怎么管理（用户常问）

### 云端入口

**设置 → 数据管理 →「我发布的应用」**（英文 `Settings - Data Management - Published Apps`）。
该入口在部分发行版里被产品开关隐藏（`DisablePublishedAppEntry`），正常版本默认显示。

| 想做的事 | 在哪做 |
|---|---|
| 看已发布应用列表 / 访问链接 | 上面这个面板 |
| 更新线上内容 | **不在面板里** —— 在对话里让 Agent 用同一目录再发布一次（覆盖式，链接不变） |
| 暂时下线（链接失效、应用保留） | 对话里让 Agent unpublish，或面板操作 |
| 彻底删除 | 面板「删除应用」——**终态、不可恢复** |

⚠️ **「下线」和「删除」不是一回事，别混用**：
- **取消发布**：链接停用，应用及其配置还在，可以再发。
- **删除应用**：云端一次调用级联 —— 终止发布 + 解绑云服务 + 释放子域名 + 软删应用，**不可恢复**。
  如果这个应用已经接过云服务（有数据库/登录），删除会把它们一起带走。

### 本机的留痕（诊断时先看这三处）

| 路径 | 内容 |
|---|---|
| `<工作区>/.workbuddy/applications.yaml` | 本会话的应用清单：`name` + `locator`(=appId) |
| `<工作区>/.<appId>.genie` | `appId / name / localDir / appType / entryHtml` —— **appId → 发布目录的映射载体** |
| `~/.workbuddy/cloudstudio-deploy-history/*.json` | 每次发布的完整记录：沙箱 id、shareLink、contentHash、entryHtml、时间戳 |

`.genie` 里的 `localDir` 是关键：云端**刻意不返回**本地目录，所以「哪个 appId 对应本机哪个目录」
只能靠它。删了它，应用列表里那张卡片就找不到发布源。

## 坑：`git push` 超时但链路是好的

`curl -x <proxy> https://github.com` 返回 200、`api.github.com` 也 200，push 却 `exit 124` 且日志为空。
**这是偶发，原样重试一次通常就成功**。不要在这时去改 proxy/remote 配置——排查成本远高于重试。
（真要重试前，先把日志重定向到文件再读，别用 `| tail`，被 SIGTERM 后管道缓冲会丢。）
