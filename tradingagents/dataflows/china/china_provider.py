"""Unified China A-share data provider.

Routes to AkShare first; falls back to Tushare on failure.
"""

from __future__ import annotations

import logging

from tradingagents.utils.stock_utils import normalize_china_code

logger = logging.getLogger(__name__)


def _try_akshare_then_tushare(ak_func, ts_func, *args, **kwargs) -> str:
    """Call *ak_func* first; on any error fall back to *ts_func*."""
    try:
        return ak_func(*args, **kwargs)
    except Exception as ak_err:
        logger.warning("AkShare failed (%s), falling back to Tushare: %s", ak_func.__name__, ak_err)
    try:
        return ts_func(*args, **kwargs)
    except Exception as ts_err:
        logger.error("Tushare also failed (%s): %s", ts_func.__name__, ts_err)
        return f"Error: unable to fetch data for args={args}. AkShare: {ak_err}; Tushare: {ts_err}"


# ---------------------------------------------------------------------------
# Public unified functions (same signature as US tools expect)
# ---------------------------------------------------------------------------

def get_china_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_stock_data, ts_p.get_stock_data, code, start_date, end_date)


def get_china_fundamentals(symbol: str, curr_date: str = None) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_fundamentals, ts_p.get_fundamentals, code, curr_date)


def get_china_balance_sheet(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_balance_sheet, ts_p.get_balance_sheet, code, freq, curr_date)


def get_china_cashflow(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_cashflow, ts_p.get_cashflow, code, freq, curr_date)


def get_china_income_statement(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_income_statement, ts_p.get_income_statement, code, freq, curr_date)


def get_china_news(symbol: str, start_date: str, end_date: str) -> str:
    code = normalize_china_code(symbol)
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_news, ts_p.get_news, code, start_date, end_date)


def get_china_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    from . import akshare_provider as ak_p, tushare_provider as ts_p
    return _try_akshare_then_tushare(ak_p.get_global_news, ts_p.get_global_news, curr_date, look_back_days, limit)


def get_china_stock_concepts(symbol: str, concept_keywords: list = None) -> list:
    """Return list of concept board names that contain this stock (e.g. ['机器人概念'])."""
    code = normalize_china_code(symbol)
    try:
        from . import akshare_provider as ak_p
        return ak_p.get_stock_concepts_em(code, concept_keywords) or []
    except Exception as e:
        logger.warning("get_china_stock_concepts failed for %s: %s", symbol, e)
        return []
