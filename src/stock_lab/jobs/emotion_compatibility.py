import argparse
import json

from stock_lab.modules.emotion.jobs import (
    backfill_hot_board_emotion,
    backfill_index_emotion,
)


def _run_cli(argv, backfill, description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--start-date", type=int)
    parser.add_argument("--end-date", type=int)
    args = parser.parse_args(argv)
    result = backfill(args.start_date, args.end_date)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


def run_index_cli(argv=None, *, backfill=backfill_index_emotion):
    return _run_cli(argv, backfill, "Backfill canonical index emotion")


def run_hot_board_cli(argv=None, *, backfill=backfill_hot_board_emotion):
    return _run_cli(argv, backfill, "Backfill canonical hot-board emotion")
