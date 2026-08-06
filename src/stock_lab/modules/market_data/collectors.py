import pandas as pd

from .helpers import daily_quote_from_source, index_daily_from_source, normalize_symbol, security_from_source
from .repository import MarketDataRepository


def create_default_repository():
    from utils import db

    return MarketDataRepository(db.mysql_localhost, db.engine)


class MarketDataCollector:
    def __init__(self, repository, *, index_source, security_source, quote_source):
        self.repository = repository
        self.index_source = index_source
        self.security_source = security_source
        self.quote_source = quote_source

    def trading_dates(self, limit=160):
        return self.repository.trading_dates(limit)

    def update_index_daily(self, start_date, end_date):
        frame = self.index_source()
        if frame is None or frame.empty:
            raise RuntimeError("AkShare returned no Shanghai index daily data")
        rows = [
            normalize_index_row(row)
            for row in frame.to_dict("records")
            if int(start_date) <= normalize_index_row(row)["trade_date"] <= int(end_date)
        ]
        return self.repository.upsert_index_daily(rows)

    def update_securities(self):
        frame = self.security_source()
        if frame is None or frame.empty:
            raise RuntimeError("Tushare returned no security data")
        rows = [security_from_source(row) for row in frame.where(frame.notna(), None).to_dict("records")]
        return self.repository.replace_securities(rows)

    def update_daily_quotes(self, start_date, end_date):
        dates = [date for date in self.trading_dates(1000) if int(start_date) <= int(date) <= int(end_date)]
        if not dates:
            dates = [int(end_date)]
        frames = [frame for date in dates if (frame := self.quote_source(date)) is not None and not frame.empty]
        if not frames:
            raise RuntimeError(f"Tushare returned no daily quotes for {start_date}-{end_date}")
        names = {normalize_symbol(row.get("symbol")): row.get("name") for row in self.repository.securities()}
        rows = [
            normalize_daily_quote(
                row,
                names.get(str(row.get("ts_code") or "").split(".", 1)[0].zfill(6)),
            )
            for row in pd.concat(frames, ignore_index=True).where(lambda value: value.notna(), None).to_dict("records")
        ]
        return self.repository.upsert_daily_quotes(rows)


def _index_source():
    import akshare as ak

    return ak.stock_zh_index_daily(symbol="sh000001")


def _tushare_client():
    from utils.common import get_tushare_pro

    return get_tushare_pro()


def _security_source():
    return _tushare_client().stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
    )


def _quote_source(trade_date):
    return _tushare_client().daily(ts_code="", trade_date=str(trade_date))


def create_default_collector():
    return MarketDataCollector(
        create_default_repository(),
        index_source=_index_source,
        security_source=_security_source,
        quote_source=_quote_source,
    )


def trading_dates(limit=160):
    dates = sorted(set(create_default_collector().trading_dates(max(int(limit), 1))))
    return dates[-int(limit):]


def normalize_index_row(row):
    return index_daily_from_source(row)


def normalize_daily_quote(row, stock_name=None):
    return daily_quote_from_source(row, stock_name)


def update_index_daily(start_date, end_date):
    collector = create_default_collector()
    collector.repository = create_default_repository()
    return collector.update_index_daily(start_date, end_date)


def update_securities():
    return create_default_collector().update_securities()


def update_daily_quotes(start_date, end_date):
    return create_default_collector().update_daily_quotes(start_date, end_date)
