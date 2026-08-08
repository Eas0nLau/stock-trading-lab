from stock_lab.modules.fund_flow.collector import (
    collect_all_flows,
    collect_flow,
    collection_interval_seconds,
    initialize_source,
    is_collection_time,
    start_monitor as _start_monitor,
    wait_until_next_run,
    warm_history,
)


def 获取资金流向采集间隔秒():
    return collection_interval_seconds()


def 等待到下次对齐执行(interval_seconds=None):
    return wait_until_next_run(interval_seconds)


def 当前是资金流向采集时间(now=None):
    return is_collection_time(now)


def init_driver():
    return initialize_source()


def 预热最新资金流向历史():
    return warm_history()


def 行业资金流向采集():
    return collect_flow("industry")


def 概念资金流向采集():
    return collect_flow("concept")


def 采集全部资金流向():
    return collect_all_flows()


def start_monitor(stop_event):
    return _start_monitor(stop_event)


if __name__ == "__main__":
    采集全部资金流向()
