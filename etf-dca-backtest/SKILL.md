---
name: etf-dca-backtest
description: 对 A 股 ETF 做真实数据回测并产出 HTML 研报——实测折溢价、比较"每月定投 vs 一次性买入"、滚动窗口胜率检验、佣金敏感性。当用户要求"回测某只 ETF""定投和一次性哪个划算""算算 ETF 折溢价""跑个定投模拟""帮我模拟十年定投"时使用。
agent_created: true
---

# ETF 定投 vs 一次性 回测

## 一、数据获取（westock MCP）

| 需要什么 | 工具 | 参数要点 |
|---|---|---|
| 长周期价格 | `mcp__westock-mcp__data_kline` | **`period=month` 一次可取全约 121 条（10 年）**——这是首选 |
| 日线（算折溢价用） | 同上 | `period=day` **单次上限约 250 条**，10 年要分 10 段，上下文成本极高，非必要不用 |
| 日度净值 | `mcp__westock-mcp__data_etf` | `aspect=nav` + `start`/`end` |
| 最新价 / 规模 | `mcp__westock-mcp__data_quote` | 支持多码逗号分隔 |
| 代码确认 | `mcp__westock-mcp__data_search` | `type=etf` |

**关键技巧**：月线的 `open` = **当月首个交易日开盘价**，直接用作"每月定投买入价"，语义贴近实操（月初发工资买入）；`last` = 月末收盘，用作月度估值点。

## 二、回测口径（必须写进交付物，否则结论不可信）

- 各方案**总投入必须相同**（如统一 12 万），否则不可比
- 定投买入价 = 每月首日开盘价（前复权）；期末统一按最新收盘价估值
- **一次性用几何年化，定投用月度 IRR**（二分法求根）。两者口径不同，**不能横向直接比较**，只用于各自衡量资金效率——这一点务必在交付物里说明
- 前复权价格**已包含分红再投资**；管理费/托管费已在净值中计提，**不重复扣除**（费率只作为背景信息引用）
- 佣金按单边万 2.5（买入端）；ETF 免印花税

## 三、必做的三件事（少一个结论就会误导人）

1. **滚动窗口测试**：遍历每一个可能的起点（每个起点都是完整窗口），统计定投的"终值胜率"与"年化胜率"。
   单一起点的结论是**幸存者偏差**——同一只 ETF 把起点从 2016-09 换成 2021-09，胜负直接反转。这是整份报告最有价值的部分。
2. **佣金最低 5 元单独测算**：小额定投（1000 元/期）遇到"每笔最低 5 元"相当于 **0.5% 的隐性费率**，比管理费高 2 倍以上，十年吞掉几百元。这是最容易被漏掉的成本项。
3. **最大浮亏 vs 最大回撤**：定投算"市值相对累计投入的最大浮亏"，一次性算"持仓市值的最大回撤"。这是定投唯一稳定占优的维度，也是最有解释力的指标。

## 四、交付流程

1. **先写模板 HTML**（含 `/*__DATA__*/` 和 `<!--__TBL_XXX__-->` 占位符），**再用 Python 从 results.json 注入数据**——避免手抄上百个数字出错
2. **JS 语法自检**：抽出内联 `<script>` 体 → `node --check`，**exit 0 才算完成**。ECharts option 括号失配会让整页图表全废
3. **实际渲染验证**：`msedge --headless=new --disable-gpu --screenshot=out.png --window-size=1150,4900 --virtual-time-budget=10000 "file:///..."`，然后**看图确认**，不能只凭"文件已生成"
4. HTML 规范见 `wb-finance-skill` 的 `references/html-report-style.md`：浅底深字、首屏结论先行、A 股红涨绿跌、图/表可切换

## 五、本机环境坑（Windows，实测）

| 坑 | 表现 | 对策 |
|---|---|---|
| PowerShell 工具不回传 stdout | exit 0 但输出为空 | 脚本**自己写文件**，再用 Read 读回 |
| Bash 工具 PATH 损坏 | `dirname`/`ls`/`mkdir` command not found，exit 127 | 一律用 PowerShell |
| 同一文件并行 Edit 静默丢失 | 报 success 但未落盘 | 多处修改一律用 **MultiEdit**，改完 Grep 复核 |
| `Remove-Item` 被沙箱拒 | exit 1，文件删不掉 | 产物直接生成在独立子目录，别指望事后清理 |
| 中文文件名回显乱码 | PowerShell 日志显示 `鍥炴祴` | 仅日志乱码，**文件内容正常**，别被误导 |

## 六、参考实现（可直接改标的重用）

`<工作区>/etf-backtest/`：

- `backtest.py` — 回测主逻辑：折溢价统计、lump_sum()、dca()、irr_monthly() 二分法、roll_test() 滚动窗口
- `report_template.html` — 研报模板（ECharts 折溢价柱状 / 价格+成本线 / 双策略曲线 / 滚动胜率）
- `gen_report.py` — 读 results.json 注入模板，产出 HTML，并自动抽 JS 供 node --check

替换 `MONTHLY` 数据数组与 `PREMIUM` 数组即可跑其他标的。
