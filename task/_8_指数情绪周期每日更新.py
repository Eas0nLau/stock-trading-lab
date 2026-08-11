"""Compatibility wrapper for canonical index-emotion backfills."""

from stock_lab.jobs.emotion_compatibility import run_index_cli as _run_index_cli
from stock_lab.modules.emotion.jobs import (
    backfill_index_emotion as _backfill_index_emotion,
)


def 更新(start_date=None, end_date=None):
    return _backfill_index_emotion(start_date, end_date)


def update(start_date=None, end_date=None):
    return _backfill_index_emotion(start_date, end_date)


def main(start_date=None, end_date=None):
    return _backfill_index_emotion(start_date, end_date)


def _cli(argv=None):
    return _run_index_cli(argv)


if __name__ == "__main__":
    raise SystemExit(_cli())
