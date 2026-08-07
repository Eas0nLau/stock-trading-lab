from datetime import datetime
from typing import Protocol

from stock_lab.modules.fund_flow.contracts import normalize_net_inflow_100m, translate_legacy_fund_flow

LEGACY_REDIS_MIGRATION_KEY = "fund_flow:v1:legacy-normalized"


class FundFlowDailySource(Protocol):
    def fetch(self, flow_type: str, trade_date: int) -> list[dict]:
        ...


class ConfiguredFundFlowDailySource:
    """Explicit production boundary; deployments must provide the historical adapter."""

    def __init__(self, fetcher=None):
        self.fetcher = fetcher

    def fetch(self, flow_type, trade_date):
        if self.fetcher is None:
            raise RuntimeError("No fund-flow historical source is configured")
        return self.fetcher(flow_type, trade_date)


def backfill_fund_flow(start_date, end_date, source, mysql_repository, redis_repository, trading_dates):
    dates = trading_dates(start_date, end_date)
    result = {"saved": [], "skipped": [], "failed": []}
    for trade_date in sorted(dates, reverse=True):
        for flow_type in ("industry", "concept"):
            if mysql_repository.has_snapshot(flow_type, trade_date):
                result["skipped"].append({"flow_type": flow_type, "trade_date": trade_date})
                continue
            try:
                records = source.fetch(flow_type, trade_date)
                if not records:
                    raise ValueError("source returned no records")
                records = translate_legacy_fund_flow(records)
                records = [
                    {
                        **record,
                        "net_inflow_100m": float(normalize_net_inflow_100m(record.get("net_inflow_100m"), record.get("source_unit", "100m"))),
                    }
                    for record in records
                ]
                collected_at = records[0].get("collected_at") or records[0].get("time") or datetime.min.strftime("%H:%M:%S")
                mysql_repository.save_snapshot(flow_type, trade_date, collected_at, records)
                redis_repository.save_history(flow_type, trade_date, [records])
                result["saved"].append({"flow_type": flow_type, "trade_date": trade_date})
            except Exception as error:
                result["failed"].append({"flow_type": flow_type, "trade_date": trade_date, "error": str(error)})
    return result


def migrate_legacy_redis(redis_repository, mysql_repository, flow_types=("industry", "concept")):
    """Normalize existing V1 Redis snapshots into MySQL and rebuild their cache."""
    if redis_repository.redis.get(LEGACY_REDIS_MIGRATION_KEY):
        return {"saved": [], "failed": [], "skipped": True}
    result = {"saved": [], "failed": []}
    for flow_type in flow_types:
        for trade_date in redis_repository.dates(flow_type):
            try:
                history = translate_legacy_fund_flow(redis_repository.history(flow_type, trade_date))
                if not isinstance(history, list):
                    raise ValueError("legacy history is not a snapshot list")
                canonical_history = []
                for snapshot in history:
                    canonical = []
                    for record in snapshot:
                        item = dict(record)
                        item["net_inflow_100m"] = float(normalize_net_inflow_100m(item.get("net_inflow_100m"), "wan"))
                        canonical.append(item)
                    if canonical:
                        mysql_repository.save_snapshot(flow_type, trade_date, canonical[0].get("time", "00:00:00"), canonical)
                        canonical_history.append(canonical)
                redis_repository.replace_history(flow_type, trade_date, canonical_history)
                result["saved"].append({"flow_type": flow_type, "trade_date": trade_date})
            except Exception as error:
                result["failed"].append({"flow_type": flow_type, "trade_date": trade_date, "error": str(error)})
    if not result["failed"]:
        redis_repository.redis.set(LEGACY_REDIS_MIGRATION_KEY, "1")
    return result
