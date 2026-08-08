from stock_lab.jobs.intraday_bars_5m import fetch_intraday_bars_5m, update_intraday_bars_5m
from stock_lab.jobs.kdj_indicators import update_kdj_indicators


class Source:
    def fetch_5m_bars(self, start_date, end_date, ts_code):
        return [{
            "date": "2026-08-06", "time": "20260806093500000", "code": "sz.000001",
            "open": "10", "high": "11", "low": "9", "close": "10.5",
            "volume": "100", "amount": "1050", "adjustflag": "3",
        }]


class Repository:
    def __init__(self):
        self.intraday_rows = None
        self.kdj_rows = None

    def upsert_intraday_bars_5m(self, rows):
        self.intraday_rows = list(rows)
        return len(self.intraday_rows)

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        return [
            {"ts_code": "000001.SZ", "trade_date": 20260805, "low_price": 9, "high_price": 11, "close_price": 10},
            {"ts_code": "000001.SZ", "trade_date": 20260806, "low_price": 10, "high_price": 12, "close_price": 11},
        ]

    def upsert_kdj_indicators(self, rows):
        self.kdj_rows = list(rows)
        return len(self.kdj_rows)


def test_intraday_job_uses_injected_source_and_repository():
    repository = Repository()

    rows = fetch_intraday_bars_5m(20260806, 20260806, "000001.SZ", source=Source())
    count = update_intraday_bars_5m(20260806, 20260806, "000001.SZ", source=Source(), repository=repository)

    assert rows[0]["stock_code"] == "000001"
    assert count == 1
    assert repository.intraday_rows == rows


def test_kdj_job_reads_daily_quotes_and_limits_writes_to_requested_dates():
    repository = Repository()

    count = update_kdj_indicators(20260806, 20260806, repository=repository)

    assert count == 1
    assert repository.kdj_rows[0]["trade_date"] == 20260806
    assert repository.kdj_rows[0]["data_id"] == "000001.SZ_20260806"
