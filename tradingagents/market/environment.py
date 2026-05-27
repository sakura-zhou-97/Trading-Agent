"""Build market environment summaries from available screening data."""

from __future__ import annotations

from statistics import mean
from typing import Dict, Iterable, List, Optional

from tradingagents.market.schemas import MarketEnvironment, MarketScoreComponent


COMPONENT_WEIGHTS: Dict[str, float] = {
    "index_trend": 0.25,
    "breadth": 0.25,
    "turnover": 0.15,
    "limit_sentiment": 0.20,
    "risk_appetite": 0.15,
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_count(count: int) -> float:
    if count >= 150:
        return 85.0
    if count >= 80:
        return 72.0
    if count >= 30:
        return 58.0
    if count >= 10:
        return 42.0
    if count > 0:
        return 28.0
    return 10.0


def _score_average_change(avg_change_pct: float) -> float:
    if avg_change_pct >= 9.0:
        return 85.0
    if avg_change_pct >= 7.0:
        return 70.0
    if avg_change_pct >= 5.0:
        return 55.0
    if avg_change_pct > 0:
        return 35.0
    return 10.0


def _score_limit_sentiment(records: List[Dict]) -> float:
    if not records:
        return 10.0
    limit_like_count = sum(1 for item in records if _safe_float(item.get("change_pct")) >= 9.5)
    limit_ratio = limit_like_count / max(len(records), 1)
    count_score = min(100.0, 20.0 + limit_like_count * 4.0)
    ratio_score = min(100.0, 30.0 + limit_ratio * 80.0)
    return round((count_score * 0.5) + (ratio_score * 0.5), 2)


def _weighted_score(components: Iterable[MarketScoreComponent]) -> Optional[float]:
    weighted_sum = 0.0
    weight_sum = 0.0
    for component in components:
        if component.score is None:
            continue
        weighted_sum += component.score * component.weight
        weight_sum += component.weight
    if weight_sum <= 0:
        return None
    return round(weighted_sum / weight_sum, 2)


def _market_state(score: Optional[float], strong_count: int) -> str:
    if score is None:
        return "unknown"
    if strong_count == 0:
        return "defensive"
    if score >= 75:
        return "attack"
    if score >= 55:
        return "normal"
    if score >= 40:
        return "cautious"
    return "defensive"


def _allowed_action(market_state: str) -> str:
    if market_state in {"attack", "normal"}:
        return "normal"
    if market_state == "cautious":
        return "light"
    if market_state == "defensive":
        return "no_new_position"
    return "unknown"


def build_market_environment(
    trade_date: str,
    universe: List[Dict],
    candidates: Optional[List[Dict]] = None,
) -> MarketEnvironment:
    """Build a conservative market environment from the data currently available.

    The current screening universe is already filtered to strong daily movers, so
    breadth and sentiment are fallback indicators rather than full-market facts.
    """
    candidates = candidates or []
    strong_count = len(universe)
    candidate_count = len(candidates)
    changes = [_safe_float(item.get("change_pct")) for item in universe]
    avg_change_pct = mean(changes) if changes else 0.0

    breadth_score = _score_count(strong_count)
    limit_sentiment_score = _score_limit_sentiment(universe)
    risk_appetite_score = round(
        (_score_count(candidate_count) * 0.55) + (_score_average_change(avg_change_pct) * 0.45),
        2,
    )

    components = [
        MarketScoreComponent(
            name="index_trend",
            weight=COMPONENT_WEIGHTS["index_trend"],
            score=None,
            status="missing",
            reason="Index trend data is not available in the current screening payload.",
        ),
        MarketScoreComponent(
            name="breadth",
            weight=COMPONENT_WEIGHTS["breadth"],
            score=breadth_score,
            status="fallback",
            reason=f"{strong_count} records passed the daily strength universe filter.",
        ),
        MarketScoreComponent(
            name="turnover",
            weight=COMPONENT_WEIGHTS["turnover"],
            score=None,
            status="missing",
            reason="Full-market turnover baseline is not available yet.",
        ),
        MarketScoreComponent(
            name="limit_sentiment",
            weight=COMPONENT_WEIGHTS["limit_sentiment"],
            score=limit_sentiment_score,
            status="fallback",
            reason="Approximated with records whose daily change is at least 9.5%.",
        ),
        MarketScoreComponent(
            name="risk_appetite",
            weight=COMPONENT_WEIGHTS["risk_appetite"],
            score=risk_appetite_score,
            status="fallback",
            reason=f"{candidate_count} candidates remained after coarse structure filtering.",
        ),
    ]
    score = _weighted_score(components)
    state = _market_state(score, strong_count)

    data_gaps = [
        "index_trend_missing",
        "full_market_turnover_baseline_missing",
        "full_market_breadth_missing",
    ]
    reasons = [
        f"Strong universe count: {strong_count}.",
        f"Coarse candidate count: {candidate_count}.",
        f"Average strong-universe change: {round(avg_change_pct, 2)}%.",
    ]
    if state == "defensive":
        reasons.append("Defensive market state blocks new position plans.")

    return MarketEnvironment(
        trade_date=trade_date,
        market_score=score,
        market_state=state,
        allowed_action=_allowed_action(state),
        index_trend_score=None,
        breadth_score=breadth_score,
        turnover_score=None,
        limit_sentiment_score=limit_sentiment_score,
        risk_appetite_score=risk_appetite_score,
        components=components,
        reasons=reasons,
        data_gaps=data_gaps,
    )
