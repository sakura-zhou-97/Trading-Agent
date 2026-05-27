# Trading-Agent Context

This context defines the domain language for the AI stock screening and trading-research workflow. It exists so product docs, technical design, and implementation use the same terms for candidate discovery, opportunity ranking, trade planning, and review.

## Language

**候选股**:
A stock that passed the stock universe filter and hard-rule coarse screen, entering the daily candidate pool.
_Avoid_: 重点机会, 交易计划标的, 可买股票

**重点机会**:
An S/A-ranked stock after comprehensive opportunity scoring.
_Avoid_: 候选股, 可买股票

**交易计划标的**:
A重点机会 with conditional entry, stop-loss, position, and invalidation rules.
_Avoid_: 候选股, 买入标的, 推荐股票

**AI 分析**:
Structured model output that explains catalysts, evidence, risks, overheating, and information gaps for a candidate or opportunity.
_Avoid_: AI 选股, AI 买卖建议

**仓位上限**:
The maximum position size allowed by deterministic risk-control rules for a trade-plan target.
_Avoid_: AI 仓位, 推荐仓位

**防守市场**:
A market state where the market score is below the V1 trading threshold and no new position plan may be generated.
_Avoid_: 弱市但可轻仓, AI 高分例外

**板块语境**:
The grouping context used by the system to judge market mainlines and stock resonance.
_Avoid_: 行业字段, 题材标签, 概念板块

**每日报告**:
The daily product entry point that summarizes market state, sector context, key opportunities, trade plans, risks, and review hooks.
_Avoid_: A/B/C 文件汇总, 调试报告

**日报数据契约**:
The stable JSON representation of the daily report used by dashboards, rich views, and review workflows.
_Avoid_: HTML 源数据, Markdown 源数据

**富展示报告**:
A future optional HTML rendering generated from the daily report data contract for richer visual review, outside V1 delivery.
_Avoid_: V1 交付项, 稳定数据契约, 唯一主报告

**交易计划**:
A conditional research plan for manual observation, not an execution command or investment recommendation.
_Avoid_: 买入建议, 自动执行清单, 投资建议

**计划前向验证**:
Forward validation of candidates, key opportunities, and trade-plan targets against future market outcomes without assuming actual user execution.
_Avoid_: 交易执行复盘, 实盘盈亏复盘

**交易执行复盘**:
Review of actual user trades, fills, position sizes, stop-loss execution, and non-plan trades.
_Avoid_: 计划前向验证

**买点触发**:
An entry condition from a trade plan observed in later daily bar data.
_Avoid_: 盘中实时触发, 用户已买入

**评分画像**:
The named set of opportunity-scoring weights and rules used for a run.
_Avoid_: 临时权重, 隐式调参

**明日观察清单**:
The daily report section listing key opportunities to manually watch on the next trading day.
_Avoid_: 观察名单管理, 用户自选池

**观察名单管理**:
User-managed cross-day watchlist editing, tagging, notes, and removals.
_Avoid_: 明日观察清单

**文件产物**:
The JSON and Markdown outputs written under the results directory that serve as V1 persistence and audit artifacts.
_Avoid_: 数据库记录, 临时日志

**补丁建议**:
A proposed rule or prompt change generated from review evidence and awaiting human decision.
_Avoid_: 自动调参, 自动优化

**已采纳补丁**:
A patch proposal explicitly accepted by the user and eligible for application.
_Avoid_: 系统自动采纳

**机会评分**:
The S/A/B/C ranking score used by the batch A-share screening workflow.
_Avoid_: 单票多智能体评级, BUY/HOLD/SELL

**单票深度研究**:
The multi-agent analysis workflow for one selected stock.
_Avoid_: 批量机会评分

**盘后系统**:
A workflow that runs from daily or after-market data and produces next-day observation plans.
_Avoid_: 实时盘中提醒, 自动盯盘

## Relationships

- A **候选股** may become a **重点机会** after opportunity scoring.
- A **重点机会** may become a **交易计划标的** when a conditional trade plan is generated.
- A **候选股** is not automatically a **交易计划标的**.
- **AI 分析** may influence opportunity ranking and risk warnings, but it must not directly increase the **仓位上限**.
- **仓位上限** is determined by risk-control rules, not by AI confidence alone.
- In a **防守市场**, every **交易计划标的** must have a zero **仓位上限** and a watch or blocked plan status.
- **板块语境** is a product-level concept; V1 uses the stock industry field as the default adapter, while later adapters may use concepts, industry taxonomies, or custom theme maps.
- V1 records the **板块语境** adapter as `industry`; additional adapters are future extensions, not V1 scope.
- The **日报数据契约** is the source of truth for the **每日报告**.
- Markdown is the default human-readable **每日报告** in V1; a **富展示报告** is outside V1 delivery.
- A **交易计划** must be conditional and must respect market state, **板块语境**, **仓位上限**, and invalidation rules.
- A **交易计划** may be used for manual observation, but it is not proof that a trade was executed.
- **计划前向验证** can evaluate future returns, drawdowns, grade effectiveness, risk scoring, and whether planned entry conditions were observed.
- **交易执行复盘** requires explicit trade logs or manual execution records and is outside V1.
- A **买点触发** in V1 is a daily-bar observation and must not be interpreted as proof of actual user execution.
- V1 uses the default **评分画像** as a product rule; experimental scoring must be named and recorded in report and review outputs.
- Forward validation must not mix results from different **评分画像** values.
- V1 generates a **明日观察清单** in the daily report, but **观察名单管理** is outside V1.
- V1 persists analysis, reports, plans, and review outputs as **文件产物**; database-backed storage is outside V1.
- A **补丁建议** must start as proposed and must not change rules or prompts until it becomes an **已采纳补丁**.
- **补丁建议** must not automatically change the default **评分画像** or hard risk controls.
- **机会评分** belongs to the batch A-share screening workflow in V1.
- **单票深度研究** may be used for deeper review of a key opportunity, but it does not share the V1 **机会评分** contract.
- V1 is a **盘后系统**; real-time intraday alerts, streaming data, and push notifications are outside V1.

## Example dialogue

> **Dev:** "Should every **候选股** appear in tomorrow's trade plan?"
> **Domain expert:** "No. Only a **重点机会** with complete conditional entry, stop-loss, position, and invalidation rules becomes a **交易计划标的**."

> **Dev:** "If **AI 分析** gives a very high catalyst score, can we increase the **仓位上限**?"
> **Domain expert:** "No. AI can improve ranking or surface risks, but the **仓位上限** comes from deterministic risk-control rules."

> **Dev:** "Can an S-ranked **重点机会** receive a small starter position in a **防守市场**?"
> **Domain expert:** "No. It can remain on the watch list, but no new position plan is generated in a **防守市场**."

> **Dev:** "Does **板块语境** mean the raw industry field forever?"
> **Domain expert:** "No. V1 uses industry as the default adapter, but callers should depend on **板块语境**, not on a specific taxonomy."

> **Dev:** "Should V1 implement multiple **板块语境** adapters?"
> **Domain expert:** "No. V1 records `industry` as the adapter and keeps the contract replaceable for future adapters."

> **Dev:** "Should the HTML report be the source of truth for the **每日报告**?"
> **Domain expert:** "No. The **日报数据契约** is the source of truth; Markdown is the V1 human-readable report, and HTML is a future **富展示报告** outside V1."

> **Dev:** "Can the **交易计划** say 'buy this stock tomorrow'?"
> **Domain expert:** "No. It must say what conditions would make the opportunity observable or actionable, and what conditions invalidate it."

> **Dev:** "Can V1 calculate whether the user followed the **交易计划**?"
> **Domain expert:** "No. V1 can run **计划前向验证**; **交易执行复盘** requires trade logs or manual execution records."

> **Dev:** "If **买点触发** is true, did the user buy?"
> **Domain expert:** "No. It only means the condition was observed in daily data; actual execution belongs to **交易执行复盘**."

> **Dev:** "Can we tweak scoring weights silently and keep comparing S/A/B results?"
> **Domain expert:** "No. Any scoring change must be recorded as a **评分画像**, and validation must group by it."

> **Dev:** "Can users manually curate the **明日观察清单** in V1?"
> **Domain expert:** "No. V1 generates the **明日观察清单** automatically; manual **观察名单管理** is a later product capability."

> **Dev:** "Should V1 store daily reports in a database?"
> **Domain expert:** "No. V1 uses **文件产物** as persistence; a database can be added later for search, collaboration, or watchlist management."

> **Dev:** "Can the system apply a high-confidence **补丁建议** automatically?"
> **Domain expert:** "No. It must become an **已采纳补丁** through explicit user review before application."

> **Dev:** "Should **单票深度研究** produce S/A/B/C **机会评分** in V1?"
> **Domain expert:** "No. V1 **机会评分** is for batch screening; **单票深度研究** remains a separate deep-review workflow."

> **Dev:** "Should V1 send real-time alerts when a **买点触发** occurs intraday?"
> **Domain expert:** "No. V1 is a **盘后系统** and only evaluates **买点触发** from later daily data."

## Flagged ambiguities

- "候选股" was used to mean both rough-screened stocks and trade-plan stocks — resolved: **候选股** only means stocks entering `A_candidates`; later layers must use **重点机会** or **交易计划标的**.
- "AI 分" could be read as an authorization to size positions — resolved: **AI 分析** can affect ranking and risk warnings, but cannot directly increase **仓位上限**.
- "防守市场" could be treated as merely cautious sizing — resolved: in V1, **防守市场** means zero new position plans.
- "板块" was used to mean industry, concept, and theme — resolved: use **板块语境** as the product term; V1's default adapter is the industry field.
- "日报" could mean Markdown, HTML, or source data — resolved: **日报数据契约** is JSON; Markdown is the V1 default human report; **富展示报告** is outside V1 delivery.
- "交易计划" could sound like an execution instruction — resolved: **交易计划** is a conditional research plan for manual observation, not an execution command or investment recommendation.
- "复盘" could mean validating the plan or auditing actual trades — resolved: V1 performs **计划前向验证**; **交易执行复盘** is a later capability requiring execution records.
- "买点触发" could imply real-time alerts or actual buying — resolved: V1 **买点触发** is daily-bar observation only.
- "评分权重" could be treated as silent tuning — resolved: V1 uses a default **评分画像**, and experimental weights must be named and tracked.
- "观察名单" could mean automatic next-day output or user-managed state — resolved: V1 has **明日观察清单** only; **观察名单管理** is later.
- "持久化" could imply a database — resolved: V1 persistence is **文件产物** under `results/`.
- "补丁" could imply automatic self-optimization — resolved: V1 generates **补丁建议**, and only **已采纳补丁** may be applied.
- "评分" could mix batch screening and single-stock research — resolved: V1 **机会评分** applies only to batch A-share screening, not **单票深度研究**.
- "买点触发" could imply real-time alerting — resolved: V1 is a **盘后系统**, and real-time intraday alerts are outside scope.
