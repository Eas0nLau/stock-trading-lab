import datetime
import threading
from threading import Timer

from stock_lab.bootstrap.workers import WorkerManager
from stock_lab.jobs.daily_update import run_daily_update
from stock_lab.jobs.premarket_summary import run_premarket_summary


_scheduled_jobs = set()
_scheduled_jobs_lock = threading.Lock()


def create_default_worker_manager(*, settings=None, premarket_source=None) -> WorkerManager:
    manager = WorkerManager()
    fund_flow_stop = threading.Event()
    manager.register(
        "fund-flow-monitor",
        lambda: run_fund_flow_monitor(fund_flow_stop, settings=settings, premarket_source=premarket_source),
        stop=fund_flow_stop.set,
    )
    strategy_pick_stop = threading.Event()
    manager.register("strategy-pick-monitor", lambda: run_strategy_pick_monitor(strategy_pick_stop, settings=settings), stop=strategy_pick_stop.set)
    return manager


def run_strategy_pick_monitor(stop_event=None, *, settings=None, collector=None, adapter=None) -> None:
    from stock_lab.modules.strategy_pick.collector import run_strategy_pick_monitor as run_collector
    run_collector(stop_event, settings=settings, collector=collector, adapter=adapter)


def run_fund_flow_monitor(stop_event: threading.Event, *, settings=None, premarket_source=None) -> None:
    from stock_lab.modules.fund_flow.collector import run_fund_flow_monitor as run_collector
    run_collector(
        stop_event,
        lambda now: schedule_optional_jobs(now, premarket_source=premarket_source),
        settings=settings,
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
    if now.time() >= datetime.time(17, 35) and _claim_job("daily-update", trade_date):
        timer_factory(0, run_daily_update, args=[trade_date]).start()
    if premarket_source is not None and now.time() >= datetime.time(8, 0) and _claim_job("premarket-summary", trade_date):
        timer_factory(
            0,
            run_premarket_summary,
            args=[trade_date],
            kwargs={"source": premarket_source},
        ).start()


def _claim_job(job_id, trade_date):
    claim = (job_id, trade_date)
    with _scheduled_jobs_lock:
        _scheduled_jobs.intersection_update({
            item for item in _scheduled_jobs if item[1] == trade_date
        })
        if claim in _scheduled_jobs:
            return False
        _scheduled_jobs.add(claim)
        return True
