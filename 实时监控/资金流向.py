from stock_lab.modules.fund_flow.collector import create_fund_flow_source, run_fund_flow_monitor


_source = None


def _get_source():
    global _source
    if _source is None:
        _source = create_fund_flow_source()
    return _source


def 获取资金流向采集间隔秒():
    return _get_source().collection_interval_seconds()


def 等待到下次对齐执行(interval_seconds=None):
    return _get_source().wait_until_next_run(interval_seconds)


def 当前是资金流向采集时间(now=None):
    if now is None:
        now = _get_source().clock()
    return _get_source().is_collection_time(now)


def init_driver():
    return _get_source().initialize()


def 预热最新资金流向历史():
    return _get_source().warm_history()


def 行业资金流向采集():
    return _get_source().collect("industry")


def 概念资金流向采集():
    return _get_source().collect("concept")


def 采集全部资金流向():
    return _get_source().collect_all()


def start_monitor(stop_event):
    return run_fund_flow_monitor(stop_event, source=_get_source())


if __name__ == "__main__":
    采集全部资金流向()
