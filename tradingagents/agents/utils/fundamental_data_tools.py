from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import (
    route_by_market_fundamentals,
    route_by_market_balance_sheet,
    route_by_market_cashflow,
    route_by_market_income_statement,
)


@tool
def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol.
    Automatically routes to China A-share sources for 6-digit codes.
    Args:
        ticker (str): Ticker symbol, e.g. AAPL, 601869
        curr_date (str): Current date, yyyy-mm-dd
    Returns:
        str: A formatted report containing comprehensive fundamental data
    """
    return route_by_market_fundamentals(ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol.
    Args:
        ticker (str): Ticker symbol, e.g. AAPL, 601869
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date, yyyy-mm-dd
    Returns:
        str: A formatted report containing balance sheet data
    """
    return route_by_market_balance_sheet(ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol.
    Args:
        ticker (str): Ticker symbol, e.g. AAPL, 601869
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date, yyyy-mm-dd
    Returns:
        str: A formatted report containing cash flow statement data
    """
    return route_by_market_cashflow(ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve income statement data for a given ticker symbol.
    Args:
        ticker (str): Ticker symbol, e.g. AAPL, 601869
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date, yyyy-mm-dd
    Returns:
        str: A formatted report containing income statement data
    """
    return route_by_market_income_statement(ticker, freq, curr_date)