import datetime
import threading

from loguru import logger

from .contracts import translate_legacy_fund_flow


def save_snapshot(
    repository,
    flow_type,
    trade_date,
    collected_at,
    records,
) -> None:
    repository.save_history(flow_type, trade_date, translate_legacy_fund_flow(records))
    repository.publish_snapshot(flow_type, trade_date, collected_at, len(records))


def run_fund_flow_monitor(
    stop_event: threading.Event,
    schedule_optional_jobs=None,
    source=None,
) -> None:
    schedule_optional_jobs = schedule_optional_jobs or (lambda now: None)
    if source is None:
        source = create_fund_flow_source()
    logger.info(
        "Fund-flow scheduler started with a {} second interval",
        source.collection_interval_seconds(),
    )
    source.initialize()
    source.warm_history()
    while not stop_event.is_set():
        source.wait_until_next_run()
        if stop_event.is_set():
            break
        now = datetime.datetime.now()
        if source.is_collection_time(now):
            source.collect_all()
        schedule_optional_jobs(now)


def create_fund_flow_source():
    from stock_lab.infrastructure.browser.client import create_page
    from stock_lab.infrastructure.cache.redis_client import create_redis_client
    from stock_lab.config import get_settings

    from .repository import FundFlowRepository
    from .source import FundFlowSource

    settings = get_settings()
    return FundFlowSource(
        create_page,
        FundFlowRepository(create_redis_client(settings)),
        settings=settings,
    )
