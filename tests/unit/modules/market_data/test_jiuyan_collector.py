from __future__ import annotations

import pytest

from stock_lab.modules.market_data.jiuyan import (
    HumanVerificationRequired,
    IncompleteJiuyanResponse,
    JiuyanCollector,
)
from stock_lab.modules.market_data.jiuyan_parsing import ParsedJiuyanBatch


def _batch() -> ParsedJiuyanBatch:
    rows = (
        {"data_id": "id-1", "trade_date": 20260805, "stock_code": "000001"},
        {"data_id": "id-2", "trade_date": 20260805, "stock_code": "600000"},
    )
    return ParsedJiuyanBatch(
        rows=rows,
        legacy_rows=(),
        source_board_count=1,
        source_stock_count=3,
        accepted_stock_count=2,
        source_fingerprint="a" * 64,
    )


class _Repository:
    def __init__(self, events=None) -> None:
        self.events = events if events is not None else []
        self.calls = []

    def replace_jiuyan_actions(self, trade_date, rows, manifest):
        self.events.append("repository")
        self.calls.append((trade_date, rows, manifest))
        return len(rows)


def test_collector_retries_with_one_shared_deadline_then_persists_manifest() -> None:
    attempts = []
    deadlines = []

    def source(trade_date, *, deadline, attempt):
        attempts.append(attempt)
        deadlines.append(deadline)
        if attempt == 1:
            raise RuntimeError("temporary")
        return {"payload": True}

    repository = _Repository()
    collector = JiuyanCollector(
        repository,
        source,
        parser=lambda response, trade_date: _batch(),
        monotonic=lambda: 100.0,
    )

    result = collector.collect(20260805)

    assert attempts == [1, 2]
    assert deadlines == [280.0, 280.0]
    assert result == {
        "status": "success",
        "updated": 2,
        "trade_date": 20260805,
        "export_paths": [],
        "warnings": [],
    }
    trade_date, rows, manifest = repository.calls[0]
    assert trade_date == 20260805
    assert rows == list(_batch().rows)
    assert manifest == {
        "trade_date": 20260805,
        "status": "complete",
        "source_board_count": 1,
        "source_stock_count": 3,
        "accepted_stock_count": 2,
        "source_fingerprint": "a" * 64,
    }


def test_collector_stops_immediately_for_human_verification() -> None:
    attempts = []

    def source(trade_date, *, deadline, attempt):
        attempts.append(attempt)
        raise HumanVerificationRequired("slider")

    collector = JiuyanCollector(_Repository(), source, monotonic=lambda: 100.0)

    with pytest.raises(HumanVerificationRequired):
        collector.collect(20260805)

    assert attempts == [1]


def test_collector_exhaustion_does_not_persist_or_export() -> None:
    repository = _Repository()
    exports = []

    def source(trade_date, *, deadline, attempt):
        raise RuntimeError(f"failure {attempt}")

    collector = JiuyanCollector(
        repository,
        source,
        exporter=lambda *args, **kwargs: exports.append((args, kwargs)),
        monotonic=lambda: 100.0,
    )

    with pytest.raises(IncompleteJiuyanResponse, match="failure 2"):
        collector.collect(20260805)

    assert repository.calls == []
    assert exports == []


def test_collector_exports_only_after_repository_success() -> None:
    events = []
    repository = _Repository(events)

    def exporter(trade_date, repository=None):
        events.append("exporter")
        assert trade_date == 20260805
        assert repository is not None
        return ["board.ini", "all.ini"]

    collector = JiuyanCollector(
        repository,
        lambda trade_date, **kwargs: {},
        parser=lambda response, trade_date: _batch(),
        exporter=exporter,
        monotonic=lambda: 100.0,
    )

    result = collector.collect(20260805)

    assert events == ["repository", "exporter"]
    assert result == {
        "status": "success",
        "updated": 2,
        "trade_date": 20260805,
        "export_paths": ["board.ini", "all.ini"],
        "warnings": [],
    }


def test_collector_reports_export_warning_after_repository_success() -> None:
    repository = _Repository()

    def exporter(*args, **kwargs):
        raise OSError("disk full")

    collector = JiuyanCollector(
        repository,
        lambda trade_date, **kwargs: {},
        parser=lambda response, trade_date: _batch(),
        exporter=exporter,
        monotonic=lambda: 100.0,
    )

    result = collector.collect(20260805)

    assert result["status"] == "succeeded_with_warnings"
    assert result["updated"] == 2
    assert result["export_paths"] == []
    assert result["warnings"] == ["disk full"]
