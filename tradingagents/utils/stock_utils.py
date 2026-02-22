"""Stock market identification utilities."""

from __future__ import annotations

import re


def is_china_a_stock(symbol: str) -> bool:
    """Check if a symbol is a China A-share stock code.

    A-share codes are 6-digit numbers, optionally suffixed with .SS or .SZ.
    Examples: 000001, 600519, 601869.SS, 000858.SZ
    """
    clean = symbol.strip().upper()
    # Strip exchange suffix
    clean = re.sub(r'\.(SS|SZ|SH)$', '', clean)
    return bool(re.fullmatch(r'\d{6}', clean))


def normalize_china_code(symbol: str) -> str:
    """Normalize a China A-share code to pure 6-digit form (no suffix).

    '601869.SS' -> '601869', '000001' -> '000001'
    """
    clean = symbol.strip().upper()
    return re.sub(r'\.(SS|SZ|SH)$', '', clean)


def get_market_type(symbol: str) -> str:
    """Return market type string: 'china_a' or 'us'.

    Args:
        symbol: Stock ticker / code.

    Returns:
        'china_a' for A-share codes, 'us' otherwise.
    """
    if is_china_a_stock(symbol):
        return "china_a"
    return "us"


def to_yfinance_china_code(symbol: str) -> str:
    """Convert a China A-share code to yfinance-compatible format.

    '601869' -> '601869.SS' (Shanghai)
    '000001' -> '000001.SZ' (Shenzhen)
    Already suffixed codes are returned as-is.
    """
    clean = symbol.strip().upper()
    if clean.endswith((".SS", ".SZ", ".SH")):
        return clean.replace(".SH", ".SS")
    code = normalize_china_code(clean)
    if code.startswith("6"):
        return f"{code}.SS"
    return f"{code}.SZ"
