# 发布之后的运营、留痕与常见故障

> 配套 `html-prototype-verify-ship/SKILL.md` 阶段 ③。发布成功之后的事都在这。

## 1. 云端入口

**设置 → 数据管理 →「我发布的应用」**（英文 `Settings - Data Management - Published Apps`）。该入口在部分发行版里被产品开关隐藏（`DisablePublishedAppEntry`），正常版本默认显示。

| 想做的事 | 在哪做 |
|---|---|
| 看已发布应用列表 / 访问链接 | 上面这个面板 |
| 更新线上内容 | **不在面板里** —— 在对话里让 Agent 用同一目录再发布一次（覆盖式，链接不变） |
| 暂时下线（链接失效、应用保留） | 对话里让 Agent unpublish，或面板操作 |
| 彻底删除 | 面板「删除应用」—— **终态、不可恢复** |

⚠️ **「下线」和「删除」不是一回事，别混用**：

- **取消发布**：链接停用，应用及其配置还在，可以再发。
- **删除应用**：云端一次调用级联 —— 终止发布 + 解绑云服务 + 释放子域名 + 软删应用，**不可恢复**。如果这个应用已经接过云服务（有数据库/登录），删除会把它们一起带走。

## 2. 本机的留痕（诊断时先看这三处）

| 路径 | 内容 |
|---|---|
| `<工作区>/.workbuddy/applications.yaml` | 本会话的应用清单：`name` + `locator`(=appId) |
| `<工作区>/.<appId>.genie` | `appId / name / localDir / appType / entryHtml` —— **appId → 发布目录的映射载体** |
| `~/.workbuddy/cloudstudio-deploy-history/*.json` | 每次发布的完整记录：沙箱 id、shareLink、contentHash、entryHtml、时间戳 |

`.genie` 里的 `localDir` 是关键：云端**刻意不返回**本地目录，所以「哪个 appId 对应本机哪个目录」只能靠它。删了它，应用列表里那张卡片就找不到发布源。

## 3. 坑：`git push` 超时但链路是好的

`curl -x <proxy> https://github.com` 返回 200、`api.github.com` 也 200，push 却 `exit 124` 且日志为空。

**这是偶发，原样重试一次通常就成功。** 不要在这时去改 proxy/remote 配置 —— 排查成本远高于重试。

（真要重试前，先把日志重定向到文件再读，别用 `| tail`：被 SIGTERM 后管道缓冲会丢，表现为"无输出的莫名失败"。）
