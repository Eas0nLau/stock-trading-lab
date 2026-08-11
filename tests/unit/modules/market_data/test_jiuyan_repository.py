from __future__ import annotations

from datetime import datetime

import pytest

from stock_lab.modules.market_data.repository import MarketDataRepository
from stock_lab.shared.errors import DataValidationError


class _Result:
    def __init__(self, scalar_value: int | None = None) -> None:
        self._scalar_value = scalar_value

    def scalar_one(self) -> int:
        assert self._scalar_value is not None
        return self._scalar_value


class _Connection:
    def __init__(self, persisted_count: int = 1, fail_at: int | None = None) -> None:
        self.persisted_count = persisted_count
        self.fail_at = fail_at
        self.calls: list[tuple[str, object | None]] = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters))
        if self.fail_at == len(self.calls):
            raise RuntimeError("transaction failed")
        if "COUNT(*)" in str(statement):
            return _Result(self.persisted_count)
        return _Result()


class _Transaction:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection
        self.begin_count = 0

    def begin(self) -> _Transaction:
        self.begin_count += 1
        return _Transaction(self.connection)


def _row(*, trade_date: int = 20260806) -> dict[str, object]:
    return {
        "data_id": "20260806_hash",
        "trade_date": trade_date,
        "board_name": "robotics",
        "board_stock_count": 12,
        "stock_code": "000001",
        "stock_name": "Ping An Bank",
        "source_code": "000001.SZ",
        "limit_up_at": datetime(2026, 8, 6, 10, 0),
        "board_streak": "first",
        "change_pct": 10.0,
        "limit_up_reason": "test",
    }


def _manifest(**overrides) -> dict[str, object]:
    manifest = {
        "trade_date": 20260806,
        "status": "complete",
        "source_board_count": 1,
        "source_stock_count": 1,
        "accepted_stock_count": 1,
        "source_fingerprint": "a" * 64,
    }
    manifest.update(overrides)
    return manifest


def _repository(connection: _Connection) -> tuple[MarketDataRepository, _Engine]:
    engine = _Engine(connection)
    return MarketDataRepository(lambda *args, **kwargs: [], engine), engine


def test_replace_jiuyan_actions_is_one_complete_day_transaction() -> None:
    connection = _Connection()
    repository, engine = _repository(connection)

    count = repository.replace_jiuyan_actions(20260806, [_row()], _manifest())

    assert count == 1
    assert engine.begin_count == 1
    sql = [statement for statement, _ in connection.calls]
    assert "DELETE FROM `jiuyan_actions` WHERE `trade_date` = :trade_date" in sql[0]
    assert "INSERT INTO `jiuyan_actions`" in sql[1]
    assert "INSERT INTO `jiuyan_collection_days`" in sql[2]
    assert "COUNT(*)" in sql[3]


@pytest.mark.parametrize(
    ("rows", "manifest"),
    [
        ([_row()], _manifest(trade_date=20260805)),
        ([_row(trade_date=20260805)], _manifest()),
        ([_row()], _manifest(status="partial")),
        ([_row()], _manifest(source_fingerprint="a" * 63)),
        ([_row()], _manifest(source_fingerprint="A" * 64)),
        ([_row()], _manifest(accepted_stock_count=2)),
    ],
)
def test_replace_jiuyan_actions_validates_before_transaction(rows, manifest) -> None:
    repository, engine = _repository(_Connection())

    with pytest.raises(DataValidationError):
        repository.replace_jiuyan_actions(20260806, rows, manifest)

    assert engine.begin_count == 0


def test_replace_jiuyan_actions_rejects_persisted_count_mismatch() -> None:
    repository, _ = _repository(_Connection(persisted_count=0))

    with pytest.raises(DataValidationError, match="Persisted Jiuyan count mismatch"):
        repository.replace_jiuyan_actions(20260806, [_row()], _manifest())


def test_replace_jiuyan_actions_stops_after_transaction_exception() -> None:
    connection = _Connection(fail_at=2)
    repository, _ = _repository(connection)

    with pytest.raises(RuntimeError, match="transaction failed"):
        repository.replace_jiuyan_actions(20260806, [_row()], _manifest())

    assert len(connection.calls) == 2


def test_jiuyan_read_methods_use_canonical_parameterized_queries() -> None:
    calls = []
    results = iter([
        [{"trade_date": 20260806, "stock_code": "000001"}],
        [{"trade_date": 20260806, "status": "complete"}],
        [{"trade_date": 20260806}],
    ])

    def query(sql, params=None, fetch=False):
        calls.append((sql, params, fetch))
        return next(results)

    repository = MarketDataRepository(query)

    assert repository.jiuyan_actions_for_date(20260806)[0]["stock_code"] == "000001"
    assert repository.jiuyan_collection_day(20260806)["status"] == "complete"
    assert repository.latest_complete_jiuyan_date() == 20260806
    assert calls[0][1] == (20260806,)
    assert calls[1][1] == (20260806,)
    assert calls[2][1] == ("complete",)
    assert all("t_韭研公社异动解析" not in sql for sql, _, _ in calls)
