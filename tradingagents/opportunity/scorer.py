"""Opportunity scoring for daily batch screening."""

from __future__ import annotations

from typing import Dict, List, Optional

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore, OpportunityScoreComponent


SCORING_PROFILE = "v1_default"
OPPORTUNITY_WEIGHTS: Dict[str, float] = {
    "market": 0.10,
    "sector": 0.20,
    "stock": 0.20,
    "structure": 0.15,
    "strategy": 0.10,
    "ai": 0.10,
    "entry_quality": 0.10,
}
RISK_PENALTY_WEIGHT = 0.15


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _component(name: str, raw_score: Optional[float], weight: float, reason: str) -> OpportunityScoreComponent:
    contribution = 0.0 if raw_score is None else round(raw_score * weight, 2)
    return OpportunityScoreComponent(
        name=name,
        weight=weight,
        raw_score=raw_score,
        contribution=contribution,
        reason=reason,
    )


def _grade(total_score: float) -> str:
    if total_score >= 85.0:
        return "S"
    if total_score >= 75.0:
        return "A"
    if total_score >= 65.0:
        return "B"
    return "C"


def _status(grade: str, risk_penalty: float) -> str:
    if risk_penalty >= 12.0 and grade in {"B", "C"}:
        return "dropped"
    if grade in {"S", "A"}:
        return "key_opportunity"
    if grade == "B":
        return "watch"
    return "low_priority"


def _score_volume_ratio(vol_ratio: float) -> float:
    if vol_ratio >= 2.5:
        return 65.0
    if vol_ratio >= 1.5:
        return 85.0
    if vol_ratio >= 1.1:
        return 75.0
    if vol_ratio >= 0.8:
        return 55.0
    return 35.0


def _stock_strength_score(item: Dict) -> tuple[float, str]:
    change_pct = _safe_float(item.get("change_pct"))
    recent_3d_change = _safe_float(item.get("recent_3d_change"))
    last_close = _safe_float(item.get("last_close"))
    ma5 = _safe_float(item.get("ma5"))
    ma10 = _safe_float(item.get("ma10"))
    ma20 = _safe_float(item.get("ma20"))
    vol_ratio = _safe_float(item.get("vol_ratio"), 1.0)

    if last_close > 0 and last_close >= ma5 >= ma10 >= ma20 > 0:
        trend_score = 88.0
        trend_reason = "price is aligned above MA5/MA10/MA20"
    elif last_close > 0 and ma10 > 0 and last_close >= ma10:
        trend_score = 70.0
        trend_reason = "price is above MA10"
    elif str(item.get("trend_label", "")) == "uptrend":
        trend_score = 65.0
        trend_reason = "trend label is uptrend"
    else:
        trend_score = 45.0
        trend_reason = "trend alignment is weak or unavailable"

    change_score = _clamp(35.0 + change_pct * 6.0)
    recent_score = _clamp(45.0 + recent_3d_change * 3.0)
    volume_score = _score_volume_ratio(vol_ratio)
    score = round(
        trend_score * 0.40
        + change_score * 0.25
        + volume_score * 0.20
        + recent_score * 0.15,
        2,
    )
    return score, f"{trend_reason}; change={round(change_pct, 2)}%, vol_ratio={round(vol_ratio, 2)}"


def _structure_score(item: Dict) -> tuple[float, List[str], str]:
    tags = set(item.get("coarse_reason_tags", []) or [])
    change_pct = _safe_float(item.get("change_pct"))
    vol_ratio = _safe_float(item.get("vol_ratio"), 1.0)
    last_close = _safe_float(item.get("last_close"))
    high = _safe_float(item.get("high"))
    ma20 = _safe_float(item.get("ma20"))
    risk_flags: List[str] = []

    score = 50.0
    reasons: List[str] = []
    if "trend_aligned" in tags:
        score += 15.0
        reasons.append("trend_aligned")
    if "volume_expansion" in tags or vol_ratio >= 1.2:
        score += 12.0
        reasons.append("volume_expansion")
    if "breakout" in tags or (high > 0 and last_close >= high * 0.995):
        score += 12.0
        reasons.append("near_breakout")
    if "high_position" in tags or (ma20 > 0 and last_close >= ma20):
        score += 8.0
        reasons.append("above_key_average")
    if change_pct >= 9.5:
        score -= 8.0
        risk_flags.append("overheat_daily_limit_like")
    if vol_ratio >= 2.8:
        score -= 6.0
        risk_flags.append("volume_spike_overheat")

    reason = ", ".join(reasons) if reasons else "basic structure only"
    return round(_clamp(score), 2), risk_flags, reason


def _strategy_score(item: Dict, sector_score: Optional[float]) -> tuple[float, str]:
    tags = set(item.get("coarse_reason_tags", []) or [])
    sector_state = str(item.get("sector_state", "unknown"))
    score = 45.0
    reasons: List[str] = []
    if sector_state == "mainline":
        score += 25.0
        reasons.append("sector mainline")
    elif sector_state == "strong":
        score += 18.0
        reasons.append("sector strong")
    elif sector_state == "watch":
        score += 10.0
        reasons.append("sector watch")
    if sector_score is not None and sector_score >= 75.0:
        score += 8.0
        reasons.append("sector score >= 75")
    if "trend_aligned" in tags:
        score += 8.0
        reasons.append("trend aligned")
    if "volume_expansion" in tags:
        score += 6.0
        reasons.append("volume expansion")
    if "concept_present" in tags:
        score += 4.0
        reasons.append("sector concept present")
    return round(_clamp(score), 2), ", ".join(reasons) if reasons else "mainline trend rules weakly matched"


def _story_payload(story_by_symbol: Dict[str, Dict], symbol: str) -> Dict:
    return (story_by_symbol.get(symbol, {}) or {}).get("story_payload", {}) or {}


def _ai_score(
    decision_card: Dict,
    story_payload: Dict,
    trace: Dict,
) -> tuple[float, List[str], List[str], str]:
    score = 55.0
    risk_flags: List[str] = []
    data_gaps: List[str] = []
    reasons: List[str] = []

    if not decision_card:
        score -= 7.0
        data_gaps.append("decision_card_missing")
        reasons.append("decision card missing")
    elif trace.get("mode") == "fallback":
        data_gaps.append("ai_analysis_fallback")
        reasons.append("fallback decision card")
    else:
        score += 5.0
        reasons.append("AI decision card available")

    evidence_count = len(decision_card.get("evidence_chain", []) or [])
    score += min(evidence_count, 3) * 4.0
    if evidence_count:
        reasons.append(f"{evidence_count} evidence item(s)")

    stage = str(decision_card.get("stage", ""))
    if stage in {"启动", "二次启动"}:
        score += 8.0
        reasons.append(f"stage={stage}")
    elif stage == "加速":
        score += 2.0
        risk_flags.append("accelerating_stage_overheat")
    elif stage == "调整":
        score -= 6.0

    heat = str(story_payload.get("story_heat_level", "")).lower()
    if heat in {"high", "strong"}:
        score += 8.0
        reasons.append("story heat high")
    elif heat in {"medium"}:
        score += 4.0
    elif heat in {"weak", "low"}:
        score -= 2.0

    if story_payload.get("is_mainline_candidate"):
        score += 5.0
        reasons.append("story marks mainline candidate")
    if story_payload.get("has_risk_alert"):
        score -= 8.0
        risk_flags.append("story_risk_alert")

    info_gaps = decision_card.get("info_gaps", []) or []
    if info_gaps:
        data_gaps.extend(str(gap) for gap in info_gaps[:5])
        score -= min(len(info_gaps) * 3.0, 12.0)

    return round(_clamp(score), 2), risk_flags, data_gaps, "; ".join(reasons) if reasons else "neutral AI/story signal"


def _entry_quality_score(decision_card: Dict, item: Dict) -> tuple[float, str]:
    stage = str(decision_card.get("stage", ""))
    reversal_trigger = str(decision_card.get("reversal_trigger", "")).strip()
    vol_ratio = _safe_float(item.get("vol_ratio"), 1.0)
    base_by_stage = {
        "二次启动": 80.0,
        "启动": 76.0,
        "调整": 62.0,
        "加速": 56.0,
    }
    score = base_by_stage.get(stage, 60.0)
    if reversal_trigger and reversal_trigger != "待观察":
        score += 8.0
    if 1.1 <= vol_ratio <= 2.2:
        score += 5.0
    elif vol_ratio >= 2.8:
        score -= 6.0
    return round(_clamp(score), 2), f"stage={stage or 'unknown'}, has_reversal_trigger={bool(reversal_trigger)}"


def _risk_raw_score(
    item: Dict,
    decision_card: Dict,
    story_payload: Dict,
    structural_risk_flags: List[str],
    ai_risk_flags: List[str],
) -> tuple[float, List[str]]:
    flags = list(dict.fromkeys(structural_risk_flags + ai_risk_flags))
    risk_text = " ".join(
        [
            str(decision_card.get("max_risk", "")),
            str(decision_card.get("sustainability", "")),
            str(decision_card.get("expectation_gap", "")),
        ]
    )
    score = 20.0
    if _safe_float(item.get("change_pct")) >= 9.5:
        score += 20.0
    if "风险" in risk_text or "回撤" in risk_text:
        score += 12.0
    if "兑现" in risk_text or "退潮" in risk_text:
        score += 10.0
    if story_payload.get("has_risk_alert"):
        score += 18.0
    if len(decision_card.get("info_gaps", []) or []) >= 2:
        score += 8.0
    if _safe_float(item.get("sector_score"), 50.0) < 60.0:
        score += 8.0
        flags.append("weak_sector_context")
    return round(_clamp(score), 2), flags


def score_opportunities(
    trade_date: str,
    market_environment: MarketEnvironment,
    candidates: List[Dict],
    decision_cards: List[Dict],
    story_by_symbol: Optional[Dict[str, Dict]] = None,
    analysis_trace: Optional[Dict[str, Dict]] = None,
) -> List[OpportunityScore]:
    """Score candidates into S/A/B/C opportunities without requiring live AI."""
    card_by_symbol = {str(card.get("symbol", "")): card for card in decision_cards}
    story_by_symbol = story_by_symbol or {}
    analysis_trace = analysis_trace or {}

    market_raw = market_environment.market_score if market_environment.market_score is not None else 50.0
    opportunities: List[OpportunityScore] = []

    for item in candidates:
        symbol = str(item.get("symbol", ""))
        if not symbol:
            continue
        card = card_by_symbol.get(symbol, {})
        story_payload = _story_payload(story_by_symbol, symbol)
        trace = analysis_trace.get(symbol, {})

        sector_raw = item.get("sector_score")
        sector_score = _safe_float(sector_raw, 45.0) if sector_raw is not None else 45.0
        stock_score, stock_reason = _stock_strength_score(item)
        structure_score, structural_risk_flags, structure_reason = _structure_score(item)
        strategy_score, strategy_reason = _strategy_score(item, sector_score)
        ai_score, ai_risk_flags, ai_data_gaps, ai_reason = _ai_score(card, story_payload, trace)
        entry_score, entry_reason = _entry_quality_score(card, item)
        risk_raw, risk_flags = _risk_raw_score(item, card, story_payload, structural_risk_flags, ai_risk_flags)
        risk_penalty = round(risk_raw * RISK_PENALTY_WEIGHT, 2)

        components = [
            _component("market", market_raw, OPPORTUNITY_WEIGHTS["market"], market_environment.market_state),
            _component("sector", sector_score, OPPORTUNITY_WEIGHTS["sector"], str(item.get("sector_state", "unknown"))),
            _component("stock", stock_score, OPPORTUNITY_WEIGHTS["stock"], stock_reason),
            _component("structure", structure_score, OPPORTUNITY_WEIGHTS["structure"], structure_reason),
            _component("strategy", strategy_score, OPPORTUNITY_WEIGHTS["strategy"], strategy_reason),
            _component("ai", ai_score, OPPORTUNITY_WEIGHTS["ai"], ai_reason),
            _component("entry_quality", entry_score, OPPORTUNITY_WEIGHTS["entry_quality"], entry_reason),
        ]
        total_score = round(_clamp(sum(c.contribution for c in components) - risk_penalty), 2)
        grade = _grade(total_score)

        data_gaps = list(dict.fromkeys((item.get("sector_score_data_gaps", []) or []) + ai_data_gaps))
        if market_environment.data_gaps:
            data_gaps.extend(gap for gap in market_environment.data_gaps if gap not in data_gaps)

        opportunities.append(
            OpportunityScore(
                trade_date=trade_date,
                symbol=symbol,
                name=str(item.get("name", "")),
                sector=str(item.get("sector", item.get("industry", "")) or "unknown_sector"),
                sector_adapter=str(item.get("sector_adapter", "industry")),
                strategy_type="mainline_trend",
                scoring_profile=SCORING_PROFILE,
                total_score=total_score,
                grade=grade,
                status=_status(grade, risk_penalty),
                market_score_component=components[0].contribution,
                sector_score_component=components[1].contribution,
                stock_score_component=components[2].contribution,
                structure_score_component=components[3].contribution,
                strategy_score_component=components[4].contribution,
                ai_score_component=components[5].contribution,
                entry_quality_component=components[6].contribution,
                risk_penalty=risk_penalty,
                components=components,
                risk_flags=list(dict.fromkeys(risk_flags)),
                data_gaps=data_gaps,
                rank_reason=(
                    f"market={market_raw}, sector={round(sector_score, 2)}, "
                    f"stock={stock_score}, structure={structure_score}, risk_penalty={risk_penalty}"
                ),
                source_refs={
                    "market": "M_market_environment.json",
                    "sector": "B_sector_calibration.json",
                    "decision_card": "C_ai_analysis_with_cards.json",
                    "story": "B_story_analysis.json",
                },
            )
        )

    opportunities.sort(key=lambda item: item.total_score, reverse=True)
    return opportunities
