"""Compatibility wrapper for :mod:`stock_lab.jobs.intraday_bars_5m`."""

from stock_lab.jobs.intraday_bars_5m import fetch_intraday_bars_5m
from stock_lab.modules.market_data.helpers import normalize_ts_code


def _legacy_number(value):
    return format(value, "g")


def _legacy_code(value):
    ts_code = normalize_ts_code(value)
    symbol, separator, exchange = ts_code.partition(".")
    if not separator:
        if symbol.startswith(("4", "8")):
            exchange = "BJ"
        else:
            exchange = "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
    return f"{exchange.lower()}.{symbol}"


def get_data(start_date, end_date, code=None, source=None, *, stock=None):
    if code is not None and stock is not None:
        raise TypeError("Pass either code or stock, not both")
    code = code if code is not None else stock
    if code is None:
        raise TypeError("Pass either code or stock")
    rows = fetch_intraday_bars_5m(start_date, end_date, code, source=source)
    return [[
        _legacy_number(row["open_price"]),
        _legacy_number(row["close_price"]),
        f"{str(row['trade_date'])[:4]}-{str(row['trade_date'])[4:6]}-{str(row['trade_date'])[6:]}",
        str(row["trade_time"]),
        _legacy_code(code),
        _legacy_number(row["high_price"]),
        _legacy_number(row["low_price"]),
        _legacy_number(row["volume"]),
        _legacy_number(row["turnover"]),
        str(row["adjustment_flag"]),
    ] for row in rows]
