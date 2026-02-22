"""Three-day tracker for selected stocks."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from tradingagents.dataflows.china import china_provider


@dataclass
class TrackingMetric:
    symbol: str
    name: str
    source_trade_date: str
    source_close: float
    t1_return_pct: Optional[float]
    t2_return_pct: Optional[float]
    t3_return_pct: Optional[float]
    mdd_3d_pct: Optional[float]
    reason_t1: str
    reason_t2: str
    reason_t3: str
    reason_tags_t1: List[str]
    reason_tags_t2: List[str]
    reason_tags_t3: List[str]
    should_remove: bool
    remove_reason: str
    decision_stage: str
    decision_conclusion_type: str
    decision_evidence_chain: List[str]
    decision_info_gaps: List[str]


def _parse_csv(raw: str) -> pd.DataFrame:
    lines = [line for line in raw.splitlines() if not line.strip().startswith("#")]
    payload = "\n".join(lines).strip()
    if not payload:
        return pd.DataFrame()
    df = pd.read_csv(StringIO(payload))
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date")
    return df


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _pct_change(base: float, val: float) -> Optional[float]:
    if base <= 0:
        return None
    return round((val / base - 1.0) * 100.0, 3)


def _reason_from_return(r: Optional[float]) -> str:
    if r is None:
        return "数据不足"
    if r >= 3:
        return "上涨: 动能延续"
    if r > 0:
        return "上涨: 温和跟涨"
    if r <= -5:
        return "下跌: 情绪退潮/资金兑现"
    return "震荡回撤"


def _reason_from_signals(
    ret_pct: Optional[float],
    day_close: Optional[float],
    prev_close: float,
    day_volume: Optional[float],
    prev_volume: float,
) -> tuple[str, List[str]]:
    """Build richer reason string and tags from price/volume behavior."""
    if ret_pct is None:
        return "数据不足", ["data_insufficient"]

    tags: List[str] = []
    vol_ratio = None
    if day_volume is not None and prev_volume > 0:
        vol_ratio = float(day_volume) / prev_volume
        if vol_ratio >= 1.3:
            tags.append("volume_expand")
        elif vol_ratio <= 0.8:
            tags.append("volume_shrink")

    if ret_pct >= 5:
        tags.append("strong_up")
        reason = "上涨: 资金推动+趋势延续"
    elif ret_pct > 0:
        tags.append("mild_up")
        reason = "上涨: 温和修复"
    elif ret_pct <= -8:
        tags.append("sharp_down")
        reason = "下跌: 快速兑现/风险释放"
    elif ret_pct <= -3:
        tags.append("pullback")
        reason = "下跌: 情绪退潮+回撤"
    else:
        tags.append("sideways")
        reason = "震荡: 多空分歧"

    if day_close is not None and prev_close > 0:
        close_ratio = float(day_close) / prev_close
        if close_ratio >= 1.03:
            tags.append("price_breakout")
        elif close_ratio <= 0.97:
            tags.append("price_breakdown")

    if vol_ratio is not None:
        reason += f" (量比≈{vol_ratio:.2f})"

    return reason, tags


def _compute_mdd(base: float, closes: List[float]) -> Optional[float]:
    if base <= 0 or not closes:
        return None
    min_close = min(closes)
    return round((min_close / base - 1.0) * 100.0, 3)


def _next_dates(df: pd.DataFrame, source_date: str, n: int = 3) -> List[pd.Series]:
    if df.empty or "Date" not in df.columns:
        return []
    src = pd.to_datetime(source_date)
    return [row for _, row in df[df["Date"] > src].head(n).iterrows()]


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_screener_dates(results_dir: str, max_date: str) -> List[str]:
    root = Path(results_dir) / "screener"
    if not root.exists():
        return []
    dates: List[str] = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        try:
            datetime.strptime(p.name, "%Y-%m-%d")
            if p.name <= max_date:
                dates.append(p.name)
        except ValueError:
            continue
    return sorted(dates)


def load_tracking_targets(results_dir: str, trade_date: str, lookback_days: int = 3) -> List[Dict]:
    """Load union of selected symbols from T-1/T-2/T-3 screener outputs."""
    dates = _iter_screener_dates(results_dir, trade_date)
    if not dates:
        return []
    # Exclude current trade_date to respect T-1/T-2/T-3
    prev_dates = [d for d in dates if d < trade_date][-lookback_days:]
    targets_map: Dict[str, Dict] = {}
    for d in prev_dates:
        b_path = Path(results_dir) / "screener" / d / "C_ai_analysis_with_cards.json"
        c_path = Path(results_dir) / "screener" / d / "B_sector_calibration.json"
        if not c_path.exists():
            continue
        b_map: Dict[str, Dict] = {}
        if b_path.exists():
            b_obj = _load_json(b_path)
            for dc in b_obj.get("decision_cards", []):
                b_map[str(dc.get("symbol", "")).strip()] = dc
        obj = _load_json(c_path)
        for item in obj.get("calibrated_analysis_list", []):
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            key = f"{symbol}:{d}"
            targets_map[key] = {
                "symbol": symbol,
                "name": item.get("name", ""),
                "source_trade_date": d,
                "decision_snapshot": item,
                "decision_card": b_map.get(symbol, {}),
            }
    return list(targets_map.values())


def track_three_day_metrics(targets: List[Dict]) -> List[Dict]:
    metrics: List[Dict] = []
    for target in targets:
        symbol = target["symbol"]
        source_date = target["source_trade_date"]
        start = source_date
        end = (datetime.strptime(source_date, "%Y-%m-%d") + timedelta(days=10)).strftime("%Y-%m-%d")
        try:
            raw = china_provider.get_china_stock_data(symbol, start, end)
            df = _parse_csv(raw)
        except Exception:
            df = pd.DataFrame()

        source_close = 0.0
        source_volume = 0.0
        if not df.empty and "Date" in df.columns:
            src_rows = df[df["Date"] == pd.to_datetime(source_date)]
            if not src_rows.empty:
                source_close = _safe_float(src_rows.iloc[-1].get("Close"))
                source_volume = _safe_float(src_rows.iloc[-1].get("Volume"))
            else:
                # fallback to first row as reference when source day missing
                source_close = _safe_float(df.iloc[0].get("Close"))
                source_volume = _safe_float(df.iloc[0].get("Volume"))

        rows = _next_dates(df, source_date, n=3)
        closes = [_safe_float(r.get("Close")) for r in rows]
        vols = [_safe_float(r.get("Volume")) for r in rows]

        t1 = _pct_change(source_close, closes[0]) if len(closes) >= 1 else None
        t2 = _pct_change(source_close, closes[1]) if len(closes) >= 2 else None
        t3 = _pct_change(source_close, closes[2]) if len(closes) >= 3 else None
        mdd = _compute_mdd(source_close, closes)

        r1, tags1 = _reason_from_signals(
            t1,
            closes[0] if len(closes) >= 1 else None,
            source_close,
            vols[0] if len(vols) >= 1 else None,
            source_volume,
        )
        r2, tags2 = _reason_from_signals(
            t2,
            closes[1] if len(closes) >= 2 else None,
            closes[0] if len(closes) >= 1 else source_close,
            vols[1] if len(vols) >= 2 else None,
            vols[0] if len(vols) >= 1 else source_volume,
        )
        r3, tags3 = _reason_from_signals(
            t3,
            closes[2] if len(closes) >= 3 else None,
            closes[1] if len(closes) >= 2 else (closes[0] if len(closes) >= 1 else source_close),
            vols[2] if len(vols) >= 3 else None,
            vols[1] if len(vols) >= 2 else (vols[0] if len(vols) >= 1 else source_volume),
        )

        # remove rule: big drop or 2 consecutive down days
        consecutive_down = False
        if len(closes) >= 2:
            consecutive_down = closes[0] < source_close and closes[1] < closes[0]
        big_drop = (mdd is not None and mdd <= -8.0)
        should_remove = bool(big_drop or consecutive_down)
        remove_reason = "3天内大跌" if big_drop else "连续下跌" if consecutive_down else ""

        metric = TrackingMetric(
            symbol=symbol,
            name=target.get("name", ""),
            source_trade_date=source_date,
            source_close=round(source_close, 3),
            t1_return_pct=t1,
            t2_return_pct=t2,
            t3_return_pct=t3,
            mdd_3d_pct=mdd,
            reason_t1=r1,
            reason_t2=r2,
            reason_t3=r3,
            reason_tags_t1=tags1,
            reason_tags_t2=tags2,
            reason_tags_t3=tags3,
            should_remove=should_remove,
            remove_reason=remove_reason,
            decision_stage=str(target.get("decision_card", {}).get("stage", "")),
            decision_conclusion_type=str(target.get("decision_card", {}).get("conclusion_type", "")),
            decision_evidence_chain=list(target.get("decision_card", {}).get("evidence_chain", [])[:3]),
            decision_info_gaps=list(target.get("decision_card", {}).get("info_gaps", [])[:3]),
        )
        metrics.append(asdict(metric))
    return metrics
