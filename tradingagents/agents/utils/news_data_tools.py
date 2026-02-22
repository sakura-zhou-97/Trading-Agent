from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import (
    route_to_vendor,
    route_by_market_news,
    route_by_market_global_news,
)
from tradingagents.utils.stock_utils import is_china_a_stock

@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Routes to China A-share news sources for 6-digit codes.
    Args:
        ticker (str): Ticker symbol, e.g. AAPL, 601869
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    return route_by_market_news(ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """
    Retrieve global news data.
    Routes to China financial news when market_type is china_a.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
    Returns:
        str: A formatted string containing global news data
    """
    return route_by_market_global_news(curr_date, look_back_days, limit)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Note: Not available for China A-share stocks; returns a notice for A-shares.
    Args:
        ticker (str): Ticker symbol
    Returns:
        str: A report of insider transaction data
    """
    if is_china_a_stock(ticker):
        return f"Insider transaction data is not available for China A-share stock {ticker}. This data source only covers US equities."
    return route_to_vendor("get_insider_transactions", ticker)
