import datetime
import threading
from threading import Timer

from loguru import logger

from stock_lab.bootstrap.workers import WorkerManager


def create_default_worker_manager() -> WorkerManager:
    manager = WorkerManager()
    fund_flow_stop = threading.Event()
    manager.register(
        "fund-flow-monitor",
        lambda: run_fund_flow_monitor(fund_flow_stop),
        stop=fund_flow_stop.set,
    )
    manager.register("strategy-pick-monitor", run_strategy_pick_monitor)
    return manager


def run_strategy_pick_monitor() -> None:
    from 实时监控 import 策略选股

    策略选股.start_monitor()


def run_fund_flow_monitor(stop_event: threading.Event) -> None:
    from 实时监控 import 资金流向

    logger.info(
        "Fund-flow scheduler started with a {} second interval",
        资金流向.获取资金流向采集间隔秒(),
    )
    资金流向.init_driver()
    资金流向.预热最新资金流向历史()

    while not stop_event.is_set():
        资金流向.等待到下次对齐执行()
        if stop_event.is_set():
            break
        now = datetime.datetime.now()
        if 资金流向.当前是资金流向采集时间(now):
            资金流向.采集全部资金流向()
        schedule_optional_jobs(now)


def schedule_optional_jobs(now: datetime.datetime) -> None:
    from utils import db

    daily_update, premarket = load_optional_tasks()
    if daily_update is not None and now.weekday() < 5 and now.time() >= datetime.time(17, 35):
        if not db.redis_con_localhost.exists(f"每日更新.py:{now:%Y%m%d}") and not db.redis_con_localhost.exists(
            "run_check:每日更新.py"
        ):
            Timer(0, daily_update.tasks, args=[now.strftime("%Y%m%d")]).start()

    if premarket is not None and now.weekday() < 5 and now.time() >= datetime.time(8, 0):
        if not db.redis_con_localhost.exists(f"盘前纪要.py:{now:%Y%m%d}") and not db.redis_con_localhost.exists(
            "run_check:盘前纪要.py"
        ):
            Timer(0, premarket.韭研公社盘前纪要采集, args=[now.strftime("%Y%m%d")]).start()


def load_optional_tasks():
    try:
        from task import 每日更新 as daily_update
    except ModuleNotFoundError as error:
        if error.name != "task":
            raise
        daily_update = None

    try:
        from task import 盘前纪要 as premarket
    except ModuleNotFoundError as error:
        if error.name not in {"task", "task.盘前纪要"}:
            raise
        premarket = None
    except ImportError as error:
        if "cannot import name" not in str(error):
            raise
        premarket = None

    return daily_update, premarket


def clear_legacy_task_locks() -> None:
    from utils import db

    daily_update, premarket = load_optional_tasks()
    if daily_update is not None:
        db.redis_con_localhost.delete("run_check:每日更新.py")
    if premarket is not None:
        db.redis_con_localhost.delete("run_check:盘前纪要.py")
