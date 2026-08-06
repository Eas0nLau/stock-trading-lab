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
