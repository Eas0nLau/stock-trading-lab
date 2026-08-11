from collections import defaultdict, deque

from stock_lab.shared.errors import DataValidationError

from .helpers import normalize_trade_date, normalize_ts_code


def _price(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise DataValidationError(f"Invalid daily quote {name}") from error


def calculate_kdj(rows, period=9):
    if int(period) < 1:
        raise DataValidationError("KDJ period must be positive")
    grouped = defaultdict(list)
    for row in rows:
        ts_code = normalize_ts_code(row.get("ts_code"))
        trade_date = normalize_trade_date(row.get("trade_date"))
        if not ts_code or not trade_date:
            raise DataValidationError("KDJ rows require ts_code and trade_date")
        grouped[ts_code].append((trade_date, row))

    indicators = []
    for ts_code in sorted(grouped):
        window = deque(maxlen=int(period))
        k_value = 50.0
        d_value = 50.0
        for trade_date, row in sorted(grouped[ts_code], key=lambda item: item[0]):
            low = _price(row, "low_price")
            high = _price(row, "high_price")
            close = _price(row, "close_price")
            if high < low:
                raise DataValidationError("Daily quote high_price is below low_price")
            window.append((low, high))
            lowest = min(item[0] for item in window)
            highest = max(item[1] for item in window)
            rsv = 50.0 if highest == lowest else (close - lowest) / (highest - lowest) * 100.0
            k_value = k_value * 2.0 / 3.0 + rsv / 3.0
            d_value = d_value * 2.0 / 3.0 + k_value / 3.0
            indicators.append({
                "data_id": f"{ts_code}_{trade_date}",
                "ts_code": ts_code,
                "trade_date": trade_date,
                "k_value": k_value,
                "d_value": d_value,
                "j_value": 3.0 * k_value - 2.0 * d_value,
            })
    return indicators


def calculate_ths_kdj(frame, n=9, m1=3, m2=3):
    try:
        n, m1, m2 = int(n), int(m1), int(m2)
    except (TypeError, ValueError) as error:
        raise DataValidationError("KDJ n, m1, and m2 must be integers") from error
    if min(n, m1, m2) <= 0:
        raise DataValidationError("KDJ n, m1, and m2 must be positive")
    required = {"trade_date", "low", "high", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError(
            "KDJ frame missing columns: " + ", ".join(sorted(missing))
        )
    result = frame.copy()
    try:
        for column in ("low", "high", "close"):
            result[column] = result[column].astype(float)
    except (TypeError, ValueError) as error:
        raise DataValidationError("KDJ frame contains invalid prices") from error
    lowest = result["low"].rolling(window=n).min()
    highest = result["high"].rolling(window=n).max()
    result["rsv"] = (
        (result["close"] - lowest) / (highest - lowest) * 100
    ).replace([float("inf"), float("-inf")], 0).fillna(0)
    result["k"] = 50.0
    result["d"] = 50.0
    k_column = result.columns.get_loc("k")
    d_column = result.columns.get_loc("d")
    rsv_column = result.columns.get_loc("rsv")
    for index in range(1, len(result)):
        k_value = (
            (1 - 1 / m1) * result.iat[index - 1, k_column]
            + result.iat[index, rsv_column] / m1
        )
        result.iat[index, k_column] = k_value
        result.iat[index, d_column] = (
            (1 - 1 / m2) * result.iat[index - 1, d_column]
            + k_value / m2
        )
    result["j"] = 3 * result["k"] - 2 * result["d"]
    return result[["trade_date", "k", "d", "j"]]
