"""Sector-level validation and score calibration."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from tradingagents.sector.schemas import SectorScore


SECTOR_SCORE_WEIGHTS: Dict[str, float] = {
    "short_term_return_score": 0.25,
    "relative_strength_score": 0.20,
    "turnover_expansion_score": 0.20,
    "breadth_score": 0.15,
    "limit_up_score": 0.10,
    "persistence_score": 0.10,
}


def _norm_sector(item: Dict) -> str:
    industry = str(item.get("industry", "")).strip()
    return industry if industry else "unknown_sector"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _weighted_average(scores: Iterable[tuple[Optional[float], float]]) -> Optional[float]:
    weighted_sum = 0.0
    weight_sum = 0.0
    for score, weight in scores:
        if score is None:
            continue
        weighted_sum += score * weight
        weight_sum += weight
    if weight_sum <= 0:
        return None
    return round(weighted_sum / weight_sum, 2)


def _score_return(change_pct: float) -> float:
    if change_pct >= 8.0:
        return 90.0
    if change_pct >= 6.0:
        return 78.0
    if change_pct >= 4.0:
        return 65.0
    if change_pct >= 2.0:
        return 52.0
    if change_pct > 0:
        return 42.0
    return 25.0


def _score_persistence(recent_3d_change: float) -> float:
    if recent_3d_change >= 12.0:
        return 90.0
    if recent_3d_change >= 8.0:
        return 78.0
    if recent_3d_change >= 4.0:
        return 64.0
    if recent_3d_change >= 0:
        return 45.0
    return 25.0


def _score_breadth(count: int, max_count: int) -> float:
    if count <= 0 or max_count <= 0:
        return 25.0
    ratio_score = 35.0 + (count / max_count) * 45.0
    absolute_score = min(20.0, count * 4.0)
    return round(_clamp(ratio_score + absolute_score, 25.0, 100.0), 2)


def _score_limit_count(limit_like_count: int) -> float:
    if limit_like_count >= 4:
        return 90.0
    if limit_like_count == 3:
        return 80.0
    if limit_like_count == 2:
        return 70.0
    if limit_like_count == 1:
        return 55.0
    return 35.0


def _score_turnover(total_amount: float, max_total_amount: float) -> Optional[float]:
    if total_amount <= 0 or max_total_amount <= 0:
        return None
    return round(_clamp(35.0 + (total_amount / max_total_amount) * 55.0, 35.0, 100.0), 2)


def _sector_state(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 80.0:
        return "mainline"
    if score >= 70.0:
        return "strong"
    if score >= 60.0:
        return "watch"
    return "weak"


def _score_to_dict(score: SectorScore) -> Dict:
    if hasattr(score, "model_dump"):
        return score.model_dump()
    return score.dict()


def score_sector_context(all_candidates: List[Dict]) -> List[SectorScore]:
    """Build explicit sector scores from the currently available candidate data.

    V1 uses the industry field as the sector adapter. Several PRD dimensions
    require broader market baselines that are not available here, so those
    dimensions are conservative fallback approximations and expose data gaps.
    """
    sector_bucket: Dict[str, List[Dict]] = defaultdict(list)
    for item in all_candidates:
        sector_bucket[_norm_sector(item)].append(item)

    max_count = max((len(items) for items in sector_bucket.values()), default=0)
    total_amount_by_sector = {
        sector: sum(_safe_float(item.get("amount")) for item in items)
        for sector, items in sector_bucket.items()
    }
    max_total_amount = max(total_amount_by_sector.values(), default=0.0)

    scores: List[SectorScore] = []
    for sector, items in sector_bucket.items():
        if not items:
            continue

        sector_count = len(items)
        day_strength = sum(_safe_float(item.get("change_pct")) for item in items) / sector_count
        trend_3d = sum(_safe_float(item.get("recent_3d_change")) for item in items) / sector_count
        limit_like_count = sum(1 for item in items if _safe_float(item.get("change_pct")) >= 9.5)
        total_amount = total_amount_by_sector.get(sector, 0.0)
        leader = max(items, key=lambda x: _safe_float(x.get("change_pct")))

        short_term_return_score = _score_return(day_strength)
        relative_strength_score = short_term_return_score
        turnover_expansion_score = _score_turnover(total_amount, max_total_amount)
        breadth_score = _score_breadth(sector_count, max_count)
        limit_up_score = _score_limit_count(limit_like_count)
        persistence_score = _score_persistence(trend_3d)

        sector_score = _weighted_average(
            [
                (short_term_return_score, SECTOR_SCORE_WEIGHTS["short_term_return_score"]),
                (relative_strength_score, SECTOR_SCORE_WEIGHTS["relative_strength_score"]),
                (turnover_expansion_score, SECTOR_SCORE_WEIGHTS["turnover_expansion_score"]),
                (breadth_score, SECTOR_SCORE_WEIGHTS["breadth_score"]),
                (limit_up_score, SECTOR_SCORE_WEIGHTS["limit_up_score"]),
                (persistence_score, SECTOR_SCORE_WEIGHTS["persistence_score"]),
            ]
        )

        data_gaps = [
            "index_relative_strength_baseline_missing",
            "sector_turnover_expansion_baseline_missing",
        ]
        reasons = [
            f"Sector has {sector_count} candidate(s).",
            f"Average daily change is {round(day_strength, 2)}%.",
            f"Average recent 3-day change is {round(trend_3d, 2)}%.",
        ]
        if turnover_expansion_score is None:
            data_gaps.append("same_day_sector_amount_missing")
            reasons.append("Turnover expansion score is unavailable because amount data is missing.")
        else:
            reasons.append("Turnover score is approximated by same-day sector amount concentration.")

        if sector == "unknown_sector" and sector_score is not None:
            sector_score = min(sector_score, 55.0)
            data_gaps.append("sector_adapter_field_missing")
            reasons.append("Unknown sector is capped conservatively.")

        scores.append(
            SectorScore(
                sector=sector,
                sector_adapter="industry",
                sector_score=sector_score,
                sector_state=_sector_state(sector_score),
                sector_count=sector_count,
                short_term_return_score=short_term_return_score,
                relative_strength_score=relative_strength_score,
                turnover_expansion_score=turnover_expansion_score,
                breadth_score=breadth_score,
                limit_up_score=limit_up_score,
                persistence_score=persistence_score,
                leader_symbol=str(leader.get("symbol", "")),
                leader_status="",
                reasons=reasons,
                data_gaps=data_gaps,
            )
        )

    scores.sort(
        key=lambda x: (
            x.sector_score if x.sector_score is not None else -1.0,
            x.sector_count,
        ),
        reverse=True,
    )
    for idx, score in enumerate(scores, start=1):
        score.sector_rank = idx
    return scores


def calibrate_with_sector(analysis_list: List[Dict], all_candidates: List[Dict]) -> Dict:
    """Calibrate per-stock score by sector momentum and resonance."""
    sector_bucket: Dict[str, List[Dict]] = defaultdict(list)
    for item in all_candidates:
        sector_bucket[_norm_sector(item)].append(item)

    sector_scores = score_sector_context(all_candidates)
    sector_score_by_name = {score.sector: score for score in sector_scores}

    sector_stats: Dict[str, Dict] = {}
    for sector, items in sector_bucket.items():
        if not items:
            continue
        day_strength = sum(_safe_float(i.get("change_pct")) for i in items) / len(items)
        trend_3d = sum(_safe_float(i.get("recent_3d_change")) for i in items) / len(items)
        leader = max(items, key=lambda x: _safe_float(x.get("change_pct")))
        leader_symbol = leader.get("symbol", "")
        leader_change = _safe_float(leader.get("change_pct"))
        leader_3d = _safe_float(leader.get("recent_3d_change"))
        if day_strength >= 6 and leader_3d >= 8:
            leader_status = "强"
        elif day_strength >= 3:
            leader_status = "分歧"
        else:
            leader_status = "退潮"
        # Momentum factor derived from raw returns only.
        momentum = _clamp(1.0 + day_strength / 100.0 + trend_3d / 200.0, 0.85, 1.15)
        sector_score = sector_score_by_name.get(sector)
        if sector_score is not None:
            sector_score.leader_status = leader_status
        sector_stats[sector] = {
            "day_strength": round(day_strength, 3),
            "trend_3d": round(trend_3d, 3),
            "momentum_factor": round(momentum, 4),
            "leader_symbol": leader_symbol,
            "leader_change_pct": round(leader_change, 3),
            "leader_recent_3d_change": round(leader_3d, 3),
            "leader_status": leader_status,
            "sector_adapter": sector_score.sector_adapter if sector_score else "industry",
            "sector_score": sector_score.sector_score if sector_score else None,
            "sector_state": sector_score.sector_state if sector_score else "unknown",
            "sector_rank": sector_score.sector_rank if sector_score else None,
            "sector_count": sector_score.sector_count if sector_score else len(items),
            "short_term_return_score": sector_score.short_term_return_score if sector_score else None,
            "relative_strength_score": sector_score.relative_strength_score if sector_score else None,
            "turnover_expansion_score": sector_score.turnover_expansion_score if sector_score else None,
            "breadth_score": sector_score.breadth_score if sector_score else None,
            "limit_up_score": sector_score.limit_up_score if sector_score else None,
            "persistence_score": sector_score.persistence_score if sector_score else None,
            "data_gaps": sector_score.data_gaps if sector_score else [],
        }

    calibrated: List[Dict] = []
    for item in analysis_list:
        sector = _norm_sector(item)
        s = sector_stats.get(sector, {"momentum_factor": 1.0, "day_strength": 0.0, "trend_3d": 0.0})
        multiplier = _clamp(float(s["momentum_factor"]), 0.85, 1.15)
        sector_score = sector_score_by_name.get(sector)
        calibrated.append(
            {
                **item,
                "sector": sector,
                "sector_adapter": sector_score.sector_adapter if sector_score else "industry",
                "sector_score": sector_score.sector_score if sector_score else None,
                "sector_state": sector_score.sector_state if sector_score else "unknown",
                "sector_rank": sector_score.sector_rank if sector_score else None,
                "sector_count": sector_score.sector_count if sector_score else 0,
                "sector_score_reasons": sector_score.reasons if sector_score else [],
                "sector_score_data_gaps": sector_score.data_gaps if sector_score else [],
                "sector_day_strength": s["day_strength"],
                "sector_trend_3d": s["trend_3d"],
                "sector_leader_symbol": s.get("leader_symbol", ""),
                "sector_leader_status": s.get("leader_status", "分歧"),
                "sector_multiplier": round(multiplier, 4),
                "calibration_reason": (
                    "板块走强，上调评估" if multiplier > 1.0 else "板块偏弱，下调评估" if multiplier < 1.0 else "板块中性"
                ),
            }
        )

    return {
        "sector_stats": sector_stats,
        "sector_scores": [_score_to_dict(score) for score in sector_scores],
        "calibrated_analysis_list": calibrated,
    }
