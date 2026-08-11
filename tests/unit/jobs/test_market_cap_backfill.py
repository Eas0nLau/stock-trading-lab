import pandas as pd

from stock_lab.jobs.market_cap_backfill import update_market_cap


class Source:
    def __init__(self, empty_dates=()):
        self.empty_dates = set(empty_dates)
        self.calls = []

    def fetch_daily_basic(self, trade_date):
        self.calls.append(trade_date)
        if trade_date in self.empty_dates:
            return pd.DataFrame()
        return pd.DataFrame([{
            "ts_code": "000001.SZ",
            "trade_date": trade_date,
            "total_mv": 10000,
            "circ_mv": 8000,
            "free_share": 500,
        }])


class Repository:
    def __init__(self):
        self.updates = []

    def trading_dates(self, _limit):
        return [20260805, 20260806, 20260807]

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        assert stock_codes is None
        assert start_date == end_date
        return [{
            "ts_code": "000001.SZ",
            "trade_date": start_date,
            "close_price": 12.5,
        }]

    def update_daily_quote_enrichment(self, rows, fields, only_missing=False):
        rows = list(rows)
        self.updates.append((rows, fields, only_missing))
        return len(rows)


def test_market_cap_backfill_updates_existing_quotes_newest_first():
    source = Source()
    repository = Repository()
    sleeps = []

    result = update_market_cap(
        20260806,
        20260807,
        source=source,
        repository=repository,
        rate_delay=0.2,
        sleep=sleeps.append,
    )

    assert source.calls == [20260807, 20260806]
    assert sleeps == [0.2]
    assert result == {
        "status": "success",
        "updated": 2,
        "processed_dates": [20260807, 20260806],
        "failed_dates": [],
        "errors": [],
    }
    rows, fields, only_missing = repository.updates[0]
    assert fields == (
        "total_market_value",
        "circulating_market_value",
        "free_float_shares",
        "free_float_market_value",
    )
    assert only_missing is True
    assert rows[0]["free_float_market_value"] == 6250


def test_market_cap_backfill_reports_empty_source_and_continues():
    source = Source(empty_dates={20260807})
    repository = Repository()

    result = update_market_cap(
        20260806,
        20260807,
        source=source,
        repository=repository,
        rate_delay=0,
    )

    assert result["status"] == "failed"
    assert result["processed_dates"] == [20260806]
    assert result["failed_dates"] == [20260807]
    assert "returned no data" in result["errors"][0]["error"]
    assert len(repository.updates) == 1


def test_market_cap_force_updates_valid_values_but_still_preserves_nulls():
    repository = Repository()

    update_market_cap(
        20260807,
        20260807,
        source=Source(),
        repository=repository,
        force=True,
        rate_delay=0,
    )

    assert repository.updates[0][2] is False
