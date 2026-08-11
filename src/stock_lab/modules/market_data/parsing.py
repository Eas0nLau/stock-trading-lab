from stock_lab.shared.errors import DataValidationError

from .helpers import normalize_symbol, normalize_trade_date


def _required_float(row, name):
    value = row.get(name)
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise DataValidationError(f"Invalid intraday {name}: {value!r}") from error


def _source_symbol(value):
    raw = str(value or "").strip()
    if raw.lower().startswith(("sh.", "sz.", "bj.")):
        raw = raw.split(".", 1)[1]
    symbol = normalize_symbol(raw)
    if len(symbol) != 6 or not symbol.isdigit():
        raise DataValidationError(f"Invalid intraday stock code: {value!r}")
    return symbol


def normalize_intraday_bar(row):
    trade_date = normalize_trade_date(row.get("date"))
    trade_time_raw = str(row.get("time") or "").strip()
    if not trade_date or len(trade_time_raw) < 12 or not trade_time_raw.isdigit():
        raise DataValidationError("Invalid intraday date or time")
    trade_time_text = trade_time_raw[:12]
    if int(trade_time_text[:8]) != trade_date:
        raise DataValidationError("Intraday date and time do not match")
    symbol = _source_symbol(row.get("code"))
    try:
        adjustment_flag = int(row.get("adjustflag"))
    except (TypeError, ValueError) as error:
        raise DataValidationError(f"Invalid adjustment flag: {row.get('adjustflag')!r}") from error
    trade_time = int(trade_time_text)
    return {
        "data_id": f"{symbol}_{trade_time}_{adjustment_flag}",
        "trade_date": trade_date,
        "trade_time": trade_time,
        "stock_code": symbol,
        "open_price": _required_float(row, "open"),
        "high_price": _required_float(row, "high"),
        "low_price": _required_float(row, "low"),
        "close_price": _required_float(row, "close"),
        "volume": _required_float(row, "volume"),
        "turnover": _required_float(row, "amount"),
        "adjustment_flag": adjustment_flag,
    }
