import argparse
import json

from stock_lab.modules.market_data.collectors import (
    update_daily_quotes,
    update_securities,
)


def main(start_date, end_date, force=False):
    return {
        "securities": update_securities(),
        "daily_quotes": update_daily_quotes(
            start_date,
            end_date,
            force=force,
        ),
    }


def _cli(argv=None):
    parser = argparse.ArgumentParser(description="Update securities and daily quotes")
    parser.add_argument("--start-date", type=int, required=True)
    parser.add_argument("--end-date", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    result = main(args.start_date, args.end_date, force=args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
