from stock_lab.modules.market_data.collectors import (
    normalize_daily_quote,
    normalize_index_row,
    trading_dates,
    update_daily_quotes,
    update_index_daily,
    update_securities,
)


def 交易日期列表(limit=160):
    return trading_dates(limit)


def 标准化指数行(row):
    return normalize_index_row(row)


def 股票日线记录(row, stock_name=None):
    return normalize_daily_quote(row, stock_name)


def 更新指数日线(start_date, end_date):
    return update_index_daily(start_date, end_date)


def 更新股票基础信息():
    return update_securities()


def 更新股票日线(start_date, end_date):
    return update_daily_quotes(start_date, end_date)
