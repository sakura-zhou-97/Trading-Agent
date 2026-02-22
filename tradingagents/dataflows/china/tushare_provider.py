"""Tinyshare-backed data provider for China A-share market.

Requires Tinyshare auth code via TINYSHARE_TOKEN (fallback: TUSHARE_TOKEN).
Used as fallback when AkShare fails.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_api = None


def _get_api():
    """Lazy-init Tinyshare/Tushare compatible pro API."""
    global _api
    if _api is not None:
        return _api

    token = os.getenv("TINYSHARE_TOKEN", "") or os.getenv("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError(
            "TINYSHARE_TOKEN is not set (fallback TUSHARE_TOKEN). Please add it to your .env file or environment."
        )

    import tinyshare as ts
    ts.set_token(token)
    _api = ts.pro_api()
    return _api


def _to_ts_code(symbol: str) -> str:
    """Convert pure 6-digit code to Tushare ts_code format.

    '601869' -> '601869.SH'  (6xxxxx -> SH)
    '000001' -> '000001.SZ'  (0xxxxx / 3xxxxx -> SZ)
    """
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


# ---------------------------------------------------------------------------
# Stock OHLCV
# ---------------------------------------------------------------------------

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch daily OHLCV via Tushare."""
    api = _get_api()
    ts_code = _to_ts_code(symbol)
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    df = api.daily(ts_code=ts_code, start_date=start_fmt, end_date=end_fmt)
    if df is None or df.empty:
        raise RuntimeError(f"Tushare: no OHLCV for {ts_code} ({start_date}~{end_date})")

    df = df.sort_values("trade_date")
    col_map = {
        "trade_date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "vol": "Volume",
        "amount": "Amount",
        "pct_chg": "Change%",
    }
    df = df.rename(columns=col_map)
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "Change%"] if c in df.columns]
    df = df[keep]

    header = f"# A-share daily data for {symbol} ({start_date} ~ {end_date})\n"
    header += f"# Records: {len(df)}  | Source: Tushare\n\n"
    return header + df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def get_fundamentals(symbol: str, curr_date: str = None) -> str:
    """Fetch basic company info + daily basic indicators via Tushare."""
    api = _get_api()
    ts_code = _to_ts_code(symbol)

    info = api.stock_basic(ts_code=ts_code)
    if info is None or info.empty:
        raise RuntimeError(f"Tushare: no basic info for {ts_code}")

    row = info.iloc[0]
    lines = [f"# Fundamentals for {symbol} (Source: Tushare)\n"]
    for col in info.columns:
        lines.append(f"- **{col}**: {row[col]}")

    # Try to get daily basic (PE, PB, etc.)
    trade_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
    try:
        daily_basic = api.daily_basic(ts_code=ts_code, trade_date=trade_date)
        if daily_basic is not None and not daily_basic.empty:
            br = daily_basic.iloc[0]
            lines.append("\n## Valuation Indicators")
            for col in daily_basic.columns:
                lines.append(f"- **{col}**: {br[col]}")
    except Exception:
        pass

    return "\n".join(lines)


def get_balance_sheet(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch balance sheet via Tushare."""
    api = _get_api()
    ts_code = _to_ts_code(symbol)

    df = api.balancesheet(ts_code=ts_code)
    if df is None or df.empty:
        raise RuntimeError(f"Tushare: no balance sheet for {ts_code}")

    df = df.head(4)
    header = f"# Balance Sheet for {symbol} ({freq}) | Source: Tushare\n\n"
    return header + df.to_csv(index=False)


def get_cashflow(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch cashflow via Tushare."""
    api = _get_api()
    ts_code = _to_ts_code(symbol)

    df = api.cashflow(ts_code=ts_code)
    if df is None or df.empty:
        raise RuntimeError(f"Tushare: no cashflow for {ts_code}")

    df = df.head(4)
    header = f"# Cash Flow for {symbol} ({freq}) | Source: Tushare\n\n"
    return header + df.to_csv(index=False)


def get_income_statement(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch income statement via Tushare."""
    api = _get_api()
    ts_code = _to_ts_code(symbol)

    df = api.income(ts_code=ts_code)
    if df is None or df.empty:
        raise RuntimeError(f"Tushare: no income statement for {ts_code}")

    df = df.head(4)
    header = f"# Income Statement for {symbol} ({freq}) | Source: Tushare\n\n"
    return header + df.to_csv(index=False)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def get_news(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch news via Tushare (major_news or cctv_news)."""
    api = _get_api()

    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    try:
        df = api.major_news(start_date=start_fmt, end_date=end_fmt, src=symbol)
    except Exception:
        df = None

    if df is None or df.empty:
        # Fallback to general news
        try:
            df = api.news(src="sina", start_date=start_fmt, end_date=end_fmt)
        except Exception as e:
            raise RuntimeError(f"Tushare get_news failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"Tushare: no news for {symbol}")

    df = df.head(20)
    lines = [f"## A-share News for {symbol} ({start_date} ~ {end_date}) | Source: Tushare\n"]
    for idx, row in df.iterrows():
        title = row.get("title", row.get("content", "")[:60])
        lines.append(f"### {idx+1}. {title}")
        content = str(row.get("content", ""))[:300]
        lines.append(f"{content}...\n")
    return "\n".join(lines)


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    """Fetch general financial news from Tushare."""
    api = _get_api()
    end_fmt = curr_date.replace("-", "")

    try:
        from datetime import timedelta
        start_dt = datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        start_fmt = start_dt.strftime("%Y%m%d")
        df = api.news(src="sina", start_date=start_fmt, end_date=end_fmt)
    except Exception as e:
        raise RuntimeError(f"Tushare get_global_news failed: {e}") from e

    if df is None or df.empty:
        raise RuntimeError("Tushare: no global news")

    df = df.head(limit)
    lines = [f"## China Financial News ({curr_date}) | Source: Tushare\n"]
    for idx, row in df.iterrows():
        title = row.get("title", "")
        content = str(row.get("content", ""))[:200]
        lines.append(f"### {idx+1}. {title}")
        lines.append(f"{content}\n")
    return "\n".join(lines)
