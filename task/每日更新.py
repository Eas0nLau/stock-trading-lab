"""Compatibility entry point for the official daily-update job."""

import argparse

from stock_lab.jobs.daily_update import backfill_daily_updates, run_daily_update


def tasks(date, **kwargs):
    return run_daily_update(date, **kwargs)


def backfill(days=60, **kwargs):
    return backfill_daily_updates(days, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Run the daily market-data update job")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", type=int, help="Update one trading date as YYYYMMDD")
    group.add_argument("--backfill", type=int, help="Backfill the latest N trading dates")
    args = parser.parse_args()
    result = tasks(args.date) if args.date else backfill(args.backfill)
    print(result)
    return 0 if result.get("status") in {"success", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
