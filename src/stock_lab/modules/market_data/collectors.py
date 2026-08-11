import time

import pandas as pd

from stock_lab.config import get_settings
from stock_lab.infrastructure.database import create_database_client
from stock_lab.infrastructure.market_data.baostock import BaoStockSource
from stock_lab.infrastructure.market_data.tushare import TushareSource

from .helpers import daily_quote_from_source, index_daily_from_source, normalize_symbol, security_from_source
from .repository import MarketDataRepository


def create_default_repository():
    database = create_database_client()
    return MarketDataRepository(database.query, database.engine)


class MarketDataCollector:
    def __init__(self, repository, *, index_source, security_source, quote_source):
        self.repository = repository
        self.index_source = index_source
        self.security_source = security_source
        self.quote_source = quote_source

    def trading_dates(self, limit=160):
        return self.repository.trading_dates(limit)

    def update_index_daily(self, start_date, end_date):
        frame = self.index_source(start_date, end_date)
        if frame is None or (hasattr(frame, "empty") and frame.empty) or not len(frame):
            raise RuntimeError("BaoStock returned no Shanghai index daily data")
        records = frame.to_dict("records") if hasattr(frame, "to_dict") else frame
        rows = [
            normalize_index_row(row)
            for row in records
            if int(start_date) <= normalize_index_row(row)["trade_date"] <= int(end_date)
        ]
        return self.repository.upsert_index_daily(rows)

    def update_securities(self):
        frame = self.security_source()
        if frame is None or frame.empty:
            raise RuntimeError("Tushare returned no security data")
        rows = [security_from_source(row) for row in frame.where(frame.notna(), None).to_dict("records")]
        return self.repository.replace_securities(rows)

    def update_daily_quotes(self, start_date, end_date, force=False):
        dates = [date for date in self.trading_dates(1000) if int(start_date) <= int(date) <= int(end_date)]
        if not dates:
            dates = [int(end_date)]
        if not force:
            existing = set(self.repository.daily_quote_dates(start_date, end_date))
            dates = [date for date in dates if int(date) not in existing]
        if not dates:
            return 0
        frames = []
        for date in dates:
            started_at = time.monotonic()
            try:
                frame = self.quote_source(date)
            except Exception as error:
                if "频率" not in str(error):
                    raise
                time.sleep(65)
                frame = self.quote_source(date)
            if frame is not None and not frame.empty:
                frames.append(frame)
            time.sleep(max(0.0, 1.3 - (time.monotonic() - started_at)))
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


def create_default_collector():
    settings = get_settings()
    index_source = BaoStockSource()
    tushare_source = TushareSource(settings.tushare_tokens)
    return MarketDataCollector(
        create_default_repository(),
        index_source=index_source.fetch_index_daily,
        security_source=tushare_source.fetch_securities,
        quote_source=tushare_source.fetch_daily_quotes,
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


def update_daily_quotes(start_date, end_date, force=False):
    return create_default_collector().update_daily_quotes(
        start_date,
        end_date,
        force=force,
    )
