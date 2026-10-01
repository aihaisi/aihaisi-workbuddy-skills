---
name: wechat-article-search
description: "搜索微信公众号文章技能。通过微信搜索获取文章列表，覆盖科技/AI、社会热点、财经、教育、职场等各类中文资讯；可按关键词检索并返回标题、概要、发布时间、来源公众号与链接。当用户需要查找微信公众号文章、整理参考资料或快速获取文章信息时使用此技能。"
description_zh: "搜索微信公众号文章（标题、摘要、发布时间、来源账号、链接）"
description_en: "Search WeChat public account articles by keyword"
version: 0.1.1
allowed-tools: Bash,Read
metadata:
  clawdbot:
    emoji: "\U0001F50E"
    requires:
      bins:
        - node
display_name: "wechat-article-search"
display_name_en: "wechat-article-search"
visibility: "public"
---

# 微信公众号文章搜索说明

## 适用场景

- 用户说“帮我搜某个关键词的公众号文章/最近文章”
- 需要快速拿到：标题、摘要、发布时间、公众号名称、可访问链接

## 能力边界（诉求触及时首答说明）

底层是搜狗微信搜索，脚本按相关度取前 N 条（默认 10，最多 50），不是全量：

- 按相关度排序，无可用的服务端时间筛选；需要时间窗时用 `-d N` 按返回的发布时间过滤，并说明结果可能不完整。
- 无法枚举单一账号的完整发文时间线或总篇数。
- 不含阅读量、点赞等互动指标。

诉求依赖以上能力时，先跑一次检索确认可行性再告知用户，不要反复换词、改脚本注入未支持的参数，或被限流后长时间重试。

## 工作流程

脚本零第三方依赖，只需 `node`，无需 `npm install`。

1. 确认关键词与返回数量（必要时确认时间窗）。
2. 执行搜索命令：

```bash
node scripts/search_wechat.js "关键词"
```

## 参数说明

- `query`：搜索关键词（必填）
- `-n, --num`：返回数量（默认 10，最大 50）
- `-d, --days`：仅保留最近 N 天内、有可解析发布时间的文章（客户端过滤，无发布时间的结果会被跳过）
- `-o, --output`：输出 JSON 文件路径（可选）
- `-r, --resolve-url`：尝试把中间链接解析成微信文章真实链接（会额外请求每条结果）

示例：

```bash
node scripts/search_wechat.js "人工智能" -n 15
node scripts/search_wechat.js "人工智能" -n 20 -d 365
node scripts/search_wechat.js "人工智能" -n 20 -o result.json
node scripts/search_wechat.js "人工智能" -n 5 -r
```

## 输出字段（文章对象）
文章标题、文章地址、文章概要、发布时间、来源公众号名称

## 常见问题处理

- 结果为空：换更通用、更少特殊字符的关键词重试一次；仍为空则如实告知，不外推。
- 触发反爬/限流（返回极短空页、连续 total=0）：停止连续请求，告知用户稍后再试。
- 解析真实 URL 失败：这是常态（反爬限制）；可提示用户用浏览器打开中间链接

## 注意事项

- 本工具仅用于学习和研究目的，请勿用于商业用途或大规模爬取。
- 使用本工具时请遵守相关网站的使用条款和规定。
- 过度使用可能导致 IP 被封禁，请谨慎使用。
