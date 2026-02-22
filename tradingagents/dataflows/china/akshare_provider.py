"""AkShare data provider for China A-share market.

Free, no token required.  Provides OHLCV, basic fundamentals, and news.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stock OHLCV
# ---------------------------------------------------------------------------

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch daily OHLCV data for a China A-share stock via AkShare.

    Args:
        symbol: 6-digit A-share code, e.g. '601869'.
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'

    Returns:
        CSV-formatted string with header, or error message.
    """
    import akshare as ak

    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="qfq",
        )
    except Exception as e:
        raise RuntimeError(f"AkShare get_stock_data failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no OHLCV data for {symbol} ({start_date} ~ {end_date})")

    # Standardise column names
    col_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
        "成交额": "Amount",
        "涨跌幅": "Change%",
        "换手率": "Turnover%",
    }
    df = df.rename(columns=col_map)
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "Change%", "Turnover%"] if c in df.columns]
    df = df[keep]

    header = f"# A-share daily data for {symbol} ({start_date} ~ {end_date})\n"
    header += f"# Records: {len(df)}  | Source: AkShare\n\n"
    return header + df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def get_fundamentals(symbol: str, curr_date: str = None) -> str:
    """Fetch basic fundamental info for an A-share stock via AkShare."""
    import akshare as ak

    try:
        df = ak.stock_individual_info_em(symbol=symbol)
    except Exception as e:
        raise RuntimeError(f"AkShare get_fundamentals failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no fundamentals for {symbol}")

    lines = [f"# Fundamentals for {symbol} (Source: AkShare / East Money)\n"]
    for _, row in df.iterrows():
        lines.append(f"- **{row.iloc[0]}**: {row.iloc[1]}")
    return "\n".join(lines)


def get_balance_sheet(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch balance sheet data for an A-share stock."""
    import akshare as ak

    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        raise RuntimeError(f"AkShare get_balance_sheet failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no balance sheet for {symbol}")

    # Keep latest few periods
    if len(df) > 4:
        df = df.head(4)
    header = f"# Balance Sheet for {symbol} ({freq}) | Source: AkShare\n\n"
    return header + df.to_csv(index=False)


def get_cashflow(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch cash-flow statement for an A-share stock."""
    import akshare as ak

    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        raise RuntimeError(f"AkShare get_cashflow failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no cashflow for {symbol}")

    if len(df) > 4:
        df = df.head(4)
    header = f"# Cash Flow for {symbol} ({freq}) | Source: AkShare\n\n"
    return header + df.to_csv(index=False)


def get_income_statement(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch income statement for an A-share stock."""
    import akshare as ak

    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        raise RuntimeError(f"AkShare get_income_statement failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no income statement for {symbol}")

    if len(df) > 4:
        df = df.head(4)
    header = f"# Income Statement for {symbol} ({freq}) | Source: AkShare\n\n"
    return header + df.to_csv(index=False)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def get_news(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch recent news for an A-share stock from East Money via AkShare."""
    import akshare as ak

    try:
        df = ak.stock_news_em(symbol=symbol)
    except Exception as e:
        raise RuntimeError(f"AkShare get_news failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise RuntimeError(f"AkShare: no news for {symbol}")

    col_map = {
        "新闻标题": "title",
        "新闻内容": "content",
        "发布时间": "publish_time",
        "文章来源": "source",
        "新闻链接": "url",
    }
    df = df.rename(columns=col_map)

    # Filter by date range if columns available
    if "publish_time" in df.columns:
        df["publish_time"] = df["publish_time"].astype(str)
        # best-effort date filter
        try:
            df = df[df["publish_time"] >= start_date]
            df = df[df["publish_time"] <= end_date + " 23:59:59"]
        except Exception:
            pass

    # Limit
    df = df.head(20)

    lines = [f"## A-share News for {symbol} ({start_date} ~ {end_date})\n"]
    for idx, row in df.iterrows():
        title = row.get("title", "")
        source = row.get("source", "")
        pub = row.get("publish_time", "")
        content = str(row.get("content", ""))[:300]
        lines.append(f"### {idx+1}. {title}")
        lines.append(f"**Source**: {source}  |  **Time**: {pub}")
        lines.append(f"{content}...\n")

    return "\n".join(lines) if len(lines) > 1 else f"No news found for {symbol}"


# ---------------------------------------------------------------------------
# Stock concepts (East Money concept boards)
# ---------------------------------------------------------------------------

# 用于反查个股所属概念的板块关键词（仅查询匹配的概念，避免全量遍历）
DEFAULT_CONCEPT_KEYWORDS = [
    "机器人", "人形", "丝杠", "滚柱", "滚珠", "减速器", "轴承",
    "人形机器人", "行星滚柱", "精密传动", "传动",
]

def get_stock_concepts_em(
    symbol: str,
    concept_keywords: Optional[list] = None,
) -> list[str]:
    """Get concept board names that contain this stock (East Money).
    Only checks boards whose name contains any of concept_keywords, to limit API calls.
    Returns list of concept names (e.g. ['机器人概念', '人形机器人']).
    """
    import akshare as ak

    symbol = (symbol or "").strip()
    if not symbol:
        return []
    # 统一为 6 位代码比较
    code = symbol.replace(".SS", "").replace(".SZ", "").strip()
    if len(code) == 5 and code.startswith("0"):
        code = "0" + code
    elif len(code) < 6:
        code = code.zfill(6)
    keywords = concept_keywords or DEFAULT_CONCEPT_KEYWORDS

    try:
        name_df = ak.stock_board_concept_name_em()
    except Exception as e:
        logger.warning("AkShare stock_board_concept_name_em failed: %s", e)
        return []

    if name_df is None or name_df.empty:
        return []

    # 列名可能是 "板块名称" 或 "name"
    name_col = "板块名称" if "板块名称" in name_df.columns else (name_df.columns[0] if len(name_df.columns) else None)
    if name_col is None:
        return []

    concept_names = name_df[name_col].astype(str).dropna().unique().tolist()
    # 筛选包含任一关键词的概念名
    matched = [
        n for n in concept_names
        if any(kw in n for kw in keywords)
    ]

    def _norm(s: str) -> str:
        s = (s or "").strip().replace(".SS", "").replace(".SZ", "")[:6].zfill(6)
        return s

    code_norm = _norm(code)
    result: list[str] = []
    for con_name in matched:
        try:
            cons_df = ak.stock_board_concept_cons_em(symbol=con_name)
        except Exception:
            continue
        if cons_df is None or cons_df.empty:
            continue
        code_col = "代码" if "代码" in cons_df.columns else (cons_df.columns[0] if len(cons_df.columns) else None)
        if code_col is None:
            continue
        for _, row in cons_df.iterrows():
            c = _norm(str(row[code_col]))
            if c == code_norm:
                result.append(con_name)
                break

    return list(dict.fromkeys(result))


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    """Fetch China macro / financial news from East Money via AkShare."""
    import akshare as ak

    try:
        df = ak.stock_info_global_em()
    except Exception as e:
        raise RuntimeError(f"AkShare get_global_news failed: {e}") from e

    if df is None or df.empty:
        raise RuntimeError("AkShare: no global news data")

    col_map = {"标题": "title", "摘要": "summary", "发布时间": "time", "来源": "source"}
    df = df.rename(columns=col_map)
    df = df.head(limit)

    lines = [f"## China / Global Financial News (as of {curr_date})\n"]
    for idx, row in df.iterrows():
        title = row.get("title", "")
        summary = str(row.get("summary", ""))[:200]
        lines.append(f"### {idx+1}. {title}")
        lines.append(f"{summary}\n")
    return "\n".join(lines)
