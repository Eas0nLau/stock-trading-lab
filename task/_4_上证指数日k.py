import argparse

from stock_lab.modules.market_data.collectors import update_index_daily


def update(start_date, end_date):
    return update_index_daily(start_date, end_date)


main = update


def _cli(argv=None):
    parser = argparse.ArgumentParser(description="Update Shanghai index daily data")
    parser.add_argument("--start-date", type=int, required=True)
    parser.add_argument("--end-date", type=int, required=True)
    args = parser.parse_args(argv)
    print(update(args.start_date, args.end_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
