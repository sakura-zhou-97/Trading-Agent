"""Coarse screening rules based on raw market features."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional


DEFAULT_RULEBOOK: Dict = {
    "weights": {
        "position_score": 0.20,
        "trend_score": 0.20,
        "volume_score": 0.20,
        "breakout_score": 0.15,
        "style_score": 0.10,
        "concept_score": 0.15,
    },
    "hard_filters": {
        "min_change_pct": 5.0,
        "exclude_st": True,
        "main_board_only": True,
    },
}


@dataclass
class CoarseResult:
    candidates: List[Dict]
    dropped: List[Dict]


def load_rulebook(rulebook_path: Optional[str] = None) -> Dict:
    """Load rulebook from YAML file; fallback to DEFAULT_RULEBOOK."""
    path = Path(rulebook_path) if rulebook_path else Path(__file__).with_name("rulebook_mvp.yaml")
    if not path.exists():
        return DEFAULT_RULEBOOK
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            return DEFAULT_RULEBOOK
        merged = {
            "weights": dict(DEFAULT_RULEBOOK["weights"]),
            "hard_filters": dict(DEFAULT_RULEBOOK["hard_filters"]),
        }
        merged["weights"].update(loaded.get("weights", {}) or {})
        merged["hard_filters"].update(loaded.get("hard_filters", {}) or {})
        return merged
    except Exception:
        return DEFAULT_RULEBOOK


def hard_filter(item: Dict, rulebook: Dict) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    min_change = float(rulebook["hard_filters"]["min_change_pct"])
    if float(item.get("change_pct", 0.0)) <= min_change:
        reasons.append("change_pct_below_threshold")
    if bool(rulebook["hard_filters"].get("exclude_st", True)) and bool(item.get("is_st", False)):
        reasons.append("st_excluded")
    if bool(rulebook["hard_filters"].get("main_board_only", True)):
        # Universe provider already filters this. Keep this tag for explicitness.
        if not item.get("symbol", "").startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
            reasons.append("not_main_board")
    return len(reasons) == 0, reasons


def build_raw_tags(item: Dict) -> List[str]:
    last_close = float(item.get("last_close", 0.0))
    ma5 = float(item.get("ma5", 0.0))
    ma10 = float(item.get("ma10", 0.0))
    ma20 = float(item.get("ma20", 0.0))
    vol_ratio = float(item.get("vol_ratio", 0.0))
    change_pct = float(item.get("change_pct", 0.0))
    high = float(item.get("high", 0.0))
    industry = str(item.get("industry", "")).strip()
    tags: List[str] = []
    if high > 0 and last_close >= high * 0.995:
        tags.append("breakout")
    if vol_ratio >= 1.2:
        tags.append("volume_expansion")
    if last_close > 0 and last_close > ma5 >= ma10 >= ma20:
        tags.append("trend_aligned")
    if last_close >= ma20 and change_pct >= 5.0:
        tags.append("high_position")
    if industry:
        tags.append("concept_present")
    if not tags:
        tags.append("basic_structure")
    return tags


def run_coarse_screen(
    records: List[Dict],
    top_n: int = 30,
    rulebook: Optional[Dict] = None,
) -> CoarseResult:
    rb = rulebook or DEFAULT_RULEBOOK
    kept: List[Dict] = []
    dropped: List[Dict] = []
    for item in records:
        ok, drop_reasons = hard_filter(item, rb)
        if not ok:
            dropped.append({**item, "drop_reasons": drop_reasons})
            continue
        tags = build_raw_tags(item)
        sanitized = dict(item)
        for key in [
            "position_score",
            "trend_score",
            "volume_score",
            "breakout_score",
            "style_score",
            "structural_score",
        ]:
            sanitized.pop(key, None)
        kept.append(
            {
                **sanitized,
                "coarse_reason_tags": tags,
            }
        )

    # Pure mode: no ranking and no top-N truncation.
    _ = top_n
    return CoarseResult(candidates=kept, dropped=dropped)
