from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from stock_lab.modules.ths import (
    ThsBoard,
    ThsBoardConstituent,
    ThsRepository,
    ThsStockRelation,
)


class RecordingQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, sql, params=None, fetch=False):
        self.calls.append((sql, params, fetch))
        return self.rows


def test_boards_returns_frozen_canonical_models_and_filters_by_type():
    updated_at = datetime(2026, 8, 7, 9, 30)
    query = RecordingQuery([
        {
            "board_code": "885001",
            "board_type": "concept",
            "board_name": "Example concept",
            "page_code": "301558",
            "detail_path": "885001",
            "collected_date": 20260807,
            "updated_at": updated_at,
        }
    ])

    result = ThsRepository(query).boards(board_type="concept")

    assert result == [
        ThsBoard(
            board_code="885001",
            board_type="concept",
            board_name="Example concept",
            page_code="301558",
            detail_path="885001",
            collected_date=20260807,
            updated_at=updated_at,
        )
    ]
    sql, params, fetch = query.calls[0]
    assert "FROM `ths_boards`" in sql
    assert "WHERE `board_type` = %s" in sql
    assert sql.endswith("ORDER BY `board_type`, `board_name`, `board_code`")
    assert params == ("concept",)
    assert fetch is True
    with pytest.raises(FrozenInstanceError):
        result[0].board_name = "Changed"


@pytest.mark.parametrize(
    ("filters", "expected_where", "expected_params"),
    [
        ({"board_code": "885001"}, "`board_code` = %s", ("885001",)),
        ({"board_type": "industry"}, "`board_type` = %s", ("industry",)),
        ({"stock_code": "000001"}, "`stock_code` = %s", ("000001",)),
        (
            {"board_code": "885001", "board_type": "concept", "stock_code": "000001"},
            "`board_code` = %s AND `board_type` = %s AND `stock_code` = %s",
            ("885001", "concept", "000001"),
        ),
    ],
)
def test_board_constituents_supports_canonical_filters(filters, expected_where, expected_params):
    updated_at = datetime(2026, 8, 7, 9, 30)
    row = {
        "board_code": "885001",
        "stock_code": "000001",
        "board_type": "concept",
        "board_name": "Example concept",
        "page_code": "301558",
        "stock_name": "Example stock",
        "collected_date": 20260807,
        "updated_at": updated_at,
    }
    query = RecordingQuery([row])

    result = ThsRepository(query).board_constituents(**filters)

    assert result == [ThsBoardConstituent(**row)]
    sql, params, fetch = query.calls[0]
    assert "FROM `ths_board_constituents`" in sql
    assert f"WHERE {expected_where}" in sql
    assert sql.endswith("ORDER BY `board_code`, `stock_code`")
    assert params == expected_params
    assert fetch is True


def test_stock_relations_reads_all_rows_or_filters_by_stock_code():
    updated_at = datetime(2026, 8, 7, 9, 30)
    row = {
        "stock_code": "000001",
        "stock_name": "Example stock",
        "industry_names": "Banking",
        "industry_codes": "881155",
        "concept_names": None,
        "concept_codes": None,
        "collected_date": 20260807,
        "updated_at": updated_at,
    }
    query = RecordingQuery([row])
    repository = ThsRepository(query)

    assert repository.stock_relations() == [ThsStockRelation(**row)]
    assert query.calls[-1][1] is None
    assert "WHERE" not in query.calls[-1][0]

    assert repository.stock_relations(stock_code="000001") == [ThsStockRelation(**row)]
    sql, params, fetch = query.calls[-1]
    assert "FROM `ths_stock_relations`" in sql
    assert "WHERE `stock_code` = %s" in sql
    assert sql.endswith("ORDER BY `stock_code`")
    assert params == ("000001",)
    assert fetch is True


def test_repository_exposes_no_database_write_capability():
    repository = ThsRepository(RecordingQuery([]))
    write_prefixes = ("add", "create", "delete", "insert", "replace", "save", "update", "upsert", "write")

    assert not hasattr(repository, "_engine")
    assert not any(
        name.startswith(write_prefixes)
        for name in dir(repository)
        if not name.startswith("_")
    )
