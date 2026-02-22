from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Only rate limits trigger fallback

    raise RuntimeError(f"No available vendor for '{method}'")


# ---------------------------------------------------------------------------
# Market-aware routing (China A-share vs US)
# ---------------------------------------------------------------------------

from tradingagents.utils.stock_utils import is_china_a_stock  # noqa: E402

# China A-share unified provider (lazy import to avoid hard dep when not used)
def _china():
    from tradingagents.dataflows.china import china_provider
    return china_provider


def route_by_market_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Get OHLCV data — routes to China provider for A-shares, else US vendor."""
    if is_china_a_stock(symbol):
        return _china().get_china_stock_data(symbol, start_date, end_date)
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


def route_by_market_fundamentals(ticker: str, curr_date: str = None) -> str:
    if is_china_a_stock(ticker):
        return _china().get_china_fundamentals(ticker, curr_date)
    return route_to_vendor("get_fundamentals", ticker, curr_date)


def route_by_market_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    if is_china_a_stock(ticker):
        return _china().get_china_balance_sheet(ticker, freq, curr_date)
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


def route_by_market_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    if is_china_a_stock(ticker):
        return _china().get_china_cashflow(ticker, freq, curr_date)
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


def route_by_market_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    if is_china_a_stock(ticker):
        return _china().get_china_income_statement(ticker, freq, curr_date)
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


def route_by_market_news(ticker: str, start_date: str, end_date: str) -> str:
    if is_china_a_stock(ticker):
        return _china().get_china_news(ticker, start_date, end_date)
    return route_to_vendor("get_news", ticker, start_date, end_date)


def route_by_market_concepts(ticker: str, concept_keywords: list = None) -> list:
    """Return list of concept/theme names that include this stock (e.g. ['机器人概念']). China A only."""
    if is_china_a_stock(ticker):
        return _china().get_china_stock_concepts(ticker, concept_keywords)
    return []


def route_by_market_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    """Global news — check config market_type; if china_a use China provider."""
    config = get_config()
    if config.get("market_type") == "china_a":
        return _china().get_china_global_news(curr_date, look_back_days, limit)
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)