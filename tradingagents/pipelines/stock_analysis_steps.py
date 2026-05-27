"""Reusable step helpers for the stock analysis pipeline."""

from __future__ import annotations

from typing import Dict, List


def build_sector_context_by_symbol(calibrated_rows: List[Dict]) -> Dict[str, Dict]:
    return {
        str(row.get("symbol", "")): {
            "sector": row.get("sector", ""),
            "sector_adapter": row.get("sector_adapter", "industry"),
            "sector_score": row.get("sector_score"),
            "sector_state": row.get("sector_state"),
            "sector_rank": row.get("sector_rank"),
            "sector_count": row.get("sector_count"),
            "sector_day_strength": row.get("sector_day_strength"),
            "sector_trend_3d": row.get("sector_trend_3d"),
            "sector_multiplier": row.get("sector_multiplier"),
            "sector_leader_symbol": row.get("sector_leader_symbol", ""),
            "sector_leader_status": row.get("sector_leader_status", ""),
            "calibration_reason": row.get("calibration_reason", ""),
        }
        for row in calibrated_rows
    }


def build_theme_heatmap(top_candidates: List[Dict], decision_cards: List[Dict]) -> Dict:
    sector_count: Dict[str, int] = {}
    sector_change_sum: Dict[str, float] = {}
    for item in top_candidates:
        sector = str(item.get("industry", "")).strip() or "unknown_sector"
        sector_count[sector] = sector_count.get(sector, 0) + 1
        sector_change_sum[sector] = sector_change_sum.get(sector, 0.0) + float(item.get("change_pct", 0.0))

    story_tags = {"risk_alert": 0, "theme_hot": 0, "breakout": 0}
    for card in decision_cards:
        text = " ".join(
            [
                str(card.get("tradability", "")),
                str(card.get("sustainability", "")),
                str(card.get("expectation_gap", "")),
                " ".join(card.get("evidence_chain", []) or []),
            ]
        )
        if any(key in text for key in ["风险", "回撤", "兑现"]):
            story_tags["risk_alert"] += 1
        if any(key in text for key in ["主线", "龙头", "题材", "催化"]):
            story_tags["theme_hot"] += 1
        if any(key in text for key in ["突破", "涨停", "加速"]):
            story_tags["breakout"] += 1

    sectors = []
    for sector, count in sector_count.items():
        avg_change = sector_change_sum[sector] / max(count, 1)
        sectors.append({"sector": sector, "count": count, "avg_change_pct": round(avg_change, 3)})
    sectors.sort(key=lambda x: (x["count"], x["avg_change_pct"]), reverse=True)
    return {
        "top_sectors": sectors[:10],
        "story_tag_stats": story_tags,
    }
