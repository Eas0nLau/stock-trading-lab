import datetime
import threading

from loguru import logger

from .contracts import translate_legacy_fund_flow


_default_source = None


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
    settings=None,
) -> None:
    schedule_optional_jobs = schedule_optional_jobs or (lambda now: None)
    if source is None:
        source = create_fund_flow_source(settings=settings)
    logger.info(
        "Fund-flow scheduler started with a {} second interval",
        source.collection_interval_seconds(),
    )
    try:
        source.initialize()
        source.warm_history()
        while not stop_event.is_set():
            source.wait_until_next_run(stop_event=stop_event)
            if stop_event.is_set():
                break
            now = datetime.datetime.now()
            if source.is_collection_time(now):
                source.collect_all()
            schedule_optional_jobs(now)
    finally:
        close = getattr(source, "close", None)
        if callable(close):
            close()


def create_fund_flow_source(*, settings=None):
    from stock_lab.infrastructure.browser.client import create_page
    from stock_lab.infrastructure.cache.redis_client import create_redis_client
    from stock_lab.config import get_settings

    from .repository import FundFlowRepository
    from .source import FundFlowSource

    settings = settings or get_settings()
    return FundFlowSource(
        create_page,
        FundFlowRepository(create_redis_client(settings)),
        settings=settings,
    )


def get_fund_flow_source():
    global _default_source
    if _default_source is None:
        _default_source = create_fund_flow_source()
    return _default_source


def collection_interval_seconds():
    return get_fund_flow_source().collection_interval_seconds()


def wait_until_next_run(interval_seconds=None):
    return get_fund_flow_source().wait_until_next_run(interval_seconds)


def is_collection_time(now=None):
    source = get_fund_flow_source()
    return source.is_collection_time(now or source.clock())


def initialize_source():
    return get_fund_flow_source().initialize()


def warm_history():
    return get_fund_flow_source().warm_history()


def collect_flow(flow_type):
    return get_fund_flow_source().collect(flow_type)


def collect_all_flows():
    return get_fund_flow_source().collect_all()


def start_monitor(stop_event):
    return run_fund_flow_monitor(stop_event, source=get_fund_flow_source())
