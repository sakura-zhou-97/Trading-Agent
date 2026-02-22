from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.utils.stock_utils import is_china_a_stock, to_yfinance_china_code

@tool
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Retrieve technical indicators for a given ticker symbol.
    For A-share codes (6 digits) the symbol is auto-converted to yfinance format.
    Args:
        symbol (str): Ticker symbol, e.g. AAPL, 601869, 000001
        indicator (str): Technical indicator to get the analysis and report of
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators.
    """
    # Convert A-share pure code to yfinance compatible format
    if is_china_a_stock(symbol):
        symbol = to_yfinance_china_code(symbol)
    return route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)