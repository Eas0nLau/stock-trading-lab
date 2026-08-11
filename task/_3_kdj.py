"""Compatibility wrapper for canonical KDJ jobs."""

from stock_lab.jobs.kdj_compatibility import (
    run_cli as _run_cli,
    save_code_kdj as _save_code_kdj,
    save_daily_kdj as _save_daily_kdj,
)
from stock_lab.modules.market_data.indicators import calculate_ths_kdj


def save_code_kdj(ts_code, start_date=None, end_date=None, period=9):
    return _save_code_kdj(
        ts_code,
        start_date=start_date,
        end_date=end_date,
        period=period,
    )


def save_daily_kdj(start_date=None, end_date=None, period=9):
    return _save_daily_kdj(
        start_date=start_date,
        end_date=end_date,
        period=period,
    )


def _cli(argv=None):
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(_cli())
