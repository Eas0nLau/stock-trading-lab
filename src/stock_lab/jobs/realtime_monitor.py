import datetime
import threading
from threading import Timer

from stock_lab.bootstrap.workers import WorkerManager
from stock_lab.jobs.daily_update import run_daily_update
from stock_lab.jobs.premarket_summary import run_premarket_summary


def create_default_worker_manager(*, premarket_source=None) -> WorkerManager:
    manager = WorkerManager()
    fund_flow_stop = threading.Event()
    manager.register(
        "fund-flow-monitor",
        lambda: run_fund_flow_monitor(fund_flow_stop, premarket_source=premarket_source),
        stop=fund_flow_stop.set,
    )
    strategy_pick_stop = threading.Event()
    manager.register("strategy-pick-monitor", lambda: run_strategy_pick_monitor(strategy_pick_stop), stop=strategy_pick_stop.set)
    return manager


def run_strategy_pick_monitor(stop_event=None, *, collector=None, adapter=None) -> None:
    from stock_lab.modules.strategy_pick.collector import run_strategy_pick_monitor as run_collector
    run_collector(stop_event, collector=collector, adapter=adapter)


def run_fund_flow_monitor(stop_event: threading.Event, *, premarket_source=None) -> None:
    from stock_lab.modules.fund_flow.collector import run_fund_flow_monitor as run_collector
    run_collector(
        stop_event,
        lambda now: schedule_optional_jobs(now, premarket_source=premarket_source),
    )


def schedule_optional_jobs(
    now: datetime.datetime,
    *,
    premarket_source=None,
    timer_factory=Timer,
) -> None:
    if now.weekday() >= 5:
        return
    trade_date = now.strftime("%Y%m%d")
    if now.time() >= datetime.time(17, 35):
        timer_factory(0, run_daily_update, args=[trade_date]).start()
    if premarket_source is not None and now.time() >= datetime.time(8, 0):
        timer_factory(
            0,
            run_premarket_summary,
            args=[trade_date],
            kwargs={"source": premarket_source},
        ).start()
