import argparse
import json

from stock_lab.config import Settings
from stock_lab.jobs.fund_flow_backfill import (
    AkShareFundFlowSource,
    backfill_fund_flow as _official_backfill_fund_flow,
    ConfiguredFundFlowDailySource,
    EastMoneyFundFlowSource,
    FLOW_TYPES,
    FundFlowSourceError,
    FundFlowDailySource,
    collect_fund_flow_records,
    normalize_history_rows,
    parse_daykline_response,
)
from stock_lab.jobs.fund_flow_backfill import _default_repositories, _default_writer as _official_writer


def _default_writer(settings=None, connection_factory=None, redis_factory=None):
    mysql_repository, redis_repository = _default_repositories(
        settings=settings or Settings.from_env(),
        connection_factory=connection_factory,
        redis_factory=redis_factory,
    )
    return _official_writer(mysql_repository, redis_repository)


def backfill_fund_flow(*args, **kwargs):
    return _official_backfill_fund_flow(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Backfill board fund-flow history")
    parser.add_argument("--days", type=int, default=365, help="calendar-day lookback (default: 365)")
    parser.add_argument("--retries", type=int, default=2, help="retries per source request")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="seconds between retries")
    parser.add_argument("--rate-delay", type=float, default=0.2, help="seconds between source requests")
    args = parser.parse_args(argv)
    result = _official_backfill_fund_flow(
        days=args.days,
        retries=max(args.retries, 0),
        retry_delay=max(args.retry_delay, 0),
        rate_delay=max(args.rate_delay, 0),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
