import datetime as dt
import time
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


def _read_index_dates(limit):
    rows = _db().mysql_localhost(
        f"SELECT DISTINCT `日期` FROM `akshare_sh000001` ORDER BY `日期` DESC LIMIT {int(limit)}",
        fetch=True,
    ) or []
    return [_date_int(row.get("日期")) for row in rows if _date_int(row.get("日期"))]


def 交易日期列表(limit=160):
    dates = sorted(set(_read_index_dates(max(int(limit), 1))), reverse=False)
    return dates[-int(limit):]


def 待更新交易日期(dates, existing_dates):
    existing = {int(date) for date in existing_dates}
    return [int(date) for date in dates if int(date) not in existing]


def 标准化指数行(row):
    return {
        "日期": _date_int(row.get("date", row.get("日期"))),
        "开盘": _to_float(row.get("open", row.get("开盘"))),
        "收盘": _to_float(row.get("close", row.get("收盘"))),
        "最高": _to_float(row.get("high", row.get("最高"))),
        "最低": _to_float(row.get("low", row.get("最低"))),
        "成交量": _to_float(row.get("volume", row.get("成交量"))),
        "成交额": _to_float(row.get("amount", row.get("成交额"))),
        "振幅": _to_float(row.get("amplitude", row.get("振幅"))),
        "涨跌幅": _to_float(row.get("pct_chg", row.get("涨跌幅"))),
        "涨跌额": _to_float(row.get("change", row.get("涨跌额"))),
        "换手率": _to_float(row.get("turnover", row.get("换手率"))),
    }


def 股票日线记录(row, stock_name=None):
    code = _symbol_int(row.get("ts_code", row.get("symbol")))
    date = _date_int(row.get("trade_date", row.get("date")))
    return {
        "ts_code": code,
        "trade_date": date,
        "open": _to_float(row.get("open")),
        "high": _to_float(row.get("high")),
        "low": _to_float(row.get("low")),
        "close": _to_float(row.get("close")),
        "pre_close": _to_float(row.get("pre_close")),
        "change": _to_float(row.get("change")),
        "pct_chg": _to_float(row.get("pct_chg")),
        "vol": _to_float(row.get("vol")),
        "amount": _to_float(row.get("amount")),
        "total_mv": _to_float(row.get("total_mv")),
        "circ_mv": _to_float(row.get("circ_mv")),
        "free_share": _to_float(row.get("free_share")),
        "free_mv": _to_float(row.get("free_mv")),
        "stock_name": stock_name or row.get("stock_name"),
        "data_id": f"{code}_{date}",
        "dde": _to_float(row.get("dde")),
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
    columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"]
    return _upsert_rows("akshare_sh000001", columns, rows, ["日期"])


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
    columns = ["ts_code", "symbol", "name", "area", "industry", "market", "list_date", "list_status"]
    return _replace_rows("stock_basic", columns, rows)


def 更新股票日线(start_date, end_date):
    from utils.common import pro

    all_dates = sorted([
        date for date in _read_index_dates(1000)
        if int(start_date) <= int(date) <= int(end_date)
    ])
    if not all_dates:
        all_dates = [int(end_date)]
    existing_rows = _db().mysql_localhost(
        "SELECT DISTINCT trade_date FROM stock_daily WHERE trade_date BETWEEN %s AND %s",
        params=(int(start_date), int(end_date)),
        fetch=True,
    ) or []
    dates = 待更新交易日期(all_dates, [row.get("trade_date") for row in existing_rows])
    if not dates:
        return 0
    names = {
        _symbol_int(row.get("symbol")): row.get("name")
        for row in (_db().mysql_localhost("SELECT symbol, name FROM stock_basic", fetch=True) or [])
    }
    columns = [
        "ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg",
        "vol", "amount", "total_mv", "circ_mv", "free_share", "free_mv", "stock_name", "data_id", "dde",
    ]
    total_rows = 0
    for date in dates:
        started_at = time.monotonic()
        try:
            frame = pro.daily(ts_code="", trade_date=str(date))
        except Exception as error:
            if "频率" not in str(error):
                raise
            time.sleep(65)
            frame = pro.daily(ts_code="", trade_date=str(date))
        if frame is None or frame.empty:
            raise RuntimeError(f"Tushare 未返回 {date} 股票日线")
        rows = [
            股票日线记录(row, names.get(_symbol_int(row.get("ts_code"))))
            for row in frame.where(frame.notna(), None).to_dict("records")
        ]
        total_rows += _upsert_rows("stock_daily", columns, rows, ["data_id"])
        time.sleep(max(0.0, 1.3 - (time.monotonic() - started_at)))
    return total_rows
