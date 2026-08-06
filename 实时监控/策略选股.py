from stock_lab.infrastructure.cache.redis_client import create_redis_client
from stock_lab.config import get_settings
from stock_lab.modules.strategy_pick.collector import create_strategy_pick_collector, run_strategy_pick_monitor
from stock_lab.modules.strategy_pick.source import decode_response, parse_strategy_response


_collector = None


def _get_collector():
    global _collector
    if _collector is None:
        _collector = create_strategy_pick_collector(create_redis_client(get_settings()))
    return _collector


def 策略选股采集(strategy_id=None, 最大重试次数=None):
    collector = _get_collector()
    if strategy_id is None:
        strategy_id = next(item["id"] for item in collector.repository.strategies() if item.get("enabled", True))
    return collector.refresh(strategy_id)


def 采集全部启用策略():
    return _get_collector().refresh_all()


def 解析响应体(body):
    return decode_response(body)


def 解析策略选股接口响应(data):
    return parse_strategy_response(data)


def start_monitor(stop_event=None):
    return run_strategy_pick_monitor(stop_event, collector=_get_collector())


if __name__ == "__main__":
    采集全部启用策略()
