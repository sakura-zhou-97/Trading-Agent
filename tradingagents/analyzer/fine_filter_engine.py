"""Fine filter engine using AI + rule fallback for decision cards."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from tradingagents.analyzer.decision_card_schema import DecisionCard
from tradingagents.dataflows.interface import route_by_market_news
from tradingagents.llm_clients import create_llm_client

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """你是A股短线交易研究助手。请只返回JSON，不要返回任何解释。

输入股票信息:
{stock_payload}

故事性特征:
{story_payload}

板块上下文:
{sector_payload}

近7日相关新闻摘要:
{news_payload}

要求：
1) evidence_chain 必须至少有1条直接引用板块上下文（如 sector、sector_day_strength、sector_trend_3d、sector_multiplier、sector_leader_status）。
2) tradability/sustainability/max_risk 需要体现板块状态对个股判断的影响。
3) 不要输出任何打分字段。

请输出如下JSON结构（字段名必须一致）:
{{
  "conclusion_type": "趋势|情绪|混合",
  "stage": "启动|加速|调整|二次启动",
  "evidence_chain": ["证据1","证据2","证据3"],
  "tradability": "一句话",
  "sustainability": "一句话",
  "expectation_gap": "一句话",
  "structure_position": "一句话",
  "max_risk": "一句话",
  "reversal_trigger": "一句话",
  "info_gaps": ["信息缺口1","信息缺口2"]
}}
"""


def _extract_json(text: str) -> Dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start : end + 1])


def _fallback_decision(item: Dict) -> DecisionCard:
    change_pct = float(item.get("change_pct", 0.0))
    trend = str(item.get("trend_label", "unknown"))
    last_close = float(item.get("last_close", 0.0))
    ma5 = float(item.get("ma5", 0.0))
    ma10 = float(item.get("ma10", 0.0))
    vol_ratio = float(item.get("vol_ratio", 0.0))
    sector = str(item.get("sector", "")).strip() or "unknown_sector"
    sector_day_strength = item.get("sector_day_strength")
    sector_trend_3d = item.get("sector_trend_3d")
    sector_multiplier = item.get("sector_multiplier")
    leader_status = str(item.get("sector_leader_status", "")).strip() or "未知"
    if change_pct >= 8.0 and last_close >= ma5 >= ma10:
        stage = "加速"
    elif change_pct > 0 and last_close >= ma5:
        stage = "启动"
    elif last_close < ma10:
        stage = "调整"
    else:
        stage = "二次启动"
    return DecisionCard(
        symbol=item["symbol"],
        name=item.get("name", ""),
        industry=item.get("industry", ""),
        conclusion_type="趋势",
        stage=stage,
        evidence_chain=[
            f"当日涨幅为{change_pct:.2f}%，价格行为显示短线活跃",
            f"趋势标签为{trend}，收盘与均线关系为 Close={last_close} MA5={ma5} MA10={ma10}",
            (
                f"板块{sector}强度参考：day_strength={sector_day_strength}, "
                f"trend_3d={sector_trend_3d}, multiplier={sector_multiplier}, leader_status={leader_status}"
            ),
        ],
        tradability="主线/分支交易性中等，需结合当日板块强弱确认",
        sustainability="短期持续性取决于量能是否维持与催化是否扩散",
        expectation_gap="当前更多是结构兑现，若有新增催化才可能打开空间",
        structure_position=f"Close={item.get('last_close', 0)} MA5={item.get('ma5', 0)} MA10={item.get('ma10', 0)}",
        max_risk="冲高回落并跌破MA10导致情绪快速降温",
        reversal_trigger="放量站回前高且收盘不破MA5",
        info_gaps=["缺少更细颗粒度资金流数据", "缺少板块内龙头强弱确认"],
    )


def _build_sector_payload(item: Dict, sector_context_by_symbol: Dict[str, Dict] | None) -> Dict:
    if sector_context_by_symbol:
        from_map = sector_context_by_symbol.get(item.get("symbol", ""), {})
    else:
        from_map = {}
    # Prefer explicit context map; fallback to fields merged in item.
    payload = {
        "sector": from_map.get("sector", item.get("sector", "")),
        "sector_day_strength": from_map.get("sector_day_strength", item.get("sector_day_strength")),
        "sector_trend_3d": from_map.get("sector_trend_3d", item.get("sector_trend_3d")),
        "sector_multiplier": from_map.get("sector_multiplier", item.get("sector_multiplier")),
        "sector_leader_symbol": from_map.get("sector_leader_symbol", item.get("sector_leader_symbol", "")),
        "sector_leader_status": from_map.get("sector_leader_status", item.get("sector_leader_status", "")),
        "calibration_reason": from_map.get("calibration_reason", item.get("calibration_reason", "")),
    }
    return payload


def _ensure_sector_evidence(card: DecisionCard, sector_payload: Dict) -> None:
    text = " ".join(card.evidence_chain or [])
    if any(k in text for k in ["板块", "sector", "multiplier", "leader_status"]):
        return
    card.evidence_chain = (card.evidence_chain or [])[:2]
    card.evidence_chain.append(
        "板块上下文纳入判断："
        f"sector={sector_payload.get('sector')}, "
        f"day_strength={sector_payload.get('sector_day_strength')}, "
        f"trend_3d={sector_payload.get('sector_trend_3d')}, "
        f"multiplier={sector_payload.get('sector_multiplier')}, "
        f"leader_status={sector_payload.get('sector_leader_status')}"
    )


def _load_prompt_template(config: Dict) -> str:
    prompt_path = str(config.get("stock_analysis", {}).get("prompt_path", "")).strip()
    if not prompt_path:
        return PROMPT_TEMPLATE
    path = Path(prompt_path)
    if not path.exists():
        return PROMPT_TEMPLATE
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return PROMPT_TEMPLATE
    return content + "\n\n输入股票信息:\n{stock_payload}\n\n故事性特征:\n{story_payload}\n\n板块上下文:\n{sector_payload}\n\n近7日相关新闻摘要:\n{news_payload}\n\n要求：\n1) evidence_chain 必须至少有1条直接引用板块上下文（如 sector、sector_day_strength、sector_trend_3d、sector_multiplier、sector_leader_status）。\n2) tradability/sustainability/max_risk 需要体现板块状态对个股判断的影响。\n3) 不要输出任何打分字段。\n\n请输出如下JSON结构（字段名必须一致）:\n{\n  \"conclusion_type\": \"趋势|情绪|混合\",\n  \"stage\": \"启动|加速|调整|二次启动\",\n  \"evidence_chain\": [\"证据1\",\"证据2\",\"证据3\"],\n  \"tradability\": \"一句话\",\n  \"sustainability\": \"一句话\",\n  \"expectation_gap\": \"一句话\",\n  \"structure_position\": \"一句话\",\n  \"max_risk\": \"一句话\",\n  \"reversal_trigger\": \"一句话\",\n  \"info_gaps\": [\"信息缺口1\",\"信息缺口2\"]\n}"


def _build_story_features(news_text: str) -> Dict:
    text = (news_text or "").lower()
    headlines = news_text.count("### ")
    hot_keywords = ["涨停", "龙虎榜", "题材", "政策", "预告", "风险提示", "主线", "龙头", "机构"]
    hits = {k: news_text.count(k) for k in hot_keywords}
    hotness = headlines * 8 + sum(min(v, 5) * 5 for v in hits.values())
    if hotness >= 80:
        heat_level = "high"
    elif hotness >= 40:
        heat_level = "medium"
    else:
        heat_level = "low"
    return {
        "news_count": headlines,
        "keyword_hits": hits,
        "story_heat_level": heat_level,
        "is_mainline_candidate": hits.get("主线", 0) > 0 or hits.get("龙头", 0) > 0,
        "has_risk_alert": hits.get("风险提示", 0) > 0,
        "raw_length": len(text),
    }


def _build_raw_stock_payload(item: Dict) -> Dict:
    # Only pass raw/direct features to AI to avoid derived-signal anchoring.
    fields = [
        "symbol",
        "name",
        "industry",
        "market",
        "change_pct",
        "close",
        "open",
        "high",
        "low",
        "volume",
        "amount",
        "trend_label",
        "recent_3d_change",
        "last_close",
        "ma5",
        "ma10",
        "ma20",
        "vol_ratio",
    ]
    return {k: item.get(k) for k in fields if k in item}


def _render_prompt(
    template: str,
    stock_payload: str,
    story_payload: str,
    sector_payload: str,
    news_payload: str,
) -> str:
    """Render prompt safely without depending on str.format brace escaping."""
    return (
        template.replace("{stock_payload}", stock_payload)
        .replace("{story_payload}", story_payload)
        .replace("{sector_payload}", sector_payload)
        .replace("{news_payload}", news_payload)
    )


def _build_llm(config: Dict):
    provider = config.get("llm_provider", "openai")
    model = config.get("quick_think_llm", "gpt-5-mini")
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
    return client.get_llm()


def _news_window(trade_date: str) -> Tuple[str, str]:
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=7)
    return start_dt.strftime("%Y-%m-%d"), trade_date


def _fetch_news(symbol: str, trade_date: str) -> str:
    start_date, end_date = _news_window(trade_date)
    try:
        return route_by_market_news(symbol, start_date, end_date)
    except Exception as exc:
        logger.warning("Fetch news failed for %s: %s", symbol, exc)
        return "无可用新闻"


def run_story_analysis(
    candidates: List[Dict],
    trade_date: str,
    news_max_chars: int = 1800,
) -> Dict:
    """Run story analysis for all candidates (same tier as sector calibration).
    Returns story features and raw news text per symbol for use as AI input.
    """
    story_by_symbol: Dict[str, Dict] = {}
    for item in candidates:
        symbol = item.get("symbol", "")
        if not symbol:
            continue
        news_text = _fetch_news(symbol, trade_date)
        news_text = (news_text or "")[:news_max_chars]
        story_payload = _build_story_features(news_text)
        story_by_symbol[symbol] = {
            "story_payload": story_payload,
            "news_text": news_text,
        }
    return {
        "trade_date": trade_date,
        "count": len(story_by_symbol),
        "story_by_symbol": story_by_symbol,
        "mode": "simple",
    }


def analyze_candidates(
    candidates: List[Dict],
    trade_date: str,
    config: Dict,
    max_selected: int = 10,
    enable_ai: bool = True,
    sector_context_by_symbol: Dict[str, Dict] | None = None,
    story_by_symbol: Dict[str, Dict] | None = None,
) -> Dict:
    _ = max_selected
    prompt_template = _load_prompt_template(config)
    llm = None
    if enable_ai:
        try:
            llm = _build_llm(config)
        except Exception as exc:
            logger.warning("LLM init failed, fallback to rule mode: %s", exc)
            llm = None

    story_map = story_by_symbol if story_by_symbol is not None else {}
    cards: List[DecisionCard] = []
    trace_by_symbol: Dict[str, Dict] = {}
    for item in candidates:
        sector_payload = _build_sector_payload(item=item, sector_context_by_symbol=sector_context_by_symbol)
        item_with_sector = {**item, **sector_payload}
        card: DecisionCard
        if llm is None:
            card = _fallback_decision(item_with_sector)
            trace_by_symbol[item["symbol"]] = {"mode": "fallback", "error": ""}
        else:
            try:
                symbol = item["symbol"]
                story_data = story_map.get(symbol)
                if story_data:
                    story_payload = story_data.get("story_payload", _build_story_features(""))
                    news_payload = story_data.get("news_text", "")
                else:
                    news_payload = _fetch_news(symbol, trade_date)[:1800]
                    story_payload = _build_story_features(news_payload)
                prompt = _render_prompt(
                    template=prompt_template,
                    stock_payload=json.dumps(_build_raw_stock_payload(item_with_sector), ensure_ascii=False),
                    story_payload=json.dumps(story_payload, ensure_ascii=False),
                    sector_payload=json.dumps(sector_payload, ensure_ascii=False),
                    news_payload=news_payload,
                )
                resp = llm.invoke(prompt)
                content = getattr(resp, "content", str(resp))
                obj = _extract_json(content)
                card = DecisionCard(
                    symbol=item["symbol"],
                    name=item.get("name", ""),
                    industry=item.get("industry", ""),
                    conclusion_type=obj.get("conclusion_type", "混合"),
                    stage=obj.get("stage", "启动"),
                    evidence_chain=(obj.get("evidence_chain") or [])[:3] or _fallback_decision(item).evidence_chain,
                    tradability=obj.get("tradability", "待观察"),
                    sustainability=obj.get("sustainability", "待观察"),
                    expectation_gap=obj.get("expectation_gap", "待观察"),
                    structure_position=obj.get("structure_position", "待观察"),
                    max_risk=obj.get("max_risk", "待观察"),
                    reversal_trigger=obj.get("reversal_trigger", "待观察"),
                    info_gaps=obj.get("info_gaps", [])[:3],
                )
                _ensure_sector_evidence(card, sector_payload)
                if len(card.evidence_chain) < 3:
                    fallback = _fallback_decision(item_with_sector)
                    card.evidence_chain = fallback.evidence_chain
                trace_by_symbol[item["symbol"]] = {"mode": "ai", "error": ""}
            except Exception as exc:
                logger.warning("Fine analyze failed for %s, use fallback: %s", item.get("symbol"), exc)
                card = _fallback_decision(item_with_sector)
                trace_by_symbol[item["symbol"]] = {"mode": "fallback", "error": str(exc)}
        cards.append(card)

    # Pure mode: no ranking, no truncation, keep original candidate order.
    ordered_cards = cards

    def _to_dict(card: DecisionCard) -> Dict:
        if hasattr(card, "model_dump"):
            return card.model_dump()
        return card.dict()

    return {
        "analysis_list": [_to_dict(c) for c in ordered_cards],
        "decision_cards": [_to_dict(c) for c in ordered_cards],
        "decision_card_5lines": {c.symbol: c.to_five_line_card() for c in ordered_cards},
        "analysis_trace": trace_by_symbol,
        "info_gaps": [{"symbol": c.symbol, "gaps": c.info_gaps} for c in ordered_cards],
    }
