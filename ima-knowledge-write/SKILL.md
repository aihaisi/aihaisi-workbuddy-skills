---
name: ima-knowledge-write
description: 把本地内容写进 ima 知识库时使用——覆盖本地文件入库的三步管道（create_media → COS 签名上传 → add_knowledge）、用同名 REPLACE 更新同一条目的做法、写入前脱敏要求，以及"入库成功 ≠ 可检索"的验收标准。触发词：写进 ima、存进我的知识库、上传到 ima、更新 ima 里的文档、把这份文档归档到 ima、ima 知识库怎么写入。注意：查/搜/读 ima 知识库用连接器技能 ima-mcp，本技能只管"写入管道怎么跑通"。
agent_created: true
---

# ima 知识库写入管道

## 0. 这个技能补的是什么

连接器技能 `ima-mcp` 列出了工具清单，但没说清本地文件怎么真正落地——官方入库不是一次 PUT，中间要过一道 COS 临时凭证签名。**本技能补的就是这一段可执行细节，以及验收标准。**

写入只有两条路：
- **本地文件**：`create_media` → COS 上传 → `add_knowledge`（三步，缺一步不算成功）
- **网页链接**：`import_urls`（一次最多 10 条，服务端自己抓取）

没有"直接写一段文本"的接口 —— 想写内容，必须先成文。

---

## 1. 三步管道

1. `create_media(knowledge_base_id, file_name, file_size, content_type, file_ext)`
   → 返回 `media_id` + `cos_credential`（临时 `secret_id` / `secret_key` / `token` / `cos_key`）
2. 用凭证把文件 `PUT` 到 COS（见 §2）
3. `add_knowledge(knowledge_base_id, media_id, duplicate_name_strategy)`

**两个易错参数**
- `content_type` 必须按扩展名**精确**填（`.md` → `text/markdown`），不接受 `application/octet-stream` 兜底；对照表里没有的扩展名应直接拒绝，不要猜
- `file_size` 必须与实际上传字节数**完全一致**（服务端据此校验上限）

---

## 2. COS 上传

用 `assets/cos_upload.py`，**凭证全部走环境变量**（脚本本身不含密钥，不落盘，可复用）：

```bash
export COS_SECRET_ID=... COS_SECRET_KEY=... COS_TOKEN=...
export COS_BUCKET=... COS_REGION=... COS_KEY=...
export COS_CONTENT_TYPE=text/markdown
export LOCAL_FILE='C:/abs/path/xxx.md'
python assets/cos_upload.py
```

要点：
- 签名算法是 COS 的 `q-sign-algorithm=sha1` 系列；`SignKey = HMACSHA1(SecretKey, KeyTime)`
- **临时凭证必须把 `x-cos-security-token` 同时放进 `header-list` 与请求头**（只放请求头不参与签名可能被拒）
- host 用 `{bucket}.cos.{region}.myqcloud.com`，`cos_key` 直接拼在 path 上（`/` 不转义）
- **成功标志是 HTTP 200 + 有 ETag**。响应体 `Content-Length: 0` 是正常的，不要误判失败

---

## 3. 更新已有条目 = 同名 + REPLACE

连接器没有"修改 / 删除"接口，但 `add_knowledge` 的 `duplicate_name_strategy` 支持：
- `DUPLICATE_NAME_STRATEGY_SAVE`（默认，保留副本）
- `DUPLICATE_NAME_STRATEGY_REPLACE`（替换同名的原条目）

**实测结论（2026-10-02）**：同名 REPLACE 会**替换**原条目，不新增副本 —— 条目总数不变、`file_size` 更新为新值、旧条目从列表消失。

⚠️ **副作用：REPLACE 后 media_id 会变成新的，旧 media_id 失效。** 所以不要在任何地方持久化引用 media_id，一律按标题引用。

因此"更新 ima 里的文档" = 本地改文件 → 同名三步步重传 → 自动覆盖。

---

## 4. 写入前必须脱敏

云端知识库可共享、会被检索引用，**本地绝对路径 / 用户名 / 学号 / 项目内部机制不要写进去**。

- **出处改写**：把"文件路径"改成"场景描述"（写「技能库脱敏扫描」而不是 `~/.workbuddy/skills`）
- **删掉给机器读的元信息**：frontmatter、触发词、内部技能名这类，对人无意义且污染检索
- ⚠️ **扫描命令本身不要写死真实值**——`grep 真实用户名` 会把敏感值写进命令记录，等于"为了让扫描有效反而泄露"。用 `$USERNAME` 之类的环境变量取
- **扫描必须带阳性对照**：造一个必然命中的检查，确认通路真的有效（否则"没扫"会被当成"干净"）

---

## 5. 验收标准（不能只看接口返回）

`add_knowledge` 返回 media_id **不等于**内容真的可用。三步验：

1. `get_knowledge_list` → 条目存在，`media_state=2`（解析成功）、`parse_progress=100`、`file_size` 与本地一致
2. `search_knowledge` 用**文档里独有的词**检索 → highlight 必须落在你新写的内容上（用通用词测没意义，任何文档都会命中）
3. 更新场景额外看：**条目总数是否没涨** —— 涨了说明 REPLACE 没生效，只是新增了副本

导入是异步的，刚入库检索不到属正常，等解析完成再验。

---

## 6. 图片入库：会被 OCR，因此可检索

图片（png / jpg / webp）走同一套三步管道，`content_type` 填 `image/png` / `image/jpeg` / `image/webp`。

**实测（2026-10-02）**：入库后 ima 对图片做 OCR，识别文本进 `introduction` 并**参与检索** —— 一张子网划分例题图能凭图内文字被搜到；一张时序图的摘要里完整列出了握手步骤与双方状态机。

由此两条做法：

- **`file_name` 要给有意义的中文名** —— 它是库里最关键的检索锚点。别留 `IMG_2024.jpg`、`Cache_xxxx.jpg` 这类（本地文件名不必改，`file_name` 参数与上传的文件内容无关）
- **图与正文属同一套资料时，分别作为独立条目上传。** ima 没有"把图合并进既有文档"的能力（在 md 里写图片外链，不保证解析时会去抓取）→ 别指望图会出现在文档正文里，也别为此改造 md

---

## 7. 边界

- **不能**：改名 / 移动 / 删除已有条目 / 建库 / 改权限 → 引导用户去 ima 客户端操作
- 司内版（`ima-mcp-oa`）与个人版是两个独立连接器；**只有一个在线时不要反问用户选哪一边**
- 本技能只覆盖"写入"。查询 / 检索 / 读正文 / 批量导入链接的用法见连接器技能 `ima-mcp`
