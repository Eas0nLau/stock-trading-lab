import threading

import pytest

from stock_lab.jobs.intraday_bars_5m import backfill_intraday_bars_5m
from stock_lab.shared.errors import DataValidationError


def source_row(ts_code, *, close="10.5"):
    symbol, exchange = ts_code.split(".")
    return {
        "date": "2026-08-06",
        "time": "20260806093500000",
        "code": f"{exchange.lower()}.{symbol}",
        "open": "10",
        "high": "11",
        "low": "9",
        "close": close,
        "volume": "100",
        "amount": "1050",
        "adjustflag": "3",
    }


class SourceFactory:
    def __init__(self, *, failing=(), empty=(), malformed=()):
        self.failing = set(failing)
        self.empty = set(empty)
        self.malformed = set(malformed)
        self.calls = []

    def __call__(self):
        factory = self

        class Source:
            def fetch_5m_bars(self, start_date, end_date, ts_code):
                factory.calls.append((start_date, end_date, ts_code))
                if ts_code in factory.failing:
                    raise RuntimeError("source down")
                if ts_code in factory.empty:
                    return []
                close = "bad" if ts_code in factory.malformed else "10.5"
                return [source_row(ts_code, close=close)]

        return Source()


class Repository:
    def __init__(self, securities=None):
        self.security_rows = securities if securities is not None else [
            {"ts_code": "600000.SH"},
            {"ts_code": "000001.SZ"},
        ]
        self.writes = []

    def securities(self):
        return self.security_rows

    def upsert_intraday_bars_5m(self, rows):
        rows = list(rows)
        self.writes.append((threading.get_ident(), rows))
        return len(rows)


def test_intraday_backfill_processes_explicit_codes_and_sorts_results():
    repository = Repository()
    factory = SourceFactory()
    coordinator_thread = threading.get_ident()

    result = backfill_intraday_bars_5m(
        20260806,
        20260807,
        stock_codes=["600000.SH", "000001.SZ"],
        source_factory=factory,
        repository=repository,
        max_workers=2,
    )

    assert result == {
        "status": "success",
        "updated": 2,
        "processed_codes": ["000001.SZ", "600000.SH"],
        "empty_codes": [],
        "failed": [],
    }
    assert {call[2] for call in factory.calls} == {"000001.SZ", "600000.SH"}
    assert all(thread_id == coordinator_thread for thread_id, _rows in repository.writes)


def test_intraday_backfill_uses_canonical_security_universe():
    factory = SourceFactory()

    result = backfill_intraday_bars_5m(
        20260806,
        20260806,
        source_factory=factory,
        repository=Repository([{"ts_code": "000001.SZ"}]),
        max_workers=1,
    )

    assert result["processed_codes"] == ["000001.SZ"]
    assert [call[2] for call in factory.calls] == ["000001.SZ"]


def test_intraday_backfill_keeps_successful_writes_on_partial_failure():
    repository = Repository()

    result = backfill_intraday_bars_5m(
        20260806,
        20260806,
        source_factory=SourceFactory(failing={"600000.SH"}),
        repository=repository,
        max_workers=2,
    )

    assert result["status"] == "failed"
    assert result["processed_codes"] == ["000001.SZ"]
    assert result["failed"] == [
        {"stock_code": "600000.SH", "error": "source down"}
    ]
    assert len(repository.writes) == 1


def test_intraday_backfill_isolates_malformed_security():
    repository = Repository()

    result = backfill_intraday_bars_5m(
        20260806,
        20260806,
        source_factory=SourceFactory(malformed={"600000.SH"}),
        repository=repository,
        max_workers=2,
    )

    assert result["status"] == "failed"
    assert result["processed_codes"] == ["000001.SZ"]
    assert result["failed"][0]["stock_code"] == "600000.SH"
    assert "close" in result["failed"][0]["error"]
    assert len(repository.writes) == 1


def test_intraday_backfill_fails_when_every_security_is_empty():
    result = backfill_intraday_bars_5m(
        20260806,
        20260806,
        source_factory=SourceFactory(empty={"000001.SZ", "600000.SH"}),
        repository=Repository(),
        max_workers=2,
    )

    assert result["status"] == "failed"
    assert result["updated"] == 0
    assert result["empty_codes"] == ["000001.SZ", "600000.SH"]


def test_intraday_backfill_rejects_empty_universe():
    with pytest.raises(DataValidationError, match="No securities"):
        backfill_intraday_bars_5m(
            20260806,
            20260806,
            source_factory=SourceFactory(),
            repository=Repository([]),
        )


def test_intraday_backfill_rejects_non_positive_worker_count():
    with pytest.raises(DataValidationError, match="max_workers"):
        backfill_intraday_bars_5m(
            20260806,
            20260806,
            stock_codes=["000001.SZ"],
            source_factory=SourceFactory(),
            repository=Repository(),
            max_workers=0,
        )
