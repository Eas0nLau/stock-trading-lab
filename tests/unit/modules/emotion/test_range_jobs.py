from __future__ import annotations

import pytest

from stock_lab.modules.emotion.jobs import (
    backfill_hot_board_emotion,
    backfill_index_emotion,
)
from stock_lab.shared.errors import DataValidationError


class _Repository:
    def __init__(self, dates=(20260804, 20260805, 20260806)) -> None:
        self.dates = list(dates)

    def trading_dates(self, start_date=None, end_date=None):
        return [
            date
            for date in self.dates
            if (start_date is None or date >= start_date)
            and (end_date is None or date <= end_date)
        ]

    def previous_trading_date(self, trade_date):
        previous = [date for date in self.dates if date < trade_date]
        return previous[-1] if previous else None


def test_index_backfill_normalizes_reversed_range_and_runs_ascending() -> None:
    repository = _Repository()
    calls = []

    result = backfill_index_emotion(
        20260806,
        20260804,
        repository=repository,
        runner=lambda trade_date, repository=None: calls.append(trade_date) or 1,
    )

    assert calls == [20260804, 20260805, 20260806]
    assert result == {
        "status": "success",
        "updated": 3,
        "processed_dates": [20260804, 20260805, 20260806],
        "failed_dates": [],
        "errors": [],
    }


def test_hot_board_backfill_uses_previous_canonical_session() -> None:
    repository = _Repository()
    calls = []

    result = backfill_hot_board_emotion(
        20260804,
        20260806,
        repository=repository,
        runner=lambda trade_date, previous_date, repository=None: calls.append(
            (trade_date, previous_date)
        ) or 2,
    )

    assert calls == [(20260805, 20260804), (20260806, 20260805)]
    assert result["status"] == "success"
    assert result["updated"] == 4
    assert result["processed_dates"] == [20260805, 20260806]


@pytest.mark.parametrize("kind", ["index", "hot"])
def test_range_backfill_continues_after_one_date_failure(kind) -> None:
    repository = _Repository()
    calls = []

    if kind == "index":
        def runner(trade_date, repository=None):
            calls.append(trade_date)
            if trade_date == 20260805:
                raise RuntimeError("broken index")
            return 1

        result = backfill_index_emotion(
            20260804, 20260806, repository=repository, runner=runner
        )
        expected_processed = [20260804, 20260806]
        expected_updated = 2
    else:
        def runner(trade_date, previous_date, repository=None):
            calls.append(trade_date)
            if trade_date == 20260805:
                raise RuntimeError("broken board")
            return 2

        result = backfill_hot_board_emotion(
            20260804, 20260806, repository=repository, runner=runner
        )
        expected_processed = [20260806]
        expected_updated = 2

    assert result["status"] == "failed"
    assert result["updated"] == expected_updated
    assert result["processed_dates"] == expected_processed
    assert result["failed_dates"] == [20260805]
    assert result["errors"][0]["trade_date"] == 20260805


@pytest.mark.parametrize(
    ("backfill", "expected_calls"),
    [
        (backfill_index_emotion, [(20260806,)]),
        (backfill_hot_board_emotion, [(20260806, 20260805)]),
    ],
)
def test_no_date_selects_latest_canonical_session(backfill, expected_calls) -> None:
    calls = []

    def runner(*args, repository=None):
        calls.append(args)
        return 1

    result = backfill(repository=_Repository(), runner=runner)

    assert calls == expected_calls
    assert result["processed_dates"] == [20260806]


@pytest.mark.parametrize("backfill", [backfill_index_emotion, backfill_hot_board_emotion])
def test_backfill_rejects_empty_trading_calendar(backfill) -> None:
    with pytest.raises(DataValidationError, match="trading dates"):
        backfill(repository=_Repository([]), runner=lambda *args, **kwargs: 1)


def test_one_sided_range_selects_one_date() -> None:
    calls = []

    backfill_index_emotion(
        start_date=20260805,
        repository=_Repository(),
        runner=lambda trade_date, repository=None: calls.append(trade_date) or 1,
    )

    assert calls == [20260805]
