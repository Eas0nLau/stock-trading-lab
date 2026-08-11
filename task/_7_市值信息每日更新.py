import argparse
import json

from stock_lab.jobs.market_cap_backfill import update_market_cap as _update_market_cap


def 更新(start_date=None, end_date=None, only_missing=True):
    return _update_market_cap(start_date, end_date, force=not only_missing)


def 主函数(start_date=None, end_date=None, force=False):
    return _update_market_cap(start_date, end_date, force=force)


update = 更新
main = 主函数


def _cli(argv=None):
    parser = argparse.ArgumentParser(description="Backfill daily market-cap fields")
    parser.add_argument("--start-date", type=int)
    parser.add_argument("--end-date", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    result = 主函数(args.start_date, args.end_date, force=args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
