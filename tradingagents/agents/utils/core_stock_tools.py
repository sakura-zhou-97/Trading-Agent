from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_by_market_stock_data


@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve stock price data (OHLCV) for a given ticker symbol.
    Automatically routes to China A-share data sources for 6-digit codes,
    or to the configured US vendor otherwise.
    Args:
        symbol (str): Ticker symbol, e.g. AAPL, 601869, 000001
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing stock price data.
    """
    return route_by_market_stock_data(symbol, start_date, end_date)
