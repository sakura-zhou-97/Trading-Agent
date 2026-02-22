"""Sector-level validation and score calibration."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List


def _norm_sector(item: Dict) -> str:
    industry = str(item.get("industry", "")).strip()
    return industry if industry else "unknown_sector"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def calibrate_with_sector(analysis_list: List[Dict], all_candidates: List[Dict]) -> Dict:
    """Calibrate per-stock score by sector momentum and resonance."""
    sector_bucket: Dict[str, List[Dict]] = defaultdict(list)
    for item in all_candidates:
        sector_bucket[_norm_sector(item)].append(item)

    sector_stats: Dict[str, Dict] = {}
    for sector, items in sector_bucket.items():
        if not items:
            continue
        day_strength = sum(float(i.get("change_pct", 0.0)) for i in items) / len(items)
        trend_3d = sum(float(i.get("recent_3d_change", 0.0)) for i in items) / len(items)
        leader = max(items, key=lambda x: float(x.get("change_pct", 0.0)))
        leader_symbol = leader.get("symbol", "")
        leader_change = float(leader.get("change_pct", 0.0))
        leader_3d = float(leader.get("recent_3d_change", 0.0))
        if day_strength >= 6 and leader_3d >= 8:
            leader_status = "强"
        elif day_strength >= 3:
            leader_status = "分歧"
        else:
            leader_status = "退潮"
        # Momentum factor derived from raw returns only.
        momentum = _clamp(1.0 + day_strength / 100.0 + trend_3d / 200.0, 0.85, 1.15)
        sector_stats[sector] = {
            "day_strength": round(day_strength, 3),
            "trend_3d": round(trend_3d, 3),
            "momentum_factor": round(momentum, 4),
            "leader_symbol": leader_symbol,
            "leader_change_pct": round(leader_change, 3),
            "leader_recent_3d_change": round(leader_3d, 3),
            "leader_status": leader_status,
        }

    calibrated: List[Dict] = []
    for item in analysis_list:
        sector = _norm_sector(item)
        s = sector_stats.get(sector, {"momentum_factor": 1.0, "day_strength": 0.0, "trend_3d": 0.0})
        multiplier = _clamp(float(s["momentum_factor"]), 0.85, 1.15)
        calibrated.append(
            {
                **item,
                "sector": sector,
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
        "calibrated_analysis_list": calibrated,
    }
