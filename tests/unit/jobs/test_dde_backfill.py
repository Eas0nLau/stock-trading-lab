from stock_lab.jobs.dde_backfill import update_dde


class Source:
    def __init__(self, failing=(), empty=()):
        self.failing = set(failing)
        self.empty = set(empty)
        self.calls = []

    def fetch_daily_dde(
        self,
        stock_code,
        *,
        start_date,
        end_date,
        timeout,
        retries,
    ):
        self.calls.append((stock_code, start_date, end_date, timeout, retries))
        if stock_code in self.failing:
            raise RuntimeError("source down")
        if stock_code in self.empty:
            return []
        return [
            {"stock_code": stock_code, "trade_date": start_date, "dde": 100},
            {"stock_code": stock_code, "trade_date": end_date, "dde": 200},
        ]


class Repository:
    def __init__(self):
        self.updates = []

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        assert stock_codes is None
        return [
            {"ts_code": "600000.SH", "trade_date": start_date, "dde_net_amount": None},
            {"ts_code": "000001.SZ", "trade_date": start_date, "dde_net_amount": None},
            {"ts_code": "000001.SZ", "trade_date": end_date, "dde_net_amount": None},
        ]

    def update_daily_quote_enrichment(self, rows, fields, only_missing=False):
        rows = list(rows)
        self.updates.append((rows, fields, only_missing))
        return len(rows)


def test_dde_backfill_fetches_each_pending_symbol_and_updates_only_dde():
    source = Source()
    repository = Repository()

    result = update_dde(
        20260806,
        20260807,
        source=source,
        repository=repository,
        max_workers=2,
    )

    assert {(code, start, end) for code, start, end, _, _ in source.calls} == {
        ("000001.SZ", 20260806, 20260807),
        ("600000.SH", 20260806, 20260807),
    }
    assert result == {
        "status": "success",
        "updated": 4,
        "processed_codes": ["000001.SZ", "600000.SH"],
        "empty_codes": [],
        "failed": [],
    }
    assert all(fields == ("dde_net_amount",) for _, fields, _ in repository.updates)
    assert all(only_missing is True for _, _, only_missing in repository.updates)


def test_dde_backfill_keeps_successful_writes_and_reports_failures():
    source = Source(failing={"600000.SH"})
    repository = Repository()

    result = update_dde(
        20260806,
        20260807,
        source=source,
        repository=repository,
        max_workers=2,
    )

    assert result["status"] == "failed"
    assert result["processed_codes"] == ["000001.SZ"]
    assert result["failed"] == [{"stock_code": "600000.SH", "error": "source down"}]
    assert len(repository.updates) == 1


def test_dde_backfill_tracks_empty_codes_and_force_mode():
    source = Source(empty={"600000.SH"})
    repository = Repository()

    result = update_dde(
        20260806,
        20260807,
        source=source,
        repository=repository,
        force=True,
        max_workers=1,
    )

    assert result["status"] == "success"
    assert result["empty_codes"] == ["600000.SH"]
    assert repository.updates[0][2] is False
