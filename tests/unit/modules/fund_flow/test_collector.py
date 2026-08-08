import threading
import time
import datetime as dt
from types import SimpleNamespace

import pytest

from stock_lab.modules.fund_flow import collector
from stock_lab.modules.fund_flow.collector import save_snapshot
from stock_lab.modules.fund_flow.source import FundFlowSource


class Repository:
    def __init__(self):
        self.saved = None
        self.published = None

    def save_history(self, flow_type, trade_date, records):
        self.saved = (flow_type, trade_date, records)

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        self.published = (flow_type, trade_date, collected_at, record_count)


def test_collector_commits_mysql_before_redis_success_state():
    calls = []

    class MySQL:
        def save_snapshot(self, *args):
            calls.append("mysql")

    class Redis(Repository):
        def save_history(self, *args):
            calls.append("redis")
            super().save_history(*args)

    save_snapshot(Redis(), "industry", dt.date.today().strftime("%Y%m%d"), "10:00:00", [{"board_code": "A", "net_inflow_100m": 1}], MySQL())

    assert calls == ["mysql", "redis"]


def test_collector_does_not_write_or_publish_when_mysql_commit_fails():
    repository = Repository()

    class MySQL:
        def save_snapshot(self, *args):
            raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        save_snapshot(
            repository,
            "industry",
            "20260807",
            "10:00:00",
            [{"board_code": "A", "net_inflow_100m": 1}],
            MySQL(),
        )

    assert repository.saved is None
    assert repository.published is None


def test_collector_writes_and_publishes_english_v1_snapshot():
    repository = Repository()
    records = [{"时间": "10:00:00", "板块名称": "机器人", "资金净流入(亿)": 3}]
    save_snapshot(
        repository,
        "concept",
        "20260806",
        "10:00:00",
        records,
    )

    assert repository.saved == (
        "concept",
        "20260806",
        [{"time": "10:00:00", "board_name": "机器人", "net_inflow_100m": 3}],
    )
    assert repository.published == ("concept", "20260806", "10:00:00", 1)


def test_monitor_uses_injected_source_contract_and_logs_startup(monkeypatch):
    calls = []

    class Source:
        def collection_interval_seconds(self): return 30
        def initialize(self, stop_event=None): calls.append("initialize")
        def warm_history(self): calls.append("warm_history")

    class Logger:
        def info(self, message, interval): calls.append((message, interval))

    stop_event = threading.Event()
    stop_event.set()
    monkeypatch.setattr(collector, "logger", Logger())

    collector.run_fund_flow_monitor(stop_event, source=Source())

    assert calls == [
        ("Fund-flow scheduler started with a {} second interval", 30),
        "initialize",
    ]


def test_source_warms_latest_history_for_both_flow_types():
    calls = []

    class HistoryService:
        def dates(self, flow_type):
            return {"dates": ["20260805", "20260806"] if flow_type == "industry" else ["20260804"]}

        def history(self, flow_type, trade_date, top_n=None):
            calls.append((flow_type, trade_date, top_n))

    source = FundFlowSource(
        lambda *_args, **_kwargs: None,
        object(),
        settings=SimpleNamespace(fund_flow_interval_seconds=30, fund_flow_history_top_n=5),
        history_service=HistoryService(),
    )

    source.warm_history()

    assert calls == [
        ("industry", "20260806", 5),
        ("concept", "20260804", 5),
    ]


def test_monitor_stop_interrupts_long_wait_and_closes_page():
    stop_event = threading.Event()
    waiting = threading.Event()
    closed = []

    class Page:
        def close(self):
            closed.append(True)

    class Source:
        def collection_interval_seconds(self): return 3600
        def initialize(self, stop_event=None): self.page = Page()
        def warm_history(self): pass
        def wait_until_next_run(self, stop_event=None):
            waiting.set()
            stop_event.wait(timeout=3600)
        def close(self): self.page.close()

    source = Source()
    thread = threading.Thread(
        target=collector.run_fund_flow_monitor,
        args=(stop_event,),
        kwargs={"source": source},
    )
    thread.start()
    assert waiting.wait(timeout=1)
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert closed == [True]


def test_monitor_passes_stop_event_to_blocking_collection_and_worker_stops():
    from stock_lab.bootstrap.workers import WorkerManager

    stop_event = threading.Event()
    collecting = threading.Event()
    fallback_release = threading.Event()
    observed_stop_events = []
    closed = []

    class Source:
        def collection_interval_seconds(self): return 30
        def initialize(self, stop_event=None): pass
        def warm_history(self): pass
        def wait_until_next_run(self, stop_event=None): pass
        def is_collection_time(self, now): return True
        def collect_all(self, stop_event=None):
            observed_stop_events.append(stop_event)
            collecting.set()
            (stop_event or fallback_release).wait(timeout=3600)
        def close(self): closed.append(True)

    manager = WorkerManager()
    manager.register(
        "blocking-fund-flow",
        lambda: collector.run_fund_flow_monitor(stop_event, source=Source()),
        stop=stop_event.set,
    )

    manager.start_all()
    assert collecting.wait(timeout=1)
    manager.stop_all(join_timeout=1)

    worker = manager._workers["blocking-fund-flow"]
    was_alive = worker.thread.is_alive()
    fallback_release.set()
    worker.thread.join(timeout=1)
    assert worker.thread is not None
    assert observed_stop_events == [stop_event]
    assert not was_alive
    assert closed == [True]


def test_source_close_is_idempotent_and_tolerates_partial_cleanup_failures():
    calls = []

    class Listener:
        def stop(self):
            calls.append("listener")
            raise RuntimeError("listener close failed")

    class Page:
        listen = Listener()

        def close(self):
            calls.append("page")
            raise RuntimeError("page close failed")

    source = FundFlowSource(
        lambda *_args, **_kwargs: None,
        object(),
        settings=SimpleNamespace(fund_flow_interval_seconds=30, fund_flow_history_top_n=0),
        history_service=object(),
    )
    source.close()
    source.page = Page()
    source.close()
    source.close()

    assert calls == ["listener", "page"]


def test_cleanup_does_not_mask_primary_monitor_error():
    class Source:
        def collection_interval_seconds(self): return 30
        def initialize(self, stop_event=None): raise ValueError("primary failure")
        def close(self): raise RuntimeError("cleanup failure")

    with pytest.raises(ValueError, match="primary failure"):
        collector.run_fund_flow_monitor(threading.Event(), source=Source())


def test_collection_stops_between_listener_packets():
    stop_event = threading.Event()

    class Listen:
        def start(self, _targets): pass

        def steps(self, timeout=None):
            yield SimpleNamespace(response=SimpleNamespace(body={}), target="first")
            stop_event.set()
            yield SimpleNamespace(response=SimpleNamespace(body={}), target="second")

    page = SimpleNamespace(listen=Listen(), get=lambda *_args, **_kwargs: None)
    source = FundFlowSource(
        lambda *_args, **_kwargs: page,
        object(),
        settings=SimpleNamespace(
            fund_flow_interval_seconds=30,
            fund_flow_history_top_n=0,
            concept_exclusions=(),
        ),
        history_service=object(),
    )
    source.page = page

    assert source.collect("industry", stop_event=stop_event) == []


def test_fund_flow_factory_binds_composed_settings_to_page_factory(monkeypatch):
    settings = SimpleNamespace(
        fund_flow_interval_seconds=31,
        fund_flow_history_top_n=2,
    )
    monkeypatch.setattr(
        "stock_lab.infrastructure.cache.redis_client.create_redis_client",
        lambda received: object(),
    )
    monkeypatch.setattr(
        "stock_lab.config.get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("global settings used")),
    )

    source = collector.create_fund_flow_source(settings=settings)

    assert source.settings is settings
    assert source.page_factory.keywords["settings"] is settings


def test_listener_wait_stops_within_worker_join_budget():
    stop_event = threading.Event()
    waiting = threading.Event()
    release = threading.Event()
    timeouts = []
    errors = []

    class Listen:
        def start(self, _targets): pass

        def steps(self, timeout=None):
            timeouts.append(timeout)
            waiting.set()
            release.wait(timeout=timeout)
            return iter(())

    page = SimpleNamespace(
        listen=Listen(),
        get=lambda *_args, **_kwargs: None,
    )
    source = FundFlowSource(
        lambda *_args, **_kwargs: page,
        object(),
        settings=SimpleNamespace(
            fund_flow_interval_seconds=30,
            fund_flow_history_top_n=0,
            concept_exclusions=(),
        ),
        history_service=object(),
    )
    source.page = page

    def collect():
        try:
            source.collect("industry", stop_event=stop_event)
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=collect)
    thread.start()
    assert waiting.wait(timeout=1)
    started = time.perf_counter()
    stop_event.set()
    thread.join(timeout=0.9)
    elapsed = time.perf_counter() - started
    was_alive = thread.is_alive()
    release.set()
    thread.join(timeout=1)

    assert not was_alive
    assert elapsed < 1
    assert timeouts and max(timeouts) < 0.9
    assert errors == []


def test_navigation_failure_closes_owned_page_once_without_masking_error():
    failure = ValueError("navigation failed")
    closed = []

    class Page:
        listen = SimpleNamespace(stop=lambda: None)

        def get(self, *_args, **_kwargs):
            raise failure

        def close(self):
            closed.append(True)

    page = Page()

    def page_factory(_name, url=None, **_kwargs):
        if url is not None:
            page.get(url)
        return page

    source = FundFlowSource(
        page_factory,
        object(),
        settings=SimpleNamespace(fund_flow_interval_seconds=30, fund_flow_history_top_n=0),
        history_service=object(),
    )

    with pytest.raises(ValueError) as raised:
        source.initialize()
    source.close()

    assert raised.value is failure
    assert closed == [True]
    assert source.page is None
