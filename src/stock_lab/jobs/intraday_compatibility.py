import argparse
import json

from stock_lab.jobs.intraday_bars_5m import (
    backfill_intraday_bars_5m,
    fetch_intraday_bars_5m,
)
from stock_lab.modules.market_data.helpers import normalize_ts_code


def _legacy_number(value):
    return format(value, "g")


def _legacy_code(value):
    ts_code = normalize_ts_code(value)
    symbol, separator, exchange = ts_code.partition(".")
    if not separator:
        if symbol.startswith(("4", "8")):
            exchange = "BJ"
        else:
            exchange = "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
    return f"{exchange.lower()}.{symbol}"


def get_data(
    start_date,
    end_date,
    code=None,
    source=None,
    *,
    stock=None,
    fetcher=fetch_intraday_bars_5m,
):
    if code is not None and stock is not None:
        raise TypeError("Pass either code or stock, not both")
    code = code if code is not None else stock
    if code is None:
        raise TypeError("Pass either code or stock")
    rows = fetcher(start_date, end_date, code, source=source)
    return [[
        _legacy_number(row["open_price"]),
        _legacy_number(row["close_price"]),
        f"{str(row['trade_date'])[:4]}-{str(row['trade_date'])[4:6]}-{str(row['trade_date'])[6:]}",
        str(row["trade_time"]),
        _legacy_code(code),
        _legacy_number(row["high_price"]),
        _legacy_number(row["low_price"]),
        _legacy_number(row["volume"]),
        _legacy_number(row["turnover"]),
        str(row["adjustment_flag"]),
    ] for row in rows]


def process_stock_batch(args):
    stock_codes, start_date, end_date = args
    return backfill_intraday_bars_5m(
        start_date,
        end_date,
        stock_codes=stock_codes,
        max_workers=1,
    )


def main(start_date, end_date, stock_codes=None, max_workers=4):
    return backfill_intraday_bars_5m(
        start_date,
        end_date,
        stock_codes=stock_codes,
        max_workers=max_workers,
    )


def run_cli(argv=None, main_fn=main):
    parser = argparse.ArgumentParser(description="Backfill BaoStock five-minute bars")
    parser.add_argument("--start-date", type=int, required=True)
    parser.add_argument("--end-date", type=int, required=True)
    parser.add_argument("--stock-code", action="append", dest="stock_codes")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)
    result = main_fn(
        args.start_date,
        args.end_date,
        stock_codes=args.stock_codes,
        max_workers=args.max_workers,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1
