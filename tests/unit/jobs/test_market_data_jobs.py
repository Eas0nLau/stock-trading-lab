from stock_lab.jobs.intraday_bars_5m import fetch_intraday_bars_5m, update_intraday_bars_5m
import pytest

from stock_lab.jobs.kdj_indicators import (
    update_kdj_indicators,
    update_latest_kdj_indicators,
)
from stock_lab.shared.errors import DataValidationError


class Source:
    def fetch_5m_bars(self, start_date, end_date, ts_code):
        return [{
            "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
            "open": "10", "high": "11", "low": "9", "close": "10.5",
            "volume": "100", "amount": "1050", "adjustflag": "3",
        }]


class Repository:
    def __init__(self, dates=None):
        self.intraday_rows = None
        self.kdj_rows = None
        self.dates = [20260806] if dates is None else dates
        self.requested_stock_codes = None

    def upsert_intraday_bars_5m(self, rows):
        self.intraday_rows = list(rows)
        return len(self.intraday_rows)

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        self.requested_stock_codes = stock_codes
        return [
            {"ts_code": "000001.SZ", "trade_date": 20260805, "low_price": 9, "high_price": 11, "close_price": 10},
            {"ts_code": "000001.SZ", "trade_date": 20260806, "low_price": 10, "high_price": 12, "close_price": 11},
        ]

    def upsert_kdj_indicators(self, rows):
        self.kdj_rows = list(rows)
        return len(self.kdj_rows)

    def trading_dates(self, limit):
        assert limit == 1
        return self.dates


def test_intraday_job_uses_injected_source_and_repository():
    repository = Repository()

    rows = fetch_intraday_bars_5m(20260806, 20260806, "000001.SZ", source=Source())
    count = update_intraday_bars_5m(20260806, 20260806, "000001.SZ", source=Source(), repository=repository)

    assert rows[0]["stock_code"] == "000001"
    assert count == 1
    assert repository.intraday_rows == rows


@pytest.mark.parametrize("change", [
    {"code": "sh.600000"},
    {"date": "2026-08-07", "time": "20260807093500000"},
])
def test_intraday_job_rejects_rows_outside_requested_scope(change):
    class MismatchedSource(Source):
        def fetch_5m_bars(self, start_date, end_date, ts_code):
            row = super().fetch_5m_bars(start_date, end_date, ts_code)[0]
            row.update(change)
            return [row]

    with pytest.raises(DataValidationError, match="requested"):
        fetch_intraday_bars_5m(
            20260806,
            20260806,
            "000001.SZ",
            source=MismatchedSource(),
        )


def test_kdj_job_reads_daily_quotes_and_limits_writes_to_requested_dates():
    repository = Repository()

    count = update_kdj_indicators(20260806, 20260806, repository=repository)

    assert count == 1
    assert repository.kdj_rows[0]["trade_date"] == 20260806
    assert repository.kdj_rows[0]["data_id"] == "000001.SZ_20260806"


def test_latest_kdj_job_uses_latest_canonical_trading_date():
    repository = Repository(dates=[20260805, 20260806])

    count = update_latest_kdj_indicators(
        stock_codes=["000001.SZ"],
        repository=repository,
    )

    assert count == 1
    assert repository.requested_stock_codes == ["000001.SZ"]
    assert repository.kdj_rows[0]["trade_date"] == 20260806


def test_latest_kdj_job_rejects_empty_trading_calendar():
    with pytest.raises(DataValidationError, match="No trading date"):
        update_latest_kdj_indicators(repository=Repository(dates=[]))


def test_kdj_job_rejects_reversed_range_before_query():
    repository = Repository()

    with pytest.raises(DataValidationError, match="range"):
        update_kdj_indicators(20260807, 20260806, repository=repository)

    assert repository.requested_stock_codes is None


def test_kdj_job_rejects_impossible_calendar_date_before_query():
    repository = Repository()

    with pytest.raises(DataValidationError, match="date"):
        update_kdj_indicators(20260231, 20260231, repository=repository)

    assert repository.requested_stock_codes is None
