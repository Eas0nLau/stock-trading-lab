import argparse
import json

import pandas as pd

from stock_lab.infrastructure.market_data import KplDdeSource
from stock_lab.jobs.dde_backfill import update_dde as _update_dde


def 读取历史日K_DDE(
    stock_code,
    count=100,
    start_date=None,
    end_date=None,
    timeout=20,
    retries=3,
):
    rows = KplDdeSource().fetch_daily_dde(
        stock_code,
        count=count,
        start_date=start_date,
        end_date=end_date,
        timeout=timeout,
        retries=retries,
    )
    return pd.DataFrame(rows, columns=["stock_code", "trade_date", "dde"])


def 更新(
    start_date=None,
    end_date=None,
    only_missing=True,
    max_workers=4,
    timeout=20,
    retries=3,
):
    return _update_dde(
        start_date,
        end_date,
        force=not only_missing,
        max_workers=max_workers,
        timeout=timeout,
        retries=retries,
    )


def 主函数(
    start_date=None,
    end_date=None,
    force=False,
    max_workers=4,
    timeout=20,
    retries=3,
):
    return _update_dde(
        start_date,
        end_date,
        force=force,
        max_workers=max_workers,
        timeout=timeout,
        retries=retries,
    )


fetch_daily_dde = 读取历史日K_DDE
update = 更新
main = 主函数


def _cli(argv=None):
    parser = argparse.ArgumentParser(description="Backfill KPL daily DDE")
    parser.add_argument("--start-date", type=int)
    parser.add_argument("--end-date", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)
    result = 主函数(
        args.start_date,
        args.end_date,
        force=args.force,
        max_workers=args.max_workers,
        timeout=args.timeout,
        retries=args.retries,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
