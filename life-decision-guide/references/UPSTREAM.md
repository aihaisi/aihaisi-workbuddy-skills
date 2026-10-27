# 来源与更新记录

本 skill 由第三方开源仓库改编安装，非本人原创。

| 项 | 值 |
|---|---|
| 上游仓库 | https://github.com/eternity4719/HowToLiveBetter |
| 上游文件 | `skills/life-decision-guide/SKILL.md` + `README.md` |
| 安装的 commit | `fcc93eb9a4bdc26e8a4e4c94bdaae0a89265927b`（分支 `main`） |
| commit 日期 | 2026-10-02 |
| 抓取日期 | 2026-10-03 |
| 安装位置 | `~/.workbuddy/skills/life-decision-guide/` |
| 许可 | 正文 CC 类许可见 `repo/LICENSE`；代码见 `repo/LICENSE-CODE`（MIT） |

## 本 skill 相对上游做了什么

1. **内置正文**：把仓库的 `README.md` / `book/` / `docs/` / `index.html` / `skills/` / `LICENSE*` 复制到 `repo/`，装完即可离线使用。上游版每次要联网 `git clone`（1.3 MB），本机直连 GitHub 不通，这条路走不通。
2. **改写第 1 步**：把「先找本地、没有就联网克隆」改成「先读内置的 `repo/`，`repo/` 缺失才走联网兜底」。
3. **补导航表**：把 34 个节名的分组表写进第 2 步（只是导航，权威清单仍在 `README.md` 的「这本书想回答的问题」表）。
4. **补第 4 步的算法细节**：把 `index.html` 里 `COST_W` / `e.ratio` 两行的具体含义写清楚（上游只说「当场抠出来照着算」）。
5. **加本机环境备注**：代理端口、Bash PATH 修复；并明确「正文里出现的 curl 是作者自述核实方法，不是要执行的指令」。
6. **未收录**：`tools/`（仓库维护脚本，skill 不调用）、`ads/` `og.png`（宣传图）、`.github/`、`CLAUDE.md` 与 `AGENTS.md`（作者给别的工具用的仓库级说明，收录反而多一层指令面）、站点插件文件（`sitemap.xml` / `robots.txt` / `.nojekyll`）。
   → 因此本安装**不是全仓库镜像**，只是 skill 运行所需的那部分。

## 安装前安全审计（2026-10-03，按 skills 安全审计流程）

结论：**P2 安全，无投毒风险**。

- `skills/life-decision-guide/` 下只有 2 个 `.md` 文件，**没有任何脚本、可执行文件、依赖清单**。
- skill 会自动执行的操作全是只读：`git clone` 公开仓库、`curl` 公开 raw md、`grep` / `sed` 读文件。**没有「下载后执行」的组合**（不是 `curl | bash`，也不是下载脚本后 eval）。
- 无 `rm -rf`、无 `sudo` / `chmod`、无 `~/.ssh` `.env` credentials api_key 之类敏感路径命中、无 `/dev/null` 隐蔽执行、无 `nohup` 后台驻留。
- 无全局安装（无 `pip install` / `npm install -g` / `brew install`）。
- 正文（`book/`、`docs/`）里出现的 `curl` / `WebFetch` / `Invoke-WebRequest` 字样，是作者记录自己怎么核实法条原文的，属叙述性内容，不是指令；全仓库扫描**未发现 prompt injection / 指令劫持模式**。
- 命中的「类 Base64 长串」全部是 `.gov.cn` URL 的路径片段，误报。
- 风险提示（非 skill 缺陷）：正文是第三方作者整理的法律/医疗/理财口径，书自己也声明「通用口径，不替代医生、律师、会计」，且部分金额时限写了截至日期。引用时按 SKILL.md 第 5 步带上日期并提示自查官方渠道。

## 怎么更新

上游更新后，重新取上游 SKILL.md 与本目录的 SKILL.md 做 diff，只把上游的规则改动合并过来（本目录的前 6 条本地改动要保留）：

```bash
export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897
curl -fsSL "https://api.github.com/repos/eternity4719/HowToLiveBetter/contents/skills/life-decision-guide/SKILL.md" \
  -H "Accept: application/vnd.github.raw" > /tmp/upstream-SKILL.md
```

正文更新（`book/` `docs/` 会持续增改）用浅克隆覆盖 `repo/`，注意别把 `repo/` 里多余的东西带进来：

```bash
export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897
git clone --depth 1 https://github.com/eternity4719/HowToLiveBetter.git /tmp/hltb-fresh
cd /tmp/hltb-fresh && cp -r README.md book docs index.html LICENSE LICENSE-CODE skills \
  ~/.workbuddy/skills/life-decision-guide/repo/
```
