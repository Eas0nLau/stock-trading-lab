import datetime as dt
from sqlalchemy import text

from stock_lab.modules.market_data.helpers import (
    daily_quote_from_source,
    index_daily_from_source,
    normalize_symbol,
    normalize_trade_date,
    normalize_ts_code,
    security_from_source,
)
from stock_lab.modules.market_data.repository import MarketDataRepository


def _db():
    from utils import db

    return db


def _market_data_repository():
    database = _db()
    return MarketDataRepository(database.mysql_localhost, database.engine)


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
    return normalize_trade_date(value)


def _symbol_int(value):
    return _to_int(normalize_symbol(value))


def _ts_code(value):
    return normalize_ts_code(value)


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
    return index_daily_from_source(row)


def 股票日线记录(row, stock_name=None):
    return daily_quote_from_source(row, stock_name)


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
    return _market_data_repository().upsert_index_daily(rows)


def 更新股票基础信息():
    from utils.common import get_tushare_pro

    frame = get_tushare_pro().stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
    )
    if frame is None or frame.empty:
        raise RuntimeError("Tushare 未返回股票基础信息")
    rows = [security_from_source(row) for row in frame.where(frame.notna(), None).to_dict("records")]
    return _market_data_repository().replace_securities(rows)


def 更新股票日线(start_date, end_date):
    from utils.common import get_tushare_pro

    dates = [
        date for date in _read_index_dates(1000)
        if int(start_date) <= int(date) <= int(end_date)
    ]
    if not dates:
        dates = [int(end_date)]
    frames = []
    for date in dates:
        frame = get_tushare_pro().daily(ts_code="", trade_date=str(date))
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        raise RuntimeError(f"Tushare 未返回 {start_date}-{end_date} 股票日线")
    import pandas as pd

    frame = pd.concat(frames, ignore_index=True)
    names = {normalize_symbol(row.get("symbol")): row.get("name") for row in _market_data_repository().securities()}
    rows = [
        股票日线记录(row, names.get(str(row.get("ts_code") or "").split(".", 1)[0].zfill(6)))
        for row in frame.where(frame.notna(), None).to_dict("records")
    ]
    return _market_data_repository().upsert_daily_quotes(rows)
