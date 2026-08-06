import threading

from stock_lab.bootstrap.application import create_app
from stock_lab.bootstrap.workers import WorkerManager
from stock_lab.jobs.realtime_monitor import create_default_worker_manager


class RouteRegistrar:
    def __init__(self):
        self.calls = 0

    def __call__(self, app):
        self.calls += 1

        @app.get("/api/test")
        def test_route():
            return {"status": "ok"}


def test_create_app_registers_routes_once():
    registrar = RouteRegistrar()

    app = create_app(
        worker_manager=WorkerManager(),
        route_registrar=registrar,
    )

    paths = [route.path for route in app.routes]
    assert registrar.calls == 1
    assert paths.count("/api/test") == 1


def test_worker_manager_does_not_start_live_worker_twice():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def target():
        calls.append("started")
        started.set()
        release.wait(timeout=2)

    manager = WorkerManager()
    manager.register("sample", target)

    manager.start_all()
    assert started.wait(timeout=1)
    manager.start_all()
    release.set()
    manager.stop_all()

    assert calls == ["started"]


def test_worker_manager_runs_stop_callback():
    stopped = []
    manager = WorkerManager()
    manager.register("sample", lambda: None, stop=lambda: stopped.append("stopped"))

    manager.start_all()
    manager.stop_all()

    assert stopped == ["stopped"]


def test_default_worker_manager_declares_monitoring_workers():
    manager = create_default_worker_manager()

    assert manager.names == ("fund-flow-monitor", "strategy-pick-monitor")


def test_legacy_app_entrypoint_builds_application_without_starting_workers():
    import app as legacy_app

    paths = [route.path for route in legacy_app.app.routes]
    assert legacy_app.app.title == "stock_trading_lab_api"
    assert "/api/emotion/current" in paths
    assert not any(
        thread.name in {"fund-flow-monitor", "strategy-pick-monitor"}
        for thread in threading.enumerate()
    )
