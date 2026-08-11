"""Compatibility wrapper for canonical hot-board emotion backfills."""

from stock_lab.jobs.emotion_compatibility import run_hot_board_cli as _run_hot_board_cli
from stock_lab.modules.emotion.jobs import (
    backfill_hot_board_emotion as _backfill_hot_board_emotion,
)


def 更新(start_date=None, end_date=None):
    return _backfill_hot_board_emotion(start_date, end_date)


def update(start_date=None, end_date=None):
    return _backfill_hot_board_emotion(start_date, end_date)


def main(start_date=None, end_date=None):
    return _backfill_hot_board_emotion(start_date, end_date)


def _cli(argv=None):
    return _run_hot_board_cli(argv)


if __name__ == "__main__":
    raise SystemExit(_cli())
