import datetime
import threading

from .contracts import translate_legacy_fund_flow


def save_legacy_snapshot(repository, flow_type, trade_date, collected_at, records) -> None:
    repository.save_history(flow_type, trade_date, translate_legacy_fund_flow(records))
    repository.publish_snapshot(flow_type, trade_date, collected_at, len(records))


def run_fund_flow_monitor(stop_event: threading.Event, schedule_optional_jobs=None) -> None:
    from 实时监控 import 资金流向

    schedule_optional_jobs = schedule_optional_jobs or (lambda now: None)
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
