from stock_lab.modules.strategy_pick.collector import (
    refresh_all_strategies,
    refresh_strategy,
    start_strategy_pick_monitor,
)
from stock_lab.modules.strategy_pick.source import decode_response, parse_strategy_response


def 策略选股采集(strategy_id=None, 最大重试次数=None):
    return refresh_strategy(strategy_id, 最大重试次数)


def 采集全部启用策略():
    return refresh_all_strategies()


def 解析响应体(body):
    return decode_response(body)


def 解析策略选股接口响应(data):
    return parse_strategy_response(data)


def start_monitor(stop_event=None):
    return start_strategy_pick_monitor(stop_event)


if __name__ == "__main__":
    采集全部启用策略()
