import datetime as dt
from sqlalchemy import text


def _db():
    from utils import db

    return db


def _to_int(value):
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_int(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return int(value.strftime("%Y%m%d"))
    value = str(value or "").replace("-", "")[:8]
    return _to_int(value)


def _symbol_int(value):
    return _to_int(str(value or "").split(".", 1)[0])


def _ts_code(value):
    return str(value or "").strip().upper()


def _read_index_dates(limit):
    rows = _db().mysql_localhost(
        f"SELECT DISTINCT `trade_date` FROM `index_daily` ORDER BY `trade_date` DESC LIMIT {int(limit)}",
        fetch=True,
    ) or []
    return [_date_int(row.get("trade_date")) for row in rows if _date_int(row.get("trade_date"))]


def 交易日期列表(limit=160):
    dates = sorted(set(_read_index_dates(max(int(limit), 1))), reverse=False)
    return dates[-int(limit):]


def 标准化指数行(row):
    return {
        "trade_date": _date_int(row.get("date", row.get("日期"))),
        "open_price": _to_float(row.get("open", row.get("开盘"))),
        "close_price": _to_float(row.get("close", row.get("收盘"))),
        "high_price": _to_float(row.get("high", row.get("最高"))),
        "low_price": _to_float(row.get("low", row.get("最低"))),
        "volume": _to_float(row.get("volume", row.get("成交量"))),
        "turnover": _to_float(row.get("amount", row.get("成交额"))),
        "amplitude_pct": _to_float(row.get("amplitude", row.get("振幅"))),
        "change_pct": _to_float(row.get("pct_chg", row.get("涨跌幅"))),
        "change_amount": _to_float(row.get("change", row.get("涨跌额"))),
        "turnover_rate": _to_float(row.get("turnover", row.get("换手率"))),
    }


def 股票日线记录(row, stock_name=None):
    code = _ts_code(row.get("ts_code", row.get("symbol")))
    date = _date_int(row.get("trade_date", row.get("date")))
    return {
        "ts_code": code,
        "trade_date": date,
        "open_price": _to_float(row.get("open")),
        "high_price": _to_float(row.get("high")),
        "low_price": _to_float(row.get("low")),
        "close_price": _to_float(row.get("close")),
        "previous_close": _to_float(row.get("pre_close")),
        "change_amount": _to_float(row.get("change")),
        "change_pct": _to_float(row.get("pct_chg")),
        "volume": _to_float(row.get("vol")),
        "turnover": _to_float(row.get("amount")),
        "total_market_value": _to_float(row.get("total_mv")),
        "circulating_market_value": _to_float(row.get("circ_mv")),
        "free_float_shares": _to_float(row.get("free_share")),
        "free_float_market_value": _to_float(row.get("free_mv")),
        "stock_name": stock_name or row.get("stock_name"),
        "data_id": f"{code}_{date}",
        "dde_net_amount": _to_float(row.get("dde")),
    }


def _upsert_rows(table, columns, rows, key_columns):
    rows = list(rows)
    if not rows:
        return 0
    value_names = [f"v{index}" for index in range(len(columns))]
    insert_columns = ", ".join(f"`{column}`" for column in columns)
    values = ", ".join(f":{name}" for name in value_names)
    updates = ", ".join(
        f"`{column}` = VALUES(`{column}`)"
        for column in columns
        if column not in key_columns
    )
    statement = text(
        f"INSERT INTO `{table}` ({insert_columns}) VALUES ({values}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    parameters = [
        {name: row.get(column) for name, column in zip(value_names, columns)}
        for row in rows
    ]
    with _db().engine.begin() as connection:
        connection.execute(statement, parameters)
    return len(rows)


def _replace_rows(table, columns, rows):
    rows = list(rows)
    if not rows:
        return 0
    value_names = [f"v{index}" for index in range(len(columns))]
    statement = text(
        f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) "
        f"VALUES ({', '.join(f':{name}' for name in value_names)})"
    )
    parameters = [
        {name: row.get(column) for name, column in zip(value_names, columns)}
        for row in rows
    ]
    with _db().engine.begin() as connection:
        connection.execute(text(f"DELETE FROM `{table}`"))
        connection.execute(statement, parameters)
    return len(rows)


def 更新指数日线(start_date, end_date):
    import akshare as ak

    frame = ak.stock_zh_index_daily(symbol="sh000001")
    if frame is None or frame.empty:
        raise RuntimeError("AkShare 未返回上证指数日线")
    rows = [
        标准化指数行(row)
        for row in frame.to_dict("records")
        if int(start_date) <= _date_int(row.get("date", row.get("日期"))) <= int(end_date)
    ]
    columns = ["trade_date", "open_price", "close_price", "high_price", "low_price", "volume", "turnover", "amplitude_pct", "change_pct", "change_amount", "turnover_rate"]
    return _upsert_rows("index_daily", columns, rows, ["trade_date"])


def 更新股票基础信息():
    from utils.common import pro

    frame = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
    )
    if frame is None or frame.empty:
        raise RuntimeError("Tushare 未返回股票基础信息")
    rows = frame.where(frame.notna(), None).to_dict("records")
    for row in rows:
        row["ts_code"] = _ts_code(row.get("ts_code"))
        row["symbol"] = str(row.get("symbol") or "").zfill(6)
        row["list_date"] = _date_int(row.get("list_date"))
    columns = ["ts_code", "symbol", "name", "area", "industry", "market", "list_date", "list_status"]
    return _replace_rows("securities", columns, rows)


def 更新股票日线(start_date, end_date):
    from utils.common import pro

    dates = [
        date for date in _read_index_dates(1000)
        if int(start_date) <= int(date) <= int(end_date)
    ]
    if not dates:
        dates = [int(end_date)]
    frames = []
    for date in dates:
        frame = pro.daily(ts_code="", trade_date=str(date))
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        raise RuntimeError(f"Tushare 未返回 {start_date}-{end_date} 股票日线")
    import pandas as pd

    frame = pd.concat(frames, ignore_index=True)
    names = {
        str(row.get("symbol") or "").zfill(6): row.get("name")
        for row in (_db().mysql_localhost("SELECT symbol, name FROM securities", fetch=True) or [])
    }
    rows = [
        股票日线记录(row, names.get(str(row.get("ts_code") or "").split(".", 1)[0].zfill(6)))
        for row in frame.where(frame.notna(), None).to_dict("records")
    ]
    columns = [
        "ts_code", "trade_date", "open_price", "high_price", "low_price", "close_price", "previous_close", "change_amount", "change_pct",
        "volume", "turnover", "total_market_value", "circulating_market_value", "free_float_shares", "free_float_market_value", "stock_name", "data_id", "dde_net_amount",
    ]
    return _upsert_rows("daily_quotes", columns, rows, ["data_id"])
