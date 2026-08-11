import datetime as dt


def _number(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_ts_code(value):
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    if "." in raw:
        symbol, exchange = raw.split(".", 1)
        return f"{symbol.zfill(6)}.{exchange}"
    if not raw.isdigit():
        return raw
    symbol = raw.zfill(6)
    if symbol.startswith(("4", "8")) or symbol.startswith("92"):
        exchange = "BJ"
    elif symbol.startswith(("5", "6", "9")):
        exchange = "SH"
    else:
        exchange = "SZ"
    return f"{symbol}.{exchange}"


def normalize_symbol(value):
    return normalize_ts_code(value).split(".", 1)[0]


def stock_code_filter(codes, column="ts_code"):
    symbols = sorted({normalize_symbol(code) for code in codes if code})
    if not symbols:
        return "1 = 0", ()
    placeholders = ", ".join(["%s"] * len(symbols))
    quoted_column = ".".join(f"`{part}`" for part in column.split("."))
    return f"LPAD(SUBSTRING_INDEX({quoted_column}, '.', 1), 6, '0') IN ({placeholders})", tuple(symbols)


def normalize_trade_date(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return int(value.strftime("%Y%m%d"))
    raw = str(value or "").replace("-", "").replace("/", "")[:8]
    return int(raw) if raw.isdigit() else 0


def security_from_source(row):
    return {
        "ts_code": normalize_ts_code(row.get("ts_code", row.get("symbol"))),
        "symbol": normalize_symbol(row.get("symbol", row.get("ts_code"))),
        "name": row.get("name"),
        "area": row.get("area"),
        "industry": row.get("industry"),
        "market": row.get("market"),
        "list_date": normalize_trade_date(row.get("list_date")),
        "list_status": row.get("list_status"),
    }


def daily_quote_from_source(row, stock_name=None):
    code = normalize_ts_code(row.get("ts_code", row.get("symbol")))
    trade_date = normalize_trade_date(row.get("trade_date", row.get("date")))
    return {
        "data_id": f"{code}_{trade_date}",
        "ts_code": code,
        "trade_date": trade_date,
        "open_price": _number(row.get("open")),
        "high_price": _number(row.get("high")),
        "low_price": _number(row.get("low")),
        "close_price": _number(row.get("close")),
        "previous_close": _number(row.get("pre_close")),
        "change_amount": _number(row.get("change")),
        "change_pct": _number(row.get("pct_chg")),
        "volume": _number(row.get("vol")),
        "turnover": _number(row.get("amount")),
        "total_market_value": _number(row.get("total_mv")),
        "circulating_market_value": _number(row.get("circ_mv")),
        "free_float_shares": _number(row.get("free_share")),
        "free_float_market_value": _number(row.get("free_mv")),
        "stock_name": stock_name or row.get("stock_name"),
        "dde_net_amount": _number(row.get("dde")),
    }


def index_daily_from_source(row):
    return {
        "trade_date": normalize_trade_date(row.get("date", row.get("日期"))),
        "open_price": _number(row.get("open", row.get("开盘"))),
        "close_price": _number(row.get("close", row.get("收盘"))),
        "high_price": _number(row.get("high", row.get("最高"))),
        "low_price": _number(row.get("low", row.get("最低"))),
        "volume": _number(row.get("volume", row.get("成交量"))),
        "turnover": _number(row.get("amount", row.get("成交额"))),
        "amplitude_pct": _number(row.get("amplitude", row.get("振幅"))),
        "change_pct": _number(row.get("pct_chg", row.get("pctChg", row.get("涨跌幅")))),
        "change_amount": _number(row.get("change", row.get("涨跌额"))),
        "turnover_rate": _number(row.get("turnover", row.get("turn", row.get("换手率")))),
    }
