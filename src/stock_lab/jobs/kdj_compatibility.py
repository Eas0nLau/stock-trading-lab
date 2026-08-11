import argparse
import json

from stock_lab.jobs.kdj_indicators import (
    update_kdj_indicators,
    update_latest_kdj_indicators,
)


def run_kdj_update(
    start_date=None,
    end_date=None,
    *,
    stock_codes=None,
    period=9,
):
    if start_date is None and end_date is None:
        return update_latest_kdj_indicators(
            stock_codes=stock_codes,
            period=period,
        )
    start_date = start_date if start_date is not None else end_date
    end_date = end_date if end_date is not None else start_date
    return update_kdj_indicators(
        start_date,
        end_date,
        stock_codes=stock_codes,
        period=period,
    )


def save_code_kdj(ts_code, start_date=None, end_date=None, period=9):
    return run_kdj_update(
        start_date,
        end_date,
        stock_codes=[ts_code],
        period=period,
    )


def save_daily_kdj(start_date=None, end_date=None, period=9):
    return run_kdj_update(start_date, end_date, period=period)


def run_cli(argv=None, runner=run_kdj_update):
    parser = argparse.ArgumentParser(description="Recalculate canonical KDJ indicators")
    parser.add_argument("--start-date", type=int)
    parser.add_argument("--end-date", type=int)
    parser.add_argument("--stock-code", action="append", dest="stock_codes")
    parser.add_argument("--period", type=int, default=9)
    args = parser.parse_args(argv)
    updated = runner(
        args.start_date,
        args.end_date,
        stock_codes=args.stock_codes,
        period=args.period,
    )
    print(json.dumps({"updated": updated}, ensure_ascii=False))
    return 0
