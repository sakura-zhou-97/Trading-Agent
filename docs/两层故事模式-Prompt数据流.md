# 两层故事模式：三个 Prompt 的输入输出数据流

本文档单独列举 **故事两层分析**（`story_analysis_mode=two_layer`）中三个 LLM Prompt 的**输入 / 输出**数据流，每个字段均用 603667 五洲新春的试跑结果给出示例值。  
数据来源：`tradingagents/analyzer/story_two_layer.py`、`results/screener/2026-02-19/single_603667/B_story_analysis_603667.json` 中的 `prompt_io`。

---

## 一、流程与调用顺序

| 顺序 | Prompt 名称 | 代码入口 | 输入 | 输出 |
|------|-------------|----------|------|------|
| 1 | 叙事假设生成器 | `_run_narrative_with_io` | input_json | narrative_json |
| 2 | 时间轴与催化器 | `_run_timeline_with_io` | input_json + narrative_json | timeline_json |
| 3 | 故事卡合成器 | `_run_synthesizer_with_io` | input_json + narrative_json + timeline_json | story_card |

三者共用同一 **input_json**（由 `build_input_json` 从候选条 + 证据列表 + 公司快照 + concept_list 构建）。

---

## 二、共用输入：input_json

由 `build_input_json(item, evidence_list, company_snapshot, concept_list)` 生成，作为**三个 Prompt 的公共输入**（叙事生成器仅用此；时间轴与合成器在此基础上再接收前序输出）。

| 字段 | 含义 | 示例值（603667） |
|------|------|------------------|
| symbol | 6 位代码 | "603667" |
| name | 股票名称 | "五洲新春" |
| industry | 行业 | "通用设备" |
| change_pct | 当日涨跌幅(%) | 0.0（单票跑可为占位） |
| recent_3d_change | 近 3 日涨跌幅(%) | null |
| company_snapshot.company_intro | 公司一句话介绍 | "五洲新春（603667），行业=通用设备" |
| company_snapshot.main_business_axes | 主营方向列表 | [] |
| company_snapshot.main_business_raw | 主营原始描述(截断) | "" |
| company_snapshot.fundamentals_excerpt | 基本面摘要(≤1200 字) | "# Fundamentals for 603667 ... 行业: 通用设备\n上市时间: 20161025" |
| evidence_list | 证据列表(E#) | 见下表 |
| concept_list | 东财概念/题材名列表 | ["机器人执行器","减速器","人形机器人","机器人概念"] |

**evidence_list 单条**：

| 字段 | 含义 | 示例值 |
|------|------|--------|
| id | 证据 ID | "E1" / "E2" / "E3" |
| title | 标题 | "## A-share News for 603667 (2026-02-12 ~ 2026-02-19)" / "特钢概念下跌2.47%，主力资金净流出30股" / "机械设备行业今日净流入资金69.04亿元..." |
| snippet | 片段(截断) | "### 1. 特钢概念下跌2.47% ... 603667..." |

---

## 三、Prompt 1：叙事假设生成器（Narrative Generator）

- **角色**：A股「叙事假设生成器」——根据 input_json 输出市场正在复读的主叙事、公司披露能支撑的方向、证据硬度与缺口。
- **输入**：仅 **input_json**（见第二节）。
- **输出**：**narrative_json**（下表为 603667 示例值）。

### 3.1 输出 narrative_json：字段与示例值

| 字段 | 含义 | 示例值（603667） |
|------|------|------------------|
| company_profile.company_intro | 公司介绍(100 字内) | "五洲新春（603667），通用设备行业上市公司，市值约331亿，主营通用设备与机械制造相关业务。" |
| company_profile.main_business_axes | 主营方向 | ["通用设备制造","机械零部件加工"] |
| company_profile.legacy_to_new_bridge | 传统到新业务桥接 | "公司具备传统制造能力、产线与客户基础，能为向高精密传动件（如减速器/轴承/执行器）延伸提供制造、交付与现金流支撑；但无直接披露证明已明确转型路径。" |
| company_profile.type | HARD / INFERRED | "INFERRED" |
| company_profile.evidence_ids | 引用证据 ID | ["E2","E3"] |
| market_narrative[0].narrative | 市场复读主叙事 | "市场复读口径：机器人/机器人执行器与减速器板块，重点是组件龙头（行星滚柱丝杠、微型滚珠丝杠、机器人专用轴承、减速器）国产替代與客户放量，通用设备龙头有望被市场贴上"机器人组件"标签并获得估值溢价。" |
| market_narrative[0].type | HARD / INFERRED | "INFERRED" |
| market_narrative[0].basis | 推断依据 | "概念=机器人执行器,减速器,人形机器人,机器人概念; rank_5d=n/a; ret_5d=n/a" |
| company_direction[0].direction | 公司方向描述 | "推断方向：可能被市场期待向机器人执行器/减速器/机器人专用轴承等精密传动件延伸，利用现有通用设备制造能力承接机器人零部件订单与客户。" |
| company_direction[0].type | HARD / INFERRED | "INFERRED" |
| company_direction[0].basis | 依据 | "概念=机器人执行器,减速器,人形机器人,机器人概念; rank_5d=n/a; ret_5d=n/a" |
| evidence_hardness.hard_docs | 硬证据 ID | ["E2","E3"] |
| evidence_hardness.risk_docs | 风险/弱证据 ID | ["E1"] |
| evidence_hardness.hardness_grade | 硬度等级 | "Weak" |
| evidence_hardness.reason | 原因说明 | "公司仅在行业/概念报道中被点名（E2,E3），但近7日及募投/定期报告中缺乏关于机器人/丝杠/减速器等业务的直接披露，证据不足以支撑实质性业务转向。" |
| data_gaps | 信息缺口列表 | ["缺少公司机器人/丝杠业务在近7日新闻或募投中的直接披露"] |
| main_narrative_A | 主故事 A(新方向/募投) | "从精密传动与轴承/精密制造切入具身智能机器人核心部件路径：市场口径为公司可利用传统精密零件加工能力，布局行星滚柱丝杠、微型滚珠丝杠与机器人专用轴承，参与机器人执行器与减速器国产化替代（说明：当前无公司募投/定增文件披露该类具体募投项目或产能）。" |
| main_narrative_B | 主故事 B(传统背书) | "传统制造为新方向提供背书：公司现有通用设备制造体系、产线与客户关系，被视为向机器人/丝杠/减速器等高精密部件延伸的基础，市场常以此逻辑将通用设备标的纳入机器人组件题材进行炒作。" |

---

## 四、Prompt 2：时间轴与催化器（Timeline Catalyst）

- **角色**：「时间轴与催化器」——输出近端(1–3 个月)时间轴与催化质量。
- **输入**：**input_json**（同上）+ **narrative_json**（Prompt 1 输出）。
- **输出**：**timeline_json**（下表为 603667 示例值）。

### 4.1 输入（新增部分）narrative_json

即第三节整段 narrative_json，此处不重复；用于结合叙事判断近端催化与缺口。

### 4.2 输出 timeline_json：字段与示例值

| 字段 | 含义 | 示例值（603667） |
|------|------|------------------|
| timeline_1_3m[0].event | 近端催化事件描述 | "短期内被板块/题材资金推动导致股价波动或换手率上升（题材性资金带动）" |
| timeline_1_3m[0].type | HARD / INFERRED | "INFERRED" |
| timeline_1_3m[0].window | 时间窗口 | "1-3个月" |
| timeline_1_3m[0].evidence_ids | 证据 ID | [] |
| timeline_1_3m[0].basis | 依据 | "公司被行业/资金流类报道被点名且被归入"机器人执行器/减速器/机器人概念"等题材；若该细分板块或概念在短期内获得资金集中流入，个股常被动跟随产生波动。现有公开信息仅为板块/资金流报道及概念标签，缺乏公司层面的业务或订单披露，故为推断性催化。" |
| timeline_1_3m[1].event | 第二条近端催化 | "若公司在1-3个月内披露与机器人/减速器/精密传动件相关的重大合同、募投/扩产或并购，将构成可验证的公司级催化" |
| timeline_1_3m[1].type | HARD / INFERRED | "INFERRED" |
| unverifiable_note | 暂无可验证催化说明 | "暂无可验证催化：当前缺乏公司层面可验证的近端催化事件（如业绩预告/业绩快报、重大合同/客户订单披露、募投/定增/并购公告或管理层明确转型披露）。现有证据仅为被纳入概念与被动的资金流、板块报道（行业/资金流新闻），无法作为公司级"硬"催化证据。" |
| catalyst_quality.near_term_grade | 近端催化质量 | "Weak" |
| catalyst_quality.mid_term_grade | 中期催化质量 | "Weak" |
| catalyst_quality.data_gaps | 催化缺口列表 | ["无公司层面关于机器人执行器/减速器/丝杠/轴承等业务的近期披露（重大合同、产能/募投或合作公告）", "无近期业绩预告/业绩快报或定期报告中披露的结构性业务增长证据", "缺乏管理层公开表态或投资者互动记录确认转型或新产品交付时间表", "缺少可验证的时间表（如预计订单交付、产能投产、验收节点）用于判定1-3个月内成型的硬催化"] |

---

## 五、Prompt 3：故事卡合成器（Story Synthesizer）

- **角色**：「故事性雷达（Narrative Radar）合成器」——回答：故事是什么、证据是否够硬、催化是否有时间表、资金为什么来、反证条件。
- **输入**：**input_json** + **narrative_json** + **timeline_json**（前两节输出）。
- **输出**：**story_card**（下表为 603667 示例值，仅列主要字段；highlights/drawbacks/downgrade_rules 等为数组，结构一致）。

### 5.1 输出 story_card：字段与示例值

| 字段 | 含义 | 示例值（603667） |
|------|------|------------------|
| market_impression | 市场一句话印象(100 字内) | "被市场以"机器人/减速器/丝杠组件"题材反复提及的通用设备龙头候选，炒作主线为利用传统精密制造能力切入机器人执行器与减速器国产化替代（机器人/丝杠龙头想象）。" |
| one_liner | 一句话总结 | "通用设备制造商，被资金流与题材贴上机器人组件（减速器/丝杠/轴承）标签，但缺乏公司层面实质披露，证据偏弱。" |
| company_basics.company_intro | 公司介绍 | "五洲新春（603667），通用设备行业上市公司，市值约331亿，主营通用设备与机械制造相关业务。" |
| company_basics.main_business_axes | 主营方向 | ["通用设备制造","机械零部件加工"] |
| company_basics.legacy_to_new_bridge | 传统到新业务桥接 | "公司具备传统制造产线与客户基础，理论上可承接向高精密传动件（如减速器/丝杠/机器人轴承）延伸的生产订单；但近7日及募投/定期披露中无直接证据证明已明确转型或新增相关产能（INFERRED，basis：概念标签+行业报道指名，缺少公司公告）。" |
| story.market_repeated_narrative[0].text | 市场复读叙事 | "市场复读口径：机器人执行器/减速器/丝杠板块，重视组件国产替代，通用设备龙头有望被贴上机器人组件标签并获得溢价。" |
| story.market_repeated_narrative[0].type | HARD / INFERRED | "INFERRED" |
| story.market_repeated_narrative[0].basis | 依据 | "input concept_list 包含机器人执行器、减速器、人形机器人、机器人概念；公司在行业/资金流类报道中被点名（E2, E3），故形成题材预期但无公司层面硬披露。" |
| story.company_direction[0].text | 公司方向 | "市场与资金流将公司视作可向机器人执行器/减速器/机器人专用轴承延伸的通用设备标的。" |
| story.company_direction[0].type | HARD / INFERRED | "HARD" |
| story.company_direction[0].evidence_ids | 证据 ID | ["E2"] |
| story.so_what | 叙事为何被复读 | "该叙事被复读因两点：1) 概念面——公司被归入机器人/减速器等题材（概念标签容易形成共识）；2) 资金面——相关行业与机械设备板块出现资金流与报道，题材资金会放大对未披露但被贴标签个股的预期，推高短期交易性溢价（INFERRED，basis：E2/E3 提到该股被行业或资金流类报道点名）。" |
| highlights[0].title | 亮点标题 | "产业位置（潜在）" |
| highlights[0].detail | 详情 | "具备通用设备与机械零部件制造能力，市场逻辑认为可向高精密传动件（减速器、丝杠、机器人轴承）延伸并获得高估值溢价。" |
| highlights[0].type | HARD / INFERRED | "INFERRED" |
| highlights[0].impact | 影响 | "中" |
| drawbacks[0].title | 缺点标题 | "证据不足" |
| drawbacks[0].detail | 详情 | "近7日及募投/定期报告中缺乏公司层面关于机器人/丝杠/减速器/轴承等业务的直接披露，无法确认业务转向或产能投产时间表。" |
| drawbacks[0].risk_level | 风险等级 | "高" |
| evidence_assessment.hardness_grade | 证据硬度 | "Weak" |
| evidence_assessment.hard_evidence[0].point | 硬证据要点 | "公司在近期行业/资金流报道中被点名为相关板块成员或在资金流榜单出现（表明市场将其纳入该题材关注范围）。" |
| evidence_assessment.hard_evidence[0].evidence_ids | 证据 ID | ["E2","E3"] |
| evidence_assessment.hard_evidence[0].confidence | 置信度 0–100 | 45 |
| evidence_assessment.weak_points | 弱项列表 | ["缺乏公司层面关于机器人执行器/减速器/丝杠/轴承等业务的直接披露（合同、募投、产能、管理层表态）", "未见募投/定增/并购文件中明确写入相关新方向的建设期/达产产能数据", "无近期业绩快报或定期报告证明结构性订单增长或收入归因于机器人组件"] |
| timeline.near_1_3m[0].event | 近 1–3 月事件 | "题材资金短期拉动导致股价波动或换手率上升（交易性、情绪性波动）" |
| timeline.near_1_3m[0].type | HARD / INFERRED | "INFERRED" |
| timeline.mid_1_3y | 中期 1–3 年事件列表 | 含「若公司完成募投/产能建设…」「若未能取得技术/客户验证…」等 |
| why_money_comes[0].reason | 资金来的原因 | "板块资金轮动/行业资金流入（短期交易性资金）" |
| why_money_comes[0].type | DATA / INFERRED | "DATA" |
| why_money_comes[0].basis_or_numbers | 依据或数据 | "E3 显示机械设备行业当日净流入（示例：机械设备行业资金流入69.04亿元），个股有被列示记载，表明短期资金关注（E3）。" |
| downgrade_rules[0].signal | 降级信号 | "公司公告明确否认或未列入任何募投/扩产至机器人/丝杠/减速器相关项目" |
| downgrade_rules[0].action | 降级动作 | "主叙事降级为"题材化无实质化支撑"，移出重点观察名单" |
| downgrade_rules[0].trigger | 可执行触发 | "公司公告或定期报告明确表示不涉及相关业务或撤回相关项目（可执行触发）" |
| notes.data_gaps | 数据缺口 | ["缺少公司机器人/丝杠业务在近7日新闻或募投中的直接披露"] |
| notes.strictness | 严格程度 | "高（因概念标签存在但无公司层面披露，需以公告为准）" |
| main_story_A | 主故事 A 文案 | "从精密传动与轴承/精密制造切入具身智能机器人核心部件路径：市场口径为公司可利用传统精密零件加工能力，布局行星滚柱丝杠、微型滚珠丝杠与机器人专用轴承，参与机器人执行器与减速器国产化替代（说明：当前无公司募投/定增文件披露该类具体募投项目或产能）。" |
| main_story_B | 主故事 B 文案 | "传统制造为新方向提供背书：公司现有通用设备制造体系、产线与客户关系，被视为向机器人/丝杠/减速器等高精密部件延伸的基础，市场常以此逻辑将通用设备标的纳入机器人组件题材进行炒作。" |
| evidence_list | 证据列表(回写) | 与 input_json.evidence_list 一致，含 E1/E2/E3 的 id、title、snippet |

---

## 六、数据流串联小结

| 步骤 | 输入 | 输出 | 输出去向 |
|------|------|------|----------|
| 1 叙事假设生成器 | input_json | narrative_json | 写入 B_story_analysis；供 Prompt 2、3 |
| 2 时间轴与催化器 | input_json, narrative_json | timeline_json | 写入 B_story_analysis；供 Prompt 3 |
| 3 故事卡合成器 | input_json, narrative_json, timeline_json | story_card | 写入 B_story_analysis；并导出 story_payload 供 C 使用 |

`prompt_io` 中每个 key（`narrative_generator` / `timeline_catalyst` / `story_synthesizer`）均包含：`prompt_input`（结构化输入）、`prompt_text`（完整发给 LLM 的文本）、`raw_input`/`raw_output`（原始 IO）、`parsed`（解析后的 JSON）。调试时可直接对照 `B_story_analysis_<symbol>.json` 内 `story_by_symbol[symbol].prompt_io`。
