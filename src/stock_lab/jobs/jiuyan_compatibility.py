import argparse
import json

from stock_lab.modules.market_data.jiuyan import collect_jiuyan_actions
from stock_lab.modules.market_data.jiuyan_exports import (
    export_jiuyan_actions,
    front_rank_summary,
)


def run_cli(
    argv=None,
    *,
    collector=collect_jiuyan_actions,
    exporter=export_jiuyan_actions,
    front_rank=front_rank_summary,
):
    parser = argparse.ArgumentParser(description="Collect or query Jiuyan actions")
    parser.add_argument("--date", type=int, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--export-only", action="store_true")
    modes.add_argument("--front-rank", action="store_true")
    args = parser.parse_args(argv)
    if args.export_only:
        result = [str(path) for path in exporter(args.date)]
    elif args.front_rank:
        result = front_rank(args.date)
    else:
        result = collector(args.date)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0
