from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
    def __init__(self, persisted_count: int) -> None:
        self.persisted_count = persisted_count
        self.calls: list[tuple[str, object | None]] = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.calls.append((sql, parameters))
        if "COUNT(*)" in sql:
            return _Result(self.persisted_count)
        return _Result()


def _row(*, trade_date: int = 20260811) -> dict[str, object]:
    return {
        "data_id": "20260811-000001-board",
        "trade_date": trade_date,
        "board_name": "测试板块",
        "board_stock_count": 1,
        "stock_code": "000001",
        "stock_name": "平安银行",
        "source_code": "000001.SZ",
        "limit_up_at": datetime(2026, 8, 11, 10, 0),
        "board_streak": "首板",
        "change_pct": 10.0,
        "limit_up_reason": "测试",
    }


def test_replace_jiuyan_actions_replaces_rows_and_writes_complete_manifest() -> None:
    connection = _Connection(persisted_count=1)

    persisted = MarketDataRepository.replace_jiuyan_actions(
        connection,
        trade_date=20260811,
        rows=[_row()],
        expected_row_count=1,
    )

    assert persisted == 1
    assert len(connection.calls) == 4
    sql_calls = [sql.replace("`", "") for sql, _ in connection.calls]
    assert "DELETE FROM jiuyan_actions" in sql_calls[0]
    assert "INSERT INTO jiuyan_actions" in sql_calls[1]
    assert "INSERT INTO jiuyan_collection_days" in sql_calls[2]
    assert "COUNT(*)" in connection.calls[3][0]
    manifest = connection.calls[2][1]
    assert manifest == {
        "trade_date": 20260811,
        "row_count": 1,
        "status": "complete",
    }


@pytest.mark.parametrize(
    ("rows", "expected_row_count", "persisted_count"),
    [
        ([_row(trade_date=20260808)], 1, 1),
        ([_row()], 2, 1),
        ([_row()], 1, 0),
    ],
)
def test_replace_jiuyan_actions_rejects_inconsistent_batches(
    rows: list[dict[str, object]],
    expected_row_count: int,
    persisted_count: int,
) -> None:
    connection = _Connection(persisted_count=persisted_count)

    with pytest.raises(DataValidationError):
        MarketDataRepository.replace_jiuyan_actions(
            connection,
            trade_date=20260811,
            rows=rows,
            expected_row_count=expected_row_count,
        )


def test_jiuyan_manifest_migration_defines_complete_day_contract() -> None:
    migration = (
        Path(__file__).parents[4]
        / "db"
        / "migrations"
        / "006_create_jiuyan_collection_days.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS `jiuyan_collection_days`" in migration
    assert "`trade_date` int NOT NULL" in migration
    assert "`row_count` int NOT NULL" in migration
    assert "`status` varchar(16) NOT NULL" in migration
    assert "PRIMARY KEY (`trade_date`)" in migration
