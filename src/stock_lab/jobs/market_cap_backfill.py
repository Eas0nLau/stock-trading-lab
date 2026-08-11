import datetime as dt
import time

from stock_lab.infrastructure.market_data.tushare import TushareSource
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.helpers import (
    market_cap_from_source,
    normalize_trade_date,
    normalize_ts_code,
)


MARKET_CAP_FIELDS = (
    "total_market_value",
    "circulating_market_value",
    "free_float_shares",
    "free_float_market_value",
)


def _default_source():
    from stock_lab.config import get_settings

    return TushareSource(get_settings().tushare_tokens)


def _records(frame):
    if frame is None or (hasattr(frame, "empty") and frame.empty):
        return []
    if hasattr(frame, "where") and hasattr(frame, "to_dict"):
        return frame.where(frame.notna(), None).to_dict("records")
    return list(frame)


def update_market_cap(
    start_date=None,
    end_date=None,
    *,
    source=None,
    repository=None,
    force=False,
    rate_delay=0.2,
    sleep=time.sleep,
):
    today = int(dt.date.today().strftime("%Y%m%d"))
    start_date = normalize_trade_date(start_date or today)
    end_date = normalize_trade_date(end_date or start_date)
    if not start_date or not end_date or start_date > end_date:
        raise ValueError(f"Invalid market-cap date range: {start_date}-{end_date}")
    source = source or _default_source()
    repository = repository or create_default_repository()
    dates = sorted({
        int(value)
        for value in repository.trading_dates(10000)
        if start_date <= int(value) <= end_date
    }, reverse=True)
    result = {
        "status": "success",
        "updated": 0,
        "processed_dates": [],
        "failed_dates": [],
        "errors": [],
    }
    for index, trade_date in enumerate(dates):
        if index and rate_delay > 0:
            sleep(rate_delay)
        try:
            source_rows = _records(source.fetch_daily_basic(trade_date))
            if not source_rows:
                raise ValueError("Tushare daily_basic returned no data")
            source_rows = [
                row for row in source_rows
                if normalize_trade_date(row.get("trade_date")) == trade_date
            ]
            if not source_rows:
                raise ValueError(
                    "Tushare daily_basic returned no rows for requested date"
                )
            quotes = repository.daily_quotes(
                start_date=trade_date,
                end_date=trade_date,
            )
            closes = {
                normalize_ts_code(row.get("ts_code")): row.get("close_price")
                for row in quotes
            }
            rows = [
                market_cap_from_source(row, closes[code])
                for row in source_rows
                if (code := normalize_ts_code(row.get("ts_code"))) in closes
            ]
            if not rows:
                raise ValueError("daily_basic did not match canonical daily quotes")
            result["updated"] += repository.update_daily_quote_enrichment(
                rows,
                MARKET_CAP_FIELDS,
                only_missing=not force,
            )
            result["processed_dates"].append(trade_date)
        except Exception as error:
            result["failed_dates"].append(trade_date)
            result["errors"].append({
                "trade_date": trade_date,
                "error": str(error),
            })
    if result["failed_dates"]:
        result["status"] = "failed"
    return result
