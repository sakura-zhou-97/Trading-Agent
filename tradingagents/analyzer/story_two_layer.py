# -*- coding: utf-8 -*-
"""故事性两层分析：第一层=叙事假设生成器+时间轴与催化器，第二层=故事卡合成器。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.dataflows.interface import (
    route_by_market_concepts,
    route_by_market_news,
    route_by_market_fundamentals,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 叙事假设生成器 prompt
# ---------------------------------------------------------------------------
NARRATIVE_SYSTEM = """你是A股"叙事假设生成器"。基于输入数据，输出市场正在复读的主叙事，以及公司披露能支撑的方向。
【硬规则】
1) 输出分为两类：HARD（有证据E#支持）与 INFERRED（仅由概念/热度推断）。
2) HARD类必须引用 evidence_ids（E#）。INFERRED类必须写出推断依据（概念名+rank_5d/ret_5d）。
3) 禁止编造客户、金额、产能、量产阶段等正文细节。
4) 若 input_json 中有 concept_list（东财概念/题材），必须据此输出 market_narrative：例如概念含「机器人、人形机器人、丝杠、行星滚柱丝杠、减速器、轴承」等时，必须输出市场复读的机器人/丝杠/组件龙头等叙事（标 INFERRED，basis 写概念=...）；不得忽略资金炒作的主线。
5) 当 concept_list 有上述题材但 evidence_list 中无对应披露时，在 evidence_hardness.reason 或 data_gaps 中写明：缺少公司机器人/丝杠等业务在近7日新闻或募投中的直接披露。
6) 输出严格JSON。"""

NARRATIVE_USER = """输入数据（JSON）：
{input_json}

说明：concept_list 为东财概念板块名称（如机器人概念、人形机器人）。若存在，必须据此考虑市场复读叙事（如机器人组件龙头、丝杠、行星滚柱丝杠等），并标注 INFERRED 与 basis；若 evidence_list 中无对应披露，需在 evidence_hardness.reason 或下方 data_gaps 中写明缺失。

请输出：
{{
  "company_profile": {{
    "company_intro": "公司介绍（100字内）",
    "main_business_axes": ["主营方向1","主营方向2"],
    "legacy_to_new_bridge": "传统业务如何给新方向背书（制造/客户/现金流）",
    "type": "HARD|INFERRED",
    "evidence_ids": ["E2"]
  }},
  "market_narrative": [
    {{"narrative":"详细输出市场复读的主叙事（含机器人/丝杠/组件龙头等若 concept_list 有）", "type":"INFERRED", "basis":"概念=..., rank_5d=..., ret_5d=..."}}
  ],
  "company_direction": [
    {{"direction":"详细输出公司在做的方向", "type":"HARD", "evidence_ids":["E2","E3"]}}
  ],
  "evidence_hardness": {{
    "hard_docs": ["E2","E3","E4"],
    "risk_docs": ["E1","E5"],
    "hardness_grade": "Strong|Medium|Weak",
    "reason": "为何硬/为何弱（<=100字）；若 concept 有但证据无，写缺少：机器人/丝杠等直接披露"
  }},
  "data_gaps": ["若 concept_list 有机器人/丝杠等但 evidence 无，必填：缺少公司机器人/丝杠业务在近7日新闻或募投中的直接披露"],
  "main_narrative_A": "可选。当公司有「机器人/丝杠/具身智能」新方向时：从轴承/精密制造→切入具身智能机器人核心部件（丝杠+机器人轴承）；定增/募资中的募投方向与产能（行星滚柱丝杠、微型滚珠丝杠、通用机器人专用轴承等）及建设期/达产产能。",
  "main_narrative_B": "可选。当公司有传统制造业务时：传统底盘（轴承/热管理/汽车零部件）仍在，为新故事提供现金流与制造能力背书；券商/东财核心题材描述。"
}}
要求：
- market_narrative 输出1-2条，必须可复读、像市场口径；有 concept_list 时必须覆盖概念对应的市场叙事（如机器人组件龙头）。
- 当公司同时具备「传统制造/轴承/汽车零部件」与「机器人/丝杠/具身智能」时，必须填写 main_narrative_A 与 main_narrative_B（如上格式）。
- company_direction 输出1-3条，须来自募投/募集说明书/交易所进展/定期报告等；若有定增/募资中明确写明的募投方向与产能（如行星滚柱丝杠、机器人轴承），须写出。
- company_profile 必须覆盖“公司介绍、主营方向、传统到新业务桥接”。"""

# ---------------------------------------------------------------------------
# 时间轴与催化器 prompt
# ---------------------------------------------------------------------------
TIMELINE_SYSTEM = """你是"时间轴与催化器"。必须输出近端(1-3个月)时间轴。
【硬规则】
1) 每条催化必须标注 HARD（有E#）或 INFERRED（无E#但有依据）。
2) 若证据不足，必须输出"暂无可验证催化"并说明缺口。
3) 输出严格JSON。"""

TIMELINE_USER = """输入：
- input_json: {input_json}
- narrative_json: {narrative_json}

输出：
{{
  "timeline_1_3m": [
    {{"event":"", "type":"HARD|INFERRED", "window":"1-3个月", "evidence_ids":[], "basis":""}}
  ],
  "catalyst_quality": {{
    "near_term_grade":"Strong|Medium|Weak",
    "mid_term_grade":"Strong|Medium|Weak",
    "data_gaps":[]
  }}
}}"""

# ---------------------------------------------------------------------------
# 故事卡合成器 prompt
# ---------------------------------------------------------------------------
SYNTHESIZER_SYSTEM = """你是"故事性雷达（Narrative Radar）合成器"。目标：回答5个问题：
1) 它的故事是什么（市场复读主叙事 + 公司方向）
2) 证据是否够硬
3) 催化是否有时间表（1-3个月）
4) 资金为什么愿意来
5) 反证条件（出现就降级）
【硬规则】
- HARD类事实必须引用E#；推断必须标注INFERRED并写basis。
- 禁止编造公告正文细节。
- 若 input_json.concept_list 含机器人/丝杠/人形机器人等而证据中无直接披露，notes.data_gaps 必须包含：缺少公司机器人/丝杠等业务在近7日新闻或募投中的直接披露；market_impression / story 须体现市场炒作的主线（如机器人组件龙头）。
- 当公司同时具备「传统制造/轴承/汽车零部件」与「机器人/丝杠/具身智能」时，必须填写 main_story_A 与 main_story_B（见输出 schema）。
- 输出严格JSON。"""

SYNTHESIZER_USER = """输入：
- input_json: {input_json}（含 concept_list 时表示该股所属概念/题材，须在叙事与 data_gaps 中体现）
- narrative_json: {narrative_json}（若含 main_narrative_A、main_narrative_B 则据此充实 main_story_A、main_story_B）
- timeline_json: {timeline_json}

请输出JSON：
{{
  "market_impression": "公司在市场中的一句话印象（100字内；有 concept_list 时须含市场炒作主线如机器人/丝杠龙头）",
  "one_liner": "",
  "company_basics": {{
    "company_intro": "",
    "main_business_axes": [],
    "legacy_to_new_bridge": ""
  }},
  "story": {{
    "market_repeated_narrative": [{{"text":"","type":"INFERRED","basis":""}}],
    "company_direction": [{{"text":"","type":"HARD","evidence_ids":["E2"]}}],
    "so_what": "为什么这个叙事会被复读"
  }},
  "highlights": [
    {{"title":"", "detail":"", "type":"HARD|INFERRED", "evidence_ids":[], "basis":"", "impact":"高|中|低"}}
  ],
  "drawbacks": [
    {{"title":"", "detail":"", "type":"HARD|INFERRED", "evidence_ids":[], "basis":"", "risk_level":"高|中|低"}}
  ],
  "evidence_assessment": {{
    "hardness_grade":"Strong|Medium|Weak",
    "hard_evidence": [{{"point":"","evidence_ids":["E2"],"confidence":0-100}}],
    "weak_points": ["哪些关键点只有推断/缺证据"]
  }},
  "timeline": {{
    "near_1_3m": [],
    "mid_1_3y": []
  }},
  "why_money_comes": [
    {{"reason":"", "type":"DATA|INFERRED", "basis_or_numbers":"如avg_amount_20d=..., rank_5d=..."}}
  ],
  "downgrade_rules": [
    {{"signal":"", "action":"降级动作（如：主叙事降级/移出观察/从趋势转情绪）", "trigger":"可执行触发", "evidence_ids":[]}}
  ],
  "evidence_list": [],
  "notes": {{"data_gaps":["若 concept 有机器人/丝杠等但证据无，必填：缺少公司机器人/丝杠业务在近7日新闻或募投中的直接披露"], "strictness":""}},
  "main_story_A": "主故事A：从轴承/精密制造→切入具身智能机器人核心部件（丝杠+机器人轴承）；定增/募资中明确写明的募投方向与产能（行星滚柱丝杠、微型滚珠丝杠、通用机器人专用轴承等）及建设期/达产产能（可复读的最硬证据之一）。无则填空字符串。",
  "main_story_B": "主故事B：传统底盘（轴承/热管理/汽车零部件）仍在，为新故事提供现金流与制造能力背书；券商研究/东财核心题材对业务结构的描述。无则填空字符串。"
}}
要求：
- why_money_comes 至少3条：流动性/板块定位/交易结构（异动、换手特征）各覆盖1条。
- downgrade_rules 至少4条：披露层/供需层/资金层/供给层各1条，并给出动作。
- highlights 至少3条（成长驱动/产业位置/交易结构至少各1条）。
- drawbacks 至少3条（证据不足/兑现风险/供给或资金约束至少各1条）。
- 当 input_json 含 concept_list（如机器人概念、人形机器人）时：market_impression 与 story.market_repeated_narrative 须体现该主线；若证据无直接披露，notes.data_gaps 须写明缺少机器人/丝杠等直接披露。
- 当公司兼有传统制造（轴承/汽车零部件）与机器人/丝杠新方向时：main_story_A 写新方向/募投（具身智能、丝杠、机器人轴承、定增产能）；main_story_B 写传统业务背书（轴承、热管理、汽车零部件）。"""


def _extract_json(text: str) -> Dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start : end + 1])


def parse_news_to_evidence(news_text: str, max_items: int = 20) -> List[Dict[str, str]]:
    """将新闻文本拆成带 E# 的证据列表。按 ### N. 或 ### 标题 分块。"""
    if not (news_text or "").strip():
        return []
    evidence_list: List[Dict[str, str]] = []
    # 按 ### 开头的行分割，保留块内容
    blocks = re.split(r"\n(?=###\s)", news_text.strip())
    for i, block in enumerate(blocks):
        if i >= max_items:
            break
        block = block.strip()
        if not block:
            continue
        # 首行可能是 "### 1. 标题" 或 "### 标题"
        first_line = block.split("\n")[0] if "\n" in block else block
        first_line = re.sub(r"^###\s*\d*\.?\s*", "", first_line).strip()
        title = first_line[:200] if first_line else ""
        snippet = block[:500].replace("\n", " ")
        evidence_list.append({
            "id": f"E{i + 1}",
            "title": title,
            "snippet": snippet,
        })
    return evidence_list


def _parse_fundamentals_map(fundamentals_text: str) -> Dict[str, str]:
    """Parse markdown bullet lines into key-value map."""
    out: Dict[str, str] = {}
    for line in (fundamentals_text or "").splitlines():
        m = re.match(r"^\-\s+\*\*(.+?)\*\*:\s*(.+)\s*$", line.strip())
        if not m:
            continue
        out[m.group(1).strip()] = m.group(2).strip()
    return out


def _build_company_snapshot(symbol: str, item: Dict, fundamentals_text: str) -> Dict:
    """Build company intro / main business summary for prompts."""
    kv = _parse_fundamentals_map(fundamentals_text)
    industry = item.get("industry", "") or kv.get("行业", "") or kv.get("所属行业", "")
    name = item.get("name", "") or kv.get("股票简称", "") or kv.get("公司名称", "")
    main_business_raw = (
        kv.get("主营业务")
        or kv.get("经营范围")
        or kv.get("公司简介")
        or kv.get("主营构成")
        or ""
    )
    axes: List[str] = []
    if main_business_raw:
        parts = re.split(r"[；;，,、/]+", main_business_raw)
        axes = [p.strip() for p in parts if p.strip()][:6]
    intro = f"{name}（{symbol}），行业={industry}" if name else f"{symbol}，行业={industry}"
    if main_business_raw:
        intro = f"{intro}。主营：{main_business_raw[:140]}"
    return {
        "company_intro": intro,
        "main_business_axes": axes,
        "main_business_raw": main_business_raw[:400],
        "fundamentals_excerpt": (fundamentals_text or "")[:1200],
    }


def build_input_json(
    item: Dict,
    evidence_list: List[Dict[str, str]],
    company_snapshot: Dict,
    concept_list: Optional[List[str]] = None,
) -> Dict:
    """构建叙事/时间轴/合成器所需的 input_json。concept_list 为市场概念/题材（如机器人概念）。"""
    return {
        "symbol": item.get("symbol", ""),
        "name": item.get("name", ""),
        "industry": item.get("industry", ""),
        "change_pct": item.get("change_pct"),
        "recent_3d_change": item.get("recent_3d_change"),
        "company_snapshot": company_snapshot,
        "evidence_list": evidence_list,
        "concept_list": concept_list or [],
    }


def _invoke_llm(llm: Any, full_prompt: str) -> Dict:
    resp = llm.invoke(full_prompt)
    content = getattr(resp, "content", str(resp))
    return _extract_json(content)


def _invoke_llm_with_trace(llm: Any, full_prompt: str) -> Tuple[Dict, str]:
    """调用 LLM 并返回 (解析后的 JSON, 原始响应文本)。"""
    resp = llm.invoke(full_prompt)
    raw_content = getattr(resp, "content", str(resp)) or ""
    parsed = _extract_json(raw_content)
    return parsed, raw_content


def _run_narrative_with_io(
    llm: Any, input_json: Dict
) -> Tuple[Dict, str, str]:
    """叙事假设生成器：返回 (parsed, prompt_text, raw_response)。"""
    user = NARRATIVE_USER.replace("{input_json}", json.dumps(input_json, ensure_ascii=False, indent=2))
    prompt = f"SYSTEM:\n{NARRATIVE_SYSTEM}\n\nUSER:\n{user}"
    parsed, raw = _invoke_llm_with_trace(llm, prompt)
    return parsed, prompt, raw


def _run_timeline_with_io(
    llm: Any, input_json: Dict, narrative_json: Dict
) -> Tuple[Dict, str, str]:
    """时间轴与催化器：返回 (parsed, prompt_text, raw_response)。"""
    user = TIMELINE_USER.replace("{input_json}", json.dumps(input_json, ensure_ascii=False, indent=2))
    user = user.replace("{narrative_json}", json.dumps(narrative_json, ensure_ascii=False, indent=2))
    prompt = f"SYSTEM:\n{TIMELINE_SYSTEM}\n\nUSER:\n{user}"
    parsed, raw = _invoke_llm_with_trace(llm, prompt)
    return parsed, prompt, raw


def _run_synthesizer_with_io(
    llm: Any, input_json: Dict, narrative_json: Dict, timeline_json: Dict
) -> Tuple[Dict, str, str]:
    """故事卡合成器：返回 (parsed, prompt_text, raw_response)。"""
    user = SYNTHESIZER_USER.replace("{input_json}", json.dumps(input_json, ensure_ascii=False, indent=2))
    user = user.replace("{narrative_json}", json.dumps(narrative_json, ensure_ascii=False, indent=2))
    user = user.replace("{timeline_json}", json.dumps(timeline_json, ensure_ascii=False, indent=2))
    prompt = f"SYSTEM:\n{SYNTHESIZER_SYSTEM}\n\nUSER:\n{user}"
    parsed, raw = _invoke_llm_with_trace(llm, prompt)
    return parsed, prompt, raw


def run_narrative_generator(llm: Any, input_json: Dict) -> Dict:
    """第一层：叙事假设生成器。"""
    parsed, _, _ = _run_narrative_with_io(llm, input_json)
    return parsed


def run_timeline_catalyst(llm: Any, input_json: Dict, narrative_json: Dict) -> Dict:
    """第一层：时间轴与催化器。"""
    parsed, _, _ = _run_timeline_with_io(llm, input_json, narrative_json)
    return parsed


def run_story_synthesizer(llm: Any, input_json: Dict, narrative_json: Dict, timeline_json: Dict) -> Dict:
    """第二层：故事卡合成器。"""
    parsed, _, _ = _run_synthesizer_with_io(llm, input_json, narrative_json, timeline_json)
    return parsed


def _story_payload_from_card(story_card: Dict) -> Dict:
    """从故事卡导出供 C 使用的简易 story_payload。"""
    ea = story_card.get("evidence_assessment", {}) or {}
    return {
        "news_count": len(story_card.get("evidence_list", [])),
        "story_heat_level": ea.get("hardness_grade", "Weak").lower() if isinstance(ea.get("hardness_grade"), str) else "low",
        "is_mainline_candidate": bool(story_card.get("one_liner")),
        "has_risk_alert": bool(story_card.get("downgrade_rules")),
        "raw_length": len(json.dumps(story_card, ensure_ascii=False)),
        "one_liner": story_card.get("one_liner", ""),
    }


def run_story_analysis_2layer(
    candidates: List[Dict],
    trade_date: str,
    config: Dict,
    fetch_news_fn: Optional[Any] = None,
    news_max_chars: int = 1800,
    max_evidence_items: int = 20,
) -> Dict:
    """运行两层故事分析：第一层=叙事生成+时间轴催化，第二层=故事卡合成。
    返回与 run_story_analysis 兼容的结构，并增加 narrative_json、timeline_json、story_card。
    """
    from datetime import datetime, timedelta
    from tradingagents.llm_clients import create_llm_client

    def _news_window(td: str):
        end_dt = datetime.strptime(td, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=7)
        return start_dt.strftime("%Y-%m-%d"), td

    def _fetch(symbol: str) -> str:
        if fetch_news_fn is not None:
            return (fetch_news_fn(symbol, trade_date) or "")[:news_max_chars]
        start_date, end_date = _news_window(trade_date)
        try:
            return route_by_market_news(symbol, start_date, end_date)[:news_max_chars]
        except Exception as exc:
            logger.warning("Fetch news failed for %s: %s", symbol, exc)
            return "无可用新闻"

    provider = config.get("llm_provider", "openai")
    model = config.get("quick_think_llm", "gpt-4o-mini")
    kwargs: Dict = {}
    if provider == "openai" and config.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    if provider == "google" and config.get("google_thinking_level"):
        kwargs["thinking_level"] = config["google_thinking_level"]
    client = create_llm_client(
        provider=provider,
        model=model,
        base_url=config.get("backend_url"),
        **kwargs,
    )
    llm = client.get_llm()

    story_by_symbol: Dict[str, Dict] = {}
    for item in candidates:
        symbol = item.get("symbol", "")
        if not symbol:
            continue
        news_text = _fetch(symbol)
        evidence_list = parse_news_to_evidence(news_text, max_items=max_evidence_items)
        try:
            fundamentals_text = route_by_market_fundamentals(symbol, trade_date)
        except Exception as exc:
            logger.warning("Fetch fundamentals failed for %s: %s", symbol, exc)
            fundamentals_text = ""
        company_snapshot = _build_company_snapshot(symbol, item, fundamentals_text)
        try:
            concept_list = route_by_market_concepts(symbol)
        except Exception as exc:
            logger.warning("Fetch concepts failed for %s: %s", symbol, exc)
            concept_list = []
        input_json = build_input_json(item, evidence_list, company_snapshot, concept_list=concept_list)

        narrative_json: Dict = {}
        timeline_json: Dict = {}
        story_card: Dict = {}
        err_msg = ""
        prompt_io: Dict[str, Dict] = {}

        try:
            narrative_json, prompt_narr, raw_narr = _run_narrative_with_io(llm, input_json)
            prompt_io["narrative_generator"] = {
                "prompt_input": {"input_json": input_json},
                "prompt_text": prompt_narr,
                "raw_response": raw_narr,
                "raw_input": prompt_narr,
                "raw_output": raw_narr,
                "parsed": narrative_json,
            }
        except Exception as e:
            err_msg = str(e)
            logger.warning("Narrative generator failed for %s: %s", symbol, e)
            prompt_io["narrative_generator"] = {
                "prompt_input": {"input_json": input_json},
                "prompt_text": "",
                "raw_response": "",
                "raw_input": "",
                "raw_output": "",
                "parsed": {},
                "error": err_msg,
            }

        if narrative_json:
            try:
                timeline_json, prompt_tl, raw_tl = _run_timeline_with_io(llm, input_json, narrative_json)
                prompt_io["timeline_catalyst"] = {
                    "prompt_input": {"input_json": input_json, "narrative_json": narrative_json},
                    "prompt_text": prompt_tl,
                    "raw_response": raw_tl,
                    "raw_input": prompt_tl,
                    "raw_output": raw_tl,
                    "parsed": timeline_json,
                }
            except Exception as e:
                err_msg = err_msg or str(e)
                logger.warning("Timeline catalyst failed for %s: %s", symbol, e)
                prompt_io["timeline_catalyst"] = {
                    "prompt_input": {"input_json": input_json, "narrative_json": narrative_json},
                    "prompt_text": "",
                    "raw_response": "",
                    "raw_input": "",
                    "raw_output": "",
                    "parsed": {},
                    "error": str(e),
                }

        if narrative_json and timeline_json:
            try:
                story_card, prompt_syn, raw_syn = _run_synthesizer_with_io(
                    llm, input_json, narrative_json, timeline_json
                )
                prompt_io["story_synthesizer"] = {
                    "prompt_input": {
                        "input_json": input_json,
                        "narrative_json": narrative_json,
                        "timeline_json": timeline_json,
                    },
                    "prompt_text": prompt_syn,
                    "raw_response": raw_syn,
                    "raw_input": prompt_syn,
                    "raw_output": raw_syn,
                    "parsed": story_card,
                }
            except Exception as e:
                err_msg = err_msg or str(e)
                logger.warning("Story synthesizer failed for %s: %s", symbol, e)
                prompt_io["story_synthesizer"] = {
                    "prompt_input": {
                        "input_json": input_json,
                        "narrative_json": narrative_json,
                        "timeline_json": timeline_json,
                    },
                    "prompt_text": "",
                    "raw_response": "",
                    "raw_input": "",
                    "raw_output": "",
                    "parsed": {},
                    "error": str(e),
                }

        if not story_card:
            story_card = {
                "one_liner": "",
                "story": {},
                "evidence_assessment": {"hardness_grade": "Weak", "hard_evidence": [], "weak_points": []},
                "timeline": {"near_1_3m": [], "mid_1_3y": []},
                "why_money_comes": [],
                "downgrade_rules": [],
                "evidence_list": evidence_list,
                "notes": {"data_gaps": [err_msg or "未跑通三层"], "strictness": ""},
            }

        story_payload = _story_payload_from_card(story_card)
        story_by_symbol[symbol] = {
            "company_snapshot": company_snapshot,
            "narrative_json": narrative_json,
            "timeline_json": timeline_json,
            "story_card": story_card,
            "story_payload": story_payload,
            "news_text": news_text,
            "prompt_io": prompt_io,
        }

    return {
        "trade_date": trade_date,
        "count": len(story_by_symbol),
        "story_by_symbol": story_by_symbol,
        "mode": "two_layer",
    }
