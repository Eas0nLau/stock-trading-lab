import datetime as dt
import threading

from stock_lab.bootstrap.application import create_app  # noqa: F401 - initializes bootstrap imports before direct job import
from stock_lab.jobs import realtime_monitor


def test_strategy_worker_delegates_to_official_collector(monkeypatch):
    calls = []
    stop_event = threading.Event()
    collector = object()
    adapter = object()

    def fake_runner(received_stop_event, *, collector=None, adapter=None):
        calls.append((received_stop_event, collector, adapter))

    monkeypatch.setattr("stock_lab.modules.strategy_pick.collector.run_strategy_pick_monitor", fake_runner)

    realtime_monitor.run_strategy_pick_monitor(stop_event, collector=collector, adapter=adapter)

    assert calls == [(stop_event, collector, adapter)]


def test_default_strategy_worker_owns_and_obeys_stop_event(monkeypatch):
    started = threading.Event()
    observed = []

    def fake_strategy_worker(stop_event, **kwargs):
        observed.append(stop_event)
        started.set()
        stop_event.wait(timeout=2)

    monkeypatch.setattr(realtime_monitor, "run_strategy_pick_monitor", fake_strategy_worker)
    manager = realtime_monitor.create_default_worker_manager()

    manager.start_all()
    assert started.wait(timeout=1)
    manager.stop_all(join_timeout=1)

    assert len(observed) == 1
    assert observed[0].is_set()
    strategy_worker = manager._workers["strategy-pick-monitor"]
    assert strategy_worker.thread is not None
    assert not strategy_worker.thread.is_alive()


class CapturingTimer:
    scheduled = []

    def __init__(self, interval, target, args=None, kwargs=None):
        self.interval = interval
        self.target = target
        self.args = args or []
        self.kwargs = kwargs or {}

    def start(self):
        self.scheduled.append((self.interval, self.target, self.args, self.kwargs))


def test_scheduler_dispatches_official_jobs_after_weekday_thresholds(monkeypatch):
    CapturingTimer.scheduled = []
    daily_runner = lambda _date: None
    premarket_runner = lambda _date, **_kwargs: None
    source = object()
    monkeypatch.setattr(realtime_monitor, "run_daily_update", daily_runner)
    monkeypatch.setattr(realtime_monitor, "run_premarket_summary", premarket_runner)

    realtime_monitor.schedule_optional_jobs(
        dt.datetime(2026, 8, 7, 17, 35),
        premarket_source=source,
        timer_factory=CapturingTimer,
    )

    assert CapturingTimer.scheduled == [
        (0, daily_runner, ["20260807"], {}),
        (0, premarket_runner, ["20260807"], {"source": source}),
    ]


def test_scheduler_does_not_dispatch_before_threshold_or_on_weekend(monkeypatch):
    CapturingTimer.scheduled = []
    monkeypatch.setattr(realtime_monitor, "run_daily_update", lambda _date: None)
    monkeypatch.setattr(realtime_monitor, "run_premarket_summary", lambda _date, **_kwargs: None)

    realtime_monitor.schedule_optional_jobs(
        dt.datetime(2026, 8, 7, 7, 59),
        premarket_source=object(),
        timer_factory=CapturingTimer,
    )
    realtime_monitor.schedule_optional_jobs(
        dt.datetime(2026, 8, 8, 18, 0),
        premarket_source=object(),
        timer_factory=CapturingTimer,
    )

    assert CapturingTimer.scheduled == []


def test_scheduler_leaves_unconfigured_premarket_job_disabled(monkeypatch):
    CapturingTimer.scheduled = []
    monkeypatch.setattr(realtime_monitor, "run_daily_update", lambda _date: None)

    realtime_monitor.schedule_optional_jobs(
        dt.datetime(2026, 8, 7, 8, 0),
        premarket_source=None,
        timer_factory=CapturingTimer,
    )

    assert CapturingTimer.scheduled == []
