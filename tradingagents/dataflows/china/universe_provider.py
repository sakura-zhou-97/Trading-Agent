"""Universe provider for China A-share screening.

MVP target:
- Main board only
- Non-ST
- Daily change percentage > threshold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from tradingagents.dataflows.china import tushare_provider as ts_provider

logger = logging.getLogger(__name__)


@dataclass
class UniverseRecord:
    symbol: str
    ts_code: str
    name: str
    market: str
    industry: str
    is_st: bool
    change_pct: float
    close: float
    open: float
    high: float
    low: float
    volume: float
    amount: float


def _is_main_board_from_code(symbol: str) -> bool:
    """Best-effort code-based main board classifier."""
    if len(symbol) != 6 or not symbol.isdigit():
        return False
    # STAR market (688), ChiNext (300), Beijing exchange(8/4 prefixes) excluded.
    if symbol.startswith(("688", "300", "8", "4")):
        return False
    # Main board common prefixes.
    return symbol.startswith(("000", "001", "002", "003", "600", "601", "603", "605"))


def _norm_trade_date(trade_date: str) -> str:
    return trade_date.replace("-", "")


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _load_tushare_daily(trade_date: str) -> pd.DataFrame:
    """Load all daily quotes for a trade date from tushare."""
    api = ts_provider._get_api()  # pylint: disable=protected-access
    td = _norm_trade_date(trade_date)
    df = api.daily(trade_date=td)
    if df is None or df.empty:
        raise RuntimeError(f"Tushare daily returned empty for {trade_date}")
    return df


def _load_tushare_stock_basic() -> pd.DataFrame:
    api = ts_provider._get_api()  # pylint: disable=protected-access
    df = api.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    if df is None or df.empty:
        raise RuntimeError("Tushare stock_basic returned empty")
    return df


def get_daily_universe(
    trade_date: str,
    min_change_pct: float = 5.0,
    main_board_only: bool = True,
    non_st_only: bool = True,
    max_items: Optional[int] = None,
) -> List[Dict]:
    """Get daily A-share universe records filtered by MVP constraints."""
    try:
        daily_df = _load_tushare_daily(trade_date)
        basic_df = _load_tushare_stock_basic()
    except Exception as exc:
        raise RuntimeError(
            "Universe provider currently requires Tushare for historical-day screening. "
            f"Reason: {exc}"
        ) from exc

    merged = daily_df.merge(
        basic_df[["ts_code", "symbol", "name", "market", "industry"]],
        how="left",
        on="ts_code",
    )

    # Base filters
    merged = merged[merged["pct_chg"] > float(min_change_pct)]
    if main_board_only:
        merged = merged[merged["symbol"].astype(str).apply(_is_main_board_from_code)]
    if non_st_only:
        merged = merged[~merged["name"].astype(str).str.upper().str.contains("ST", na=False)]

    # Sort by pct change descending.
    merged = merged.sort_values("pct_chg", ascending=False)
    if max_items is not None and max_items > 0:
        merged = merged.head(max_items)

    records: List[Dict] = []
    for _, row in merged.iterrows():
        record = UniverseRecord(
            symbol=str(row.get("symbol", "")),
            ts_code=str(row.get("ts_code", "")),
            name=str(row.get("name", "")),
            market=str(row.get("market", "")),
            industry=str(row.get("industry", "")),
            is_st="ST" in str(row.get("name", "")).upper(),
            change_pct=_safe_float(row.get("pct_chg")),
            close=_safe_float(row.get("close")),
            open=_safe_float(row.get("open")),
            high=_safe_float(row.get("high")),
            low=_safe_float(row.get("low")),
            volume=_safe_float(row.get("vol")),
            amount=_safe_float(row.get("amount")),
        )
        records.append(asdict(record))

    logger.info(
        "Universe loaded for %s, count=%s (min_change_pct=%s)",
        trade_date,
        len(records),
        min_change_pct,
    )
    return records


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")
