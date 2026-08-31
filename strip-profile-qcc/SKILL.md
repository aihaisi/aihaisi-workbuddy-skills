> 企业画像速览 SKILL · 企查查 MCP V2.0 增强版。
> PE / VC / FA 在 LP 推介前、项目初步筛选、内部立项汇报等场景的轻量尽调工具。3 分钟生成一页纸企业画像，整合工商登记、核心风险信号、知识产权资产、V2.0 主体延续性、核心管理层概要五大板块，以结构化方式呈现企业基本面。
>
> 核心能力：
> - 基础工商核验 + 主体延续性（V2.0 新能力，qcc-history 治理稳定性回溯）
> - 核心风险标签：1 页内呈现失信 / 限高 / 被执行 / 股权冻结等关键风险信号
> - 知识产权资产概览 + 知产出质（V2.0 新工具）
> - 核心管理层概要：实控人 + 法代 + 核心高管姓名与简要画像
> - 融资与经营活跃度：融资记录 + 招聘活跃度 + 荣誉信息
>
> 适用场景：LP 推介前 5 分钟了解目标公司全貌 / 项目初步筛选 / 内部立项汇报 / 投资分析师快速背调 / 投资经理每日浏览池。
>
> 使用方式：/strip-profile-qcc 企业名称 [--depth quick|standard] [--format md|docx|pptx]
>
> **风险核查采用「先扫后钻」**：先通过企业风险全量扫描一次性分诊 35 项风险维度、快速定位命中项，再对命中维度深入取证——既不漏维度，也避免逐项无效查询。

**命令**：`/strip-profile-qcc` · **MCP 工具集**：`qcc-company, qcc-risk, qcc-ipr, qcc-history, qcc-executive, qcc-operation`

---

<!-- QCC_EQUITY_NUMERIC_PRECISION_V1:START -->

## 股比 / 持股 / 表决权原值纪律（全报告强制）

- 企业数据中的直接持股、总持股（含间接）、间接持股、最终受益股份、表决权等比例，必须逐字引用本次接口返回的原始字符串并保留全部小数位；接口返回 `X.XXXX%` 时，禁止改写为 `X.XX%`、禁止补零改写或四舍五入。
- 同一指标在执行摘要、一句话结论、KPI、正文、表格、图注、风险矩阵和最终结论中重复出现时，每一次必须复用同一原始字符串；禁止因“展示简洁”改变精度。
- 禁止用直接持股与总持股相减推算间接持股，禁止逐层相乘、加总或倒算；接口未单独返回间接持股时，只写“总持股（含间接）”，不得把总持股误标为间接持股。
- 法定阈值、评分权重和区间（如 UBO 识别阈值）按规则原文展示，不属于企业股比返回值，不强制补成四位小数。
<!-- QCC_EQUITY_NUMERIC_PRECISION_V1:END -->


## MCP Resource 条件读取（跨客户端兼容）

> MCP Resource 不等同于自动注入的系统上下文。本 SKILL 的 Resource 均为 `auto_read_allowed=false`，不得假设连接时自动加载或跨会话保留。

1. 每个新会话首次执行本 SKILL 时，先按标准 `resources/list` 发现，再用 `resources/read` 读取 `qcc://terminology/core`、`qcc://policy/data-discipline`、`qcc://policy/entity-anchoring`、`qcc://skill/strip-profile/tool-binding`。
2. 生成最终报告前读取 `qcc://skill/strip-profile/report-template`，严格按固定骨架填充。
3. `qcc://tools/{server}/dictionary` 只在核验当前可见工具或 Input Schema 时按当前 Server 读取，禁止一次读取六个 Server 或据此全量调用工具。
4. 同一会话、同一版本已成功读取后不重复读取；新会话重新发现。客户端不支持、未授权或读取失败时不循环重试，继续使用 A 层与本 SKILL 内联内容。
5. Resource URI、读取动作、内部工具代码和失败记录不得写入客户报告。

---

## 🔍 风险维度扫描 · 先扫后钻（统一规范 · 2026-06-08 · 对齐 A 层铁律 5-A）

> 本 SKILL 凡涉及“一次性排查 ≥ 2 个企业风险维度”（司法风险 / 失信 / 被执行 / 限高 / 经营异常 / 行政处罚 / 破产 / 担保 / 税务 等 qcc-risk 维度），**一律按“先扫后钻”执行，禁止逐个原子风险工具散弹枪式调用**（慢 / 贵 / 多为无效调用）：
>
> 1. **第 1 步 · 分诊（先扫）**：先调 `mcp__qcc-risk__get_company_risk_scan`（企业风险扫描）一次返回企业**自身** 35 项风险维度的命中计数（脱水版：有 / 无 + 条数，不含明细）。
> 2. **第 2 步 · 下钻（后钻）**：仅对 `count > 0` 的维度，调对应原子风险工具取明细（具体工具见本 SKILL 工作流 / 术语对照表）。示例：scan 显示「失信 2、被执行 1、其余 0」→ 只下钻 `mcp__qcc-risk__get_dishonest_info` + `mcp__qcc-risk__get_judgment_debtor_info`。
> 3. **`count = 0` 的维度**：直接判定“无记录”，不再调用该维度原子工具。
> 4. **明确单一维度问句**（仅查某一项，如“有没有失信”）→ 直接调对应原子工具，无需先扫（对应 A 层铁律 5-A 路由 3）。
> 5. scan 只分诊、不出明细；要明细必须下钻原子工具。风险结论只陈述“命中维度 + 计数 / 明细”客观事实，**不替客户判定“能不能合作 / 可不可开户”**。
> 6. 先扫后钻发生在**实体锚定确定唯一主体之后**；简称 / 品牌名仍须先 `mcp__qcc-company__get_company_by_query` 锁定主体，再 scan。
> 7. 可引用已上线的聚合风险扫描工具：`get_company_risk_scan`（企业自身）、`get_executive_risk_scan`（董监高个人）、`get_company_related_risk_scan`（企业关联）、`get_executive_related_risk_scan`（人关联）；关联扫描遵守**单层预警 · 禁自动下钻**；仍不得引用任何尚未上线的工具。
>
> 8. **【定性必须有下钻证据】** 对任一风险维度给出**定性判断**（如“多为原告身份 / 属正常维权”“轻微合规瑕疵”“诉讼活跃度正常”等）之前，必须已下钻该维度的明细工具、拿到支撑数据；未下钻则**只陈述 scan 计数并标注“（未取明细）”**，禁止凭 scan 计数或印象给定性。例：scan 显示「裁判文书 77」但未下钻 `mcp__qcc-risk__get_judicial_documents` → 只能写“裁判文书 77 条（未取明细）”，**不得**写“多为原告身份、属正常维权”；如需该定性，必须先下钻 `get_judicial_documents`（可按 `role` 取原告 / 被告分布）再下结论。
>
> **【关联风险先扫 · 防散弹枪 · 2026-06-27】** 凡本 SKILL 涉及"关联企业 / 关联方 / 实控人名下企业"风险排查，**先调** `mcp__qcc-risk__get_company_related_risk_scan`（企业关联 · 单锚）/ 对关键人 `mcp__qcc-executive__get_executive_related_risk_scan`（人关联 · 双锚）一次拿关联方风险面（有风险关联方 + 命中计数 · 单层预警）→ 仅对"有风险关联方"单点下钻；**禁止**先列对外投资 / 控制企业再逐个散弹枪 `get_company_risk_scan`。
>
> 📌 **year 留空拿全量 · 禁逐年循环（防 year 散弹枪 · 2026-07-01）**：立案 / 裁判文书 / 开庭公告 / 法院公告等带 `year` 过滤参数的诉讼类工具，**取全量时 `year` 一律留空——接口在 year 缺省时即一次返回全部年份**；**严禁为“覆盖多年”而逐年（2024、2023 … 直至成立年）循环调用同一工具**（实测曾逐年一直调到 1976、单次运行 60+ 次冗余调用）。需要按年做趋势分桶时，基于“留空一次拿回的全量列表”在报告侧自行分桶；`role` / `notice_type` 等其他过滤参数同理，取全量时留空；仅当明确限定某一年 / 区间时才传 `year`。qcc-history / qcc-executive 的同名历史 / 个人诉讼工具同理，不逐年循环。

---


## 📖 QCC MCP 术语对照表（强制工具映射）

> **使用约定**：本表列出 SKILL 内业务简写与企查查 MCP 工具的精确映射。AI 执行本 SKILL 时遇到下表"业务简写"列的词汇，**必须调用对应"MCP 工具"列**，禁止使用 web search 或自由文本推测替代。完整规范见 [QCC-MCP-TERMINOLOGY.md](../../QCC-MCP-TERMINOLOGY.md)。

| 业务简写 | 规范全名 | 企查查 MCP 工具 |
| --- | --- | --- |
| 失信 | 失信被执行人 | `mcp__qcc-risk__get_dishonest_info` |
| 被执行 | 被执行人 / 判决债务人 | `mcp__qcc-risk__get_judgment_debtor_info` |
| 限高 | 限制高消费 | `mcp__qcc-risk__get_high_consumption_restriction` |
| 限出境 / 限境 | 限制出境 | `mcp__qcc-risk__get_exit_restriction` |
| 终本 | 终结本次执行案件 | `mcp__qcc-risk__get_terminated_cases` |
| 破产 / 重整 | 破产重整 | `mcp__qcc-risk__get_bankruptcy_reorganization` |
| 经营异常 | 经营异常 | `mcp__qcc-risk__get_business_exception` |
| 严重违法 | 严重违法失信 | `mcp__qcc-risk__get_serious_violation` |
| 行政处罚 / 重大处罚 | 行政处罚 | `mcp__qcc-risk__get_administrative_penalty` |
| 股权冻结 | 股权冻结 | `mcp__qcc-risk__get_equity_freeze` |
| 股权出质 | 股权出质 | `mcp__qcc-risk__get_equity_pledge_info` |
| 欠税 | 欠税公告 | `mcp__qcc-risk__get_tax_arrears_notice` |
| 税务异常 / 税务违法 | 税务异常 / 税收违法 | `mcp__qcc-risk__get_tax_abnormal` / `mcp__qcc-risk__get_tax_violation` |
| 受益所有人 / UBO | 受益所有人 | `mcp__qcc-company__get_beneficial_owners` |
| 实控人 / 实际控制人 | 实际控制人 | `mcp__qcc-company__get_actual_controller` |
| 主要人员 / 董监高 | 主要人员 | `mcp__qcc-company__get_key_personnel` |
| 抽查检查 / 双随机 | 双随机抽查 | `mcp__qcc-operation__get_random_check` |
| 吊销 | （登记状态字段判断）| 调 `mcp__qcc-company__get_company_registration_info` 取"登记状态" |
| 资不抵债 | （资产负债率字段判断）| 调 `mcp__qcc-company__get_financial_data` 判断负债率 > 100% |

---

# 企业画像速览 · 企查查 MCP V2.0 增强版

## SKILL 定位

本 SKILL 服务于投资类场景的"快速筛查"——在 IC Memo 之前、DD 之前，投资团队常常需要对大量项目做"5 分钟扫一眼"式筛查。企业画像速览就是这种场景的标准工具：输入公司名，5 分钟内输出一张结构化的"公司身份卡"，让投资经理快速判断"这家公司是否值得进入 DD 阶段"。

V2.0 相对 V1.0 的升级在两个方面：
- **主体延续性维度**（qcc-history）—— 画像表上增加"治理稳定性"一行，识别"频繁变更"的高风险企业
- **核心管理层概要**（qcc-executive）—— 画像表上增加"创始人速览"一行，3 秒内判断实控人是否清洁

## MCP 依赖与配置

必选：
- `qcc-company`（企业基座）—— 工商基础 + 股东 + 实控人
- `qcc-risk`（风控大脑）—— 核心风险标签

强烈建议：
- `qcc-history`（历史存档）—— 主体延续性
- `qcc-executive`（人员画像）—— 核心管理层快扫

可选：
- `qcc-ipr`（知产引擎）—— IP 资产概览
- `qcc-operation`（经营罗盘）—— 融资、荣誉、招聘活跃度

## 通用执行原则

**第一，轻量快速是第一目标。** 画像速览不是 IC Memo。要在 1-2 页（500-800 字）内让读者快速抓到"主体真实性 + 核心风险 + 关键人物 + IP 数量 + 融资轮次"五项核心信息，**不做深度推演**。

**第二，信息密度优先于文字包装。** 推荐用表格而非段落。每个指标一行，最多一句话解读。

**第三，主体延续性是新加入的结构化维度。** 治理稳定 / 不稳定 / 高度不稳定三档标签，不做深入分析——如读者想深入，进入下一层的 IC Memo / KYB。

**第四，创始人画像做"轻扫"而非"深扫"。** 只看 4 项核心红线（失信 / 限高 / 被执行 / 限出境）是否触发，不做完整 18 维扫描。

**第五，明确告知"可用于初步筛查不可用于投资决策"。** 画像速览定位决定了其深度——如进入正式投资决策阶段，必须升级到 IC Memo + KYB + 专项 DD 工作。

## 工作流

### 维度一：基础工商 × 主体延续性（V2.0 加强）

工具链：
- `mcp__qcc-company__get_company_registration_info`
- `mcp__qcc-company__get_shareholder_info`
- `mcp__qcc-company__get_actual_controller`
- `mcp__qcc-history__get_historical_legal_rep` / `get_historical_registration`

**速览输出**：
- 全称 + USCC
- 成立日期 + 注册资本（实缴）
- 登记状态
- 所属地区 + 行业
- 实控人 + 持股比例
- **治理稳定性标签**（V2.0 新）：稳定 / 不稳定 / 高度不稳定

### 维度二：核心风险标签

工具链：
- `mcp__qcc-risk__get_dishonest_info` / `get_judgment_debtor_info` / `get_high_consumption_restriction` / `get_equity_freeze` / `get_business_exception` / `get_tax_arrears_notice` / `get_administrative_penalty`

**速览输出 6 色标签**：
- 🟢 失信 0
- 🟢 被执行 0
- 🟢 限高 0
- 🟢 股权冻结 0
- 🟢 经营异常 0
- 🟡 行政处罚 N（有则列数量）

### 维度三：知识产权资产概览

工具链：
- `mcp__qcc-ipr__get_patent_info`（总数）
- `mcp__qcc-ipr__get_trademark_info`（总数）
- `mcp__qcc-ipr__get_software_copyright_info`（总数）
- `mcp__qcc-ipr__get_ipr_pledge`（V2.0 新工具，是否有知产出质）

**速览输出**：
- 专利 N 件 / 商标 N 件 / 软著 N 件 / 域名 N 个
- 知产出质：有 / 无（V2.0 新指标）

### 维度四：核心管理层速览（V2.0 新能力）

**【个人风险先扫后钻 · 2026-06-08 · 对齐 A 层铁律 5 个人维度】** 对每位目标人（法代/实控人/董监高），**先调 `mcp__qcc-executive__get_executive_risk_scan`（searchKey=企业完整名/USCC + personName=姓名，双锚定）一次返回其 18 项个人风险维度命中计数 → 仅对 count>0 维度下钻下列对应 `get_executive_*` 原子工具取明细**；count=0 跳过。❌ 禁止不先扫、逐个散弹枪调个人风险原子。单人工具：多人则逐人各扫一次，不对全体董监高自动循环。
对实控人 + 法代做 4 项红线快扫：
- `mcp__qcc-executive__get_executive_dishonest`
- `mcp__qcc-executive__get_executive_high_consumption_ban`
- `mcp__qcc-executive__get_executive_judgment_debtor`
- `mcp__qcc-executive__get_executive_exit_restriction`

**速览输出**：
- 实控人姓名 + 4 项红线扫描结果（全绿 / 有红）
- 法代姓名 + 红线扫描结果
- 如两人非同一人，各扫一遍

### 维度五：融资与经营活跃度

工具链：
- `mcp__qcc-operation__get_financing_records`（融资历史）
- `mcp__qcc-operation__get_recruitment_info`（招聘活跃度）
- `mcp__qcc-operation__get_honor_info`（荣誉）

**速览输出**：
- 最近融资轮次 + 金额 + 时间 + 投资方
- 招聘活跃度（近 3 月职位数）
- 荣誉：高新技术企业 / 专精特新 / 国家级 / 省级 等关键标签

## 报告输出格式（严格填空骨架 · 模型只填值、不造结构）

> **使用约定**：以下是企业画像速览的**完整骨架**——标题层级、表头与列、免责声明**全部固定**，模型只把 `{}` 占位替换为工具返回值，**禁止新增 / 删除章节、禁止改表列、禁止虚构接口未返回的列或分类**。企业画像偏「速览」，骨架精简、信息密度优先，每个指标一行、最多一句解读，**不做深度推演**。各章数据来源见每节标注（业务语言，报告内不写工具代码名）。
> **填写纪律（务必遵守，对齐本 SKILL 已有铁律）**：
> ① **实控人 / 股比数字全篇逐字引用**：凡「直接持股 / 总持股 / 最终受益股份 / 表决权」在**执行摘要、一句话画像、关键画像表、正文、表格或结论**中出现，每一次都必须复用接口返回的同一原始字符串并保留全部小数位（如 直接 35.4938% / 总持股 47.6955% / **表决权 53.0011%**）；**禁止写成 35.49% / 47.70% / 53.00%，禁止以展示简洁为由缩位或四舍五入**。同时禁自行把各层持股比例相乘重构穿透路径百分比、禁臆测中间层、禁把聚合值与自算分项的差额圆场为「四舍五入」；股东持股比例 / 持股数逐字引用，不加总、不重算。
> ② **风险先扫后钻**：§四风险面先调企业风险扫描分诊，仅对命中维度下钻取明细；**未下钻则只写计数 +「（未取明细）」，禁凭计数定性**；只陈述「命中维度 + 计数 / 明细」客观事实，**不替读者判定能否投资 / 合作**。
> ③ **创始人轻扫**：§三实控人 / 法代仅 4 项红线（失信 / 限高 / 被执行 / 限出境）先扫后钻，不做完整 18 维深扫。
> ④ **关联单层预警**：如涉关联方风险，先扫一次拿关联面、**不对返回的关联方再自动逐个穿透**。
> ⑤ **各维计数逐字引用**：专利 / 商标 / 软著 / 荣誉 / 融资轮次等数量一律照抄接口返回值，**禁跨类目加总、禁估算**；未返回写「未披露 / 本次未核验」。
> ⑥ **治理稳定性仅三档**：稳定 / 不稳定 / 高度不稳定，速览不展开分析。

```markdown
# 企业画像速览

## {企业完整登记名}

**目标企业：** {完整登记名}
**统一社会信用代码：** {18 位}
**法定代表人 / 实控人：** {姓名}
**所属行业：** {国民经济行业大类}
**报告生成：** YYYY-MM-DD HH:MM:SS
**审计留档编号：** SKILL-CP-{统一社会信用代码}-{YYYYMMDD}
**整体定位：** {一句话画像 · 用于初步筛查，不构成投资决策依据}

---

## 执行摘要

> **一句话画像：** {成立年份、注册地、实控人、注册资本、主营、核心风险面、关键资本状态，一段话讲清「这家公司是否值得进入 DD」；如写持股或表决权，必须从 §3.1 逐字复制完整原值，禁止缩位或四舍五入}

| 关键画像 | 内容 |
| --- | --- |
| 公司年龄 | {N 年 · YYYY-MM-DD 成立} |
| 主营业务 | {} |
| 实控人 | {姓名（直接 {35.4938%} / 总持股 {47.6955%} / 表决权 {53.0011%}）} |
| 登记状态 | {存续 / 在业 / 吊销 / 注销} |
| 治理稳定性 | {稳定 / 不稳定 / 高度不稳定} |
| 核心风险面 | {命中 N 维 / 全绿无记录} |
| 知产资产 | {专利 N / 商标 N / 软著 N} |
| 资本市场状态 | {融资 N 轮 / 上市 / 申报中 / 无} |

---

## 一、基本工商信息

| 项目 | 内容 |
| --- | --- |
| 企业全称 | {} |
| 统一社会信用代码 | {} |
| 法定代表人 | {} |
| 成立日期 | YYYY-MM-DD |
| 注册资本 | {} 万元（{实缴 / 认缴}） |
| 注册地 | {完整地址} |
| 所属行业 | {} |
| 登记状态 | {存续 / 在业 / 吊销 / 注销} |
| 治理稳定性 | {稳定 / 不稳定 / 高度不稳定} |

> 本节数据来自企查查工商登记数据 + 历史存档数据（主体延续性）。治理稳定性仅三档标签，不展开分析。

---

## 二、股权结构

| # | 股东名称 | 持股比例 | 持股数 (股) | 股东类型 |
| --- | --- | --- | --- | --- |
| 1 | {} | {%} | {} | {自然人 / 企业法人 / 有限合伙} |


---

## 三、实际控制人与创始人速览

### 3.1 实际控制人

| 实际控制人 | 直接持股 | 总持股（含间接） | 表决权 |
| --- | --- | --- | --- |
| {} | {35.4938%} | {47.6955%} | {53.0011%} |


### 3.2 创始人红线速扫（先扫后钻 · 4 项红线）

| 关键人 | 身份 | 失信 | 限高 | 被执行 | 限出境 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| {} | {实控人 / 法代} | {无 / N 条} | {无 / N 条} | {无 / N 条} | {无 / N 条} | {全绿 / 有红} |

> 本节数据来自企查查人员风险信息。仅 4 项红线轻扫；任一红线触发即标注「有红」，不做完整 18 维深扫。

---

## 四、核心风险面（先扫后钻 · 企业自身）

### 4.1 风险标签速览

| 风险维度 | 命中 |
| --- | --- |
| 失信 | {无 / N 条} |
| 被执行 | {无 / N 条} |
| 限高 | {无 / N 条} |
| 股权冻结 | {无 / N 条} |
| 经营异常 | {无 / N 条} |
| 行政处罚 | {无 / N 条} |

> 本节数据来自企查查风险信息数据。先调企业风险扫描分诊，仅对命中维度下钻；未下钻的维度写「N 条（未取明细）」，不凭计数定性。

### 4.2 命中维度简述（仅 count>0）

{对命中维度一句话客观陈述命中条数 / 关键事实；只陈述客观事实，不替读者判定能否投资 / 合作}

---

## 五、知识产权资产

| 类别 | 数量 |
| --- | --- |
| 专利 | {N 件 / 未披露} |
| 商标 | {N 件 / 未披露} |
| 软件著作权 | {N 件 / 未披露} |
| 知产出质 | {无 / 有} |


---

## 六、经营概况（融资与活跃度 · --depth standard）

| 指标 | 内容 |
| --- | --- |
| 最近融资 | {第 N 轮 · {金额} · YYYY-MM} |
| 主要投资方 | {} |
| 招聘活跃度 | {近 3 月 N 个职位 / 未披露} |
| 关键荣誉 | {高新技术企业 / 专精特新 / 独角兽 等 · 或无} |


---

## 七、一句话结论

> {基于上述已填入数据生成的一句话画像，仅供初步筛查；明确「不可用于投资决策，正式决策须升级到 IC Memo + KYB + 专项 DD」}

---

## 数据来源与免责声明

**数据来源：** 本报告全部数据由企查查 MCP 实时返回（上游为国家市场监督管理总局及省 / 市市场监管、数据局公示数据），采集时间 YYYY-MM-DD HH:MM:SS。

**免责声明：**
1. 本报告为「企业画像速览」，仅供初步筛查 / 立项前浏览 / LP 推介前准备场景，**不得作为投资决策依据**。
2. 画像速览不做深度推演与风险定性；如进入正式投资决策阶段，须升级到 IC Memo + KYB + 专项 DD 的完整尽调流程。
3. 数据为查询时点公开记录快照，未披露的代持、协议控制、一致行动安排等无法穿透识别。
```

> **章节 ↔ 工具绑定**：执行摘要←全维度汇总；§一←`get_company_registration_info` + qcc-history（`get_historical_legal_rep` / `get_historical_registration` 判治理稳定性）；§二←`get_shareholder_info`；§三←`get_actual_controller`（聚合值逐字引用）+ 实控人 / 法代个人风险先扫（`get_executive_risk_scan`）后钻 4 红线原子（`get_executive_dishonest` / `get_executive_high_consumption_ban` / `get_executive_judgment_debtor` / `get_executive_exit_restriction`）；§四←`get_company_risk_scan` 先扫 + 命中维度原子下钻；§五←`get_patent_info` / `get_trademark_info` / `get_software_copyright_info` / `get_ipr_pledge`；§六←`get_financing_records` / `get_recruitment_info` / `get_honor_info`。

## 参数

- `--depth <quick|standard>`：quick（默认）仅 4 红线 + 基础工商；standard 涵盖所有维度
- `--format md|docx|pptx`：输出格式，默认 md；pptx 为一页 PPT 速览模板

## 边界与免责

画像速览仅供"初步筛查 / 立项前浏览 / LP 推介前准备"场景。**不得**作为投资决策依据——任何投资决策应基于 IC Memo + KYB + 专项 DD 的完整尽调流程。

---

**SKILL 版本**：v2.0（MCP V2.0 升级版）
**适配 MCP 版本**：146 工具 / 6 Server 全量版
**所需 Server**：qcc-company（必选）、qcc-risk（必选）、qcc-history（建议）、qcc-executive（建议）、qcc-ipr（可选）、qcc-operation（可选）

---

## 报告输出纪律（内部规则 · 严禁出现在最终报告中）

1. **一律业务语言**：报告正文、备注、数据来源说明中不得出现 MCP 工具代码名（`get_xxx` / `mcp__qcc-xxx`）、server 名（qcc-company 等）、schema / manifest / 字段名等技术词；数据来源统一用业务表述（如"企查查工商登记数据 / 企查查风险信息数据 / 企查查财务数据"）。"企查查 MCP"作为对外产品名仅允许出现在「数据来源」固定句式中。
2. **禁止内部用语**：SKILL / SKILL.md / V1.0 / V2.0 / 增强版 / 新能力 / 维度编号 / 评级引擎规则等开发概念不得出现在报告中；「Decision Pack」一律写「决策摘要」。
3. **禁止执行过程独白**：不输出"我将按照…/第一步获取…/已锁定主体/接下来…"等过程描述，直接输出报告正文。
4. **禁止运行时状态泄漏**：积分余额、配额、调用受限、超时重试、在线体验版本等不得写入报告；某维度数据未获取时统一写"本次未核验 / 未发现公开记录"。
5. **数据零推算、零缩位**：只引用工具返回的原始数字；禁止自行加总、相减、相乘、加权、估算或四舍五入（含"推算 / 估算值"字样）。同一股比 / 持股 / 最终受益股份 / 表决权在执行摘要、一句话画像、KPI、正文、表格、结论中重复出现时，必须复用同一原始字符串并保留全部小数位；工具未返回的字段留空或写"未披露"，不得编造。
6. 本节及全部内部执行规则只约束 AI 行为，严禁以任何形式抄入报告。
<!-- QCC_ONLINE_EXPERIENCE_PLAN_V1
{"version":1,"steps":[{"id":"profile-identify","label":"识别为企业画像速览，锁定目标主体","cap":"主体识别","capabilityKeys":["entity"],"completeOn":"route_match"},{"id":"profile-registration","label":"汇总工商登记与股权结构","cap":"工商与股权数据","capabilityKeys":["registration","ownership","history"]},{"id":"profile-risk","label":"提取核心风险信号","cap":"风险数据","capabilityKeys":["risk","management"]},{"id":"profile-ipr","label":"盘点知识产权资产","cap":"知识产权数据","capabilityKeys":["ipr","operation"]},{"id":"profile-report","label":"生成一页纸企业画像","cap":"画像结论","completion":true}]}
QCC_ONLINE_EXPERIENCE_PLAN_V1_END -->
