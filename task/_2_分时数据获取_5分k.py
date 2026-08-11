"""Compatibility wrapper for canonical five-minute history jobs."""

from stock_lab.jobs.intraday_bars_5m import fetch_intraday_bars_5m
from stock_lab.jobs.intraday_compatibility import (
    get_data as _get_data,
    main as _main,
    process_stock_batch as _process_stock_batch,
    run_cli as _run_cli,
)


def get_data(start_date, end_date, code=None, source=None, *, stock=None):
    return _get_data(
        start_date,
        end_date,
        code,
        source,
        stock=stock,
        fetcher=fetch_intraday_bars_5m,
    )


def process_stock_batch(args):
    return _process_stock_batch(args)


def main(start_date, end_date, stock_codes=None, max_workers=4):
    return _main(
        start_date,
        end_date,
        stock_codes=stock_codes,
        max_workers=max_workers,
    )


def _cli(argv=None):
    return _run_cli(argv, main_fn=main)


if __name__ == "__main__":
    raise SystemExit(_cli())
