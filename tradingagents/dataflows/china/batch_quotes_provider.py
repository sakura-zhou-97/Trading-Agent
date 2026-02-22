"""Batch quote feature provider for screening pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from io import StringIO
from typing import Dict, List

import pandas as pd

from tradingagents.dataflows.china import china_provider

logger = logging.getLogger(__name__)


def _clean_csv_payload(raw: str) -> str:
    lines = [line for line in raw.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines).strip()


def _parse_stock_csv(raw: str) -> pd.DataFrame:
    payload = _clean_csv_payload(raw)
    if not payload:
        return pd.DataFrame()
    return pd.read_csv(StringIO(payload))


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _history_window(trade_date: str, lookback_days: int) -> tuple[str, str]:
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=max(lookback_days * 2, lookback_days + 10))
    return start_dt.strftime("%Y-%m-%d"), trade_date


def compute_struct_features_from_history(df: pd.DataFrame) -> Dict:
    """Compute MVP structural features from OHLCV history."""
    if df is None or df.empty:
        return {
            "position_score": 0.0,
            "trend_score": 0.0,
            "volume_score": 0.0,
            "breakout_score": 0.0,
            "style_score": 0.0,
            "trend_label": "unknown",
            "recent_3d_change": 0.0,
            "last_close": 0.0,
        }

    work = df.copy()
    if "Date" in work.columns:
        work["Date"] = pd.to_datetime(work["Date"], errors="coerce")
        work = work.sort_values("Date")
    work = work.tail(30)
    close = pd.to_numeric(work.get("Close"), errors="coerce").ffill()
    volume = pd.to_numeric(work.get("Volume"), errors="coerce").fillna(0.0)
    change = pd.to_numeric(work.get("Change%"), errors="coerce").fillna(0.0)

    if close.empty:
        return {
            "position_score": 0.0,
            "trend_score": 0.0,
            "volume_score": 0.0,
            "breakout_score": 0.0,
            "style_score": 0.0,
            "trend_label": "unknown",
            "recent_3d_change": 0.0,
            "last_close": 0.0,
        }

    last_close = float(close.iloc[-1])
    rolling_high = float(close.max()) if len(close) else 0.0
    rolling_low = float(close.min()) if len(close) else 0.0
    ma5 = float(close.tail(5).mean()) if len(close) >= 5 else last_close
    ma10 = float(close.tail(10).mean()) if len(close) >= 10 else ma5
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else ma10

    recent_vol = float(volume.tail(5).mean()) if len(volume) >= 5 else float(volume.mean())
    base_vol = float(volume.head(max(len(volume) - 5, 1)).mean()) if len(volume) else 0.0
    vol_ratio = (recent_vol / base_vol) if base_vol > 0 else 1.0

    recent_3d_change = float(change.tail(3).sum()) if len(change) >= 3 else float(change.sum())
    position = 0.0
    if rolling_high > rolling_low:
        position = (last_close - rolling_low) / (rolling_high - rolling_low)

    trend_score = 100.0 if (last_close > ma5 >= ma10 >= ma20) else 60.0 if last_close > ma10 else 35.0
    volume_score = min(max((vol_ratio - 0.8) * 50, 0), 100)
    breakout_score = 100.0 if last_close >= rolling_high * 0.995 else 40.0
    style_score = min(max(abs(recent_3d_change) * 5, 0), 100)
    trend_label = "uptrend" if last_close >= ma10 else "sideways"
    position_score = min(max(position * 100, 0), 100)

    return {
        "position_score": round(position_score, 2),
        "trend_score": round(trend_score, 2),
        "volume_score": round(float(volume_score), 2),
        "breakout_score": round(float(breakout_score), 2),
        "style_score": round(float(style_score), 2),
        "trend_label": trend_label,
        "recent_3d_change": round(recent_3d_change, 2),
        "last_close": round(last_close, 3),
        "ma5": round(ma5, 3),
        "ma10": round(ma10, 3),
        "ma20": round(ma20, 3),
        "vol_ratio": round(vol_ratio, 3),
    }


def get_batch_struct_features(
    symbols: List[str],
    trade_date: str,
    lookback_days: int = 30,
) -> Dict[str, Dict]:
    """Fetch and compute structural features for many stocks."""
    start_date, end_date = _history_window(trade_date, lookback_days)
    features: Dict[str, Dict] = {}
    for symbol in symbols:
        try:
            raw = china_provider.get_china_stock_data(symbol, start_date, end_date)
            df = _parse_stock_csv(raw)
            features[symbol] = compute_struct_features_from_history(df)
        except Exception as exc:
            logger.warning("Failed to build struct features for %s: %s", symbol, exc)
            features[symbol] = compute_struct_features_from_history(pd.DataFrame())
    return features


def attach_struct_features(universe: List[Dict], trade_date: str, lookback_days: int = 30) -> List[Dict]:
    """Attach computed structural features to universe records."""
    symbols = [item["symbol"] for item in universe]
    feats = get_batch_struct_features(symbols=symbols, trade_date=trade_date, lookback_days=lookback_days)
    enriched: List[Dict] = []
    for item in universe:
        symbol = item["symbol"]
        merged = {**item, **feats.get(symbol, {})}
        merged["change_pct"] = _safe_float(merged.get("change_pct"))
        enriched.append(merged)
    return enriched
