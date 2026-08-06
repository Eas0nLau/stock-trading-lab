import datetime
import threading

from loguru import logger

from .contracts import translate_legacy_fund_flow
from .legacy_adapter import LegacyFundFlowCollectorAdapter, LegacyFundFlowWriteAdapter


def save_legacy_snapshot(
    repository,
    flow_type,
    trade_date,
    collected_at,
    records,
    legacy_writer=None,
) -> None:
    repository.save_history(flow_type, trade_date, translate_legacy_fund_flow(records))
    if legacy_writer is None:
        legacy_writer = LegacyFundFlowWriteAdapter(repository.redis)
    legacy_writer.save_snapshot(flow_type, trade_date, collected_at, records)
    repository.publish_snapshot(flow_type, trade_date, collected_at, len(records))


def run_fund_flow_monitor(
    stop_event: threading.Event,
    schedule_optional_jobs=None,
    legacy_adapter=None,
) -> None:
    schedule_optional_jobs = schedule_optional_jobs or (lambda now: None)
    legacy_adapter = legacy_adapter or LegacyFundFlowCollectorAdapter()
    logger.info(
        "Fund-flow scheduler started with a {} second interval",
        legacy_adapter.collection_interval_seconds(),
    )
    legacy_adapter.initialize()
    legacy_adapter.warm_history()
    while not stop_event.is_set():
        legacy_adapter.wait_until_next_run()
        if stop_event.is_set():
            break
        now = datetime.datetime.now()
        if legacy_adapter.is_collection_time(now):
            legacy_adapter.collect_all()
        schedule_optional_jobs(now)
