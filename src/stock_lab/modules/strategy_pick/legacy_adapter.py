import json

from .contracts import LEGACY_KEY_MAP, translate_legacy_strategy_pick


LEGACY_DEFAULT_STRATEGY_ID = "eastmoney_1"
LEGACY_STRATEGY_CONFIG_KEYS = {
    "id": "id",
    "name": "名称",
    "pageUrl": "页面URL",
    "listenTargets": "监听目标",
    "monitorPeriods": "监控时间段",
    "monitorIntervalSeconds": "监控频率秒",
    "enabled": "启用",
    "createdAt": "创建时间",
    "updatedAt": "更新时间",
}


class LegacyStrategyPickReadAdapter:
    def __init__(self, redis, default_strategy_id=LEGACY_DEFAULT_STRATEGY_ID):
        self.redis = redis
        self.default_strategy_id = default_strategy_id

    def strategies(self):
        value = _json_value(self.redis.get("策略选股:strategies"), [])
        return translate_legacy_strategy_pick(value)

    def latest(self, strategy_id):
        keys = [f"策略选股:{strategy_id}:latest"]
        if strategy_id == self.default_strategy_id:
            keys.append("策略选股:latest")
        for key in keys:
            value = _json_value(self.redis.get(key), None)
            if value is not None: return translate_legacy_strategy_pick(value)
        return {}

    def history(self, strategy_id, date):
        return _json_list(self.redis.lrange(f"策略选股:{strategy_id}:history:{date}"))

    def events(self, strategy_id, date):
        return _json_list(self.redis.lrange(f"策略选股:{strategy_id}:events:{date}"))

    def global_events(self, date):
        return _json_list(self.redis.lrange(f"策略选股:events:{date}"))

    def dates(self, strategy_id=None):
        patterns = ["策略选股:*:history:*", "策略选股:*:events:*"] if strategy_id is None else [f"策略选股:{strategy_id}:history:*", f"策略选股:{strategy_id}:events:*"]
        dates = set()
        for pattern in patterns:
            for key in self.redis.keys(pattern):
                if isinstance(key, bytes): key = key.decode()
                dates.add(key.rsplit(":", 1)[-1])
        return sorted(dates, reverse=True)


class LegacyStrategyPickWriteAdapter:
    def __init__(self, redis):
        self.redis = redis

    def save_snapshot(self, strategy_id, snapshot, update_latest):
        legacy = _legacy_value(snapshot)
        date = snapshot.get("collectedDate")
        self.redis.rpush(f"策略选股:{strategy_id}:history:{date}", json.dumps(legacy, ensure_ascii=False))
        if update_latest:
            key = "策略选股:latest" if strategy_id == "eastmoney_default" else f"策略选股:{strategy_id}:latest"
            self.redis.set(key, json.dumps(legacy, ensure_ascii=False))

    def save_strategies(self, strategies):
        payload = [_legacy_strategy_config(strategy) for strategy in strategies]
        self.redis.set("策略选股:strategies", json.dumps(payload, ensure_ascii=False))

    def save_events(self, strategy_id, date, events):
        for event in events:
            encoded = json.dumps(_legacy_value(event), ensure_ascii=False)
            self.redis.rpush(f"策略选股:{strategy_id}:events:{date}", encoded)
            self.redis.rpush(f"策略选股:events:{date}", encoded)

    def save_selected_state(self, strategy_id, codes, stock_info):
        code_key = f"策略选股:{strategy_id}:selected_codes"
        self.redis.delete(code_key)
        if codes: self.redis.sadd(code_key, *sorted(codes))
        self.redis.set(f"策略选股:{strategy_id}:selected_info", json.dumps(_legacy_value(stock_info), ensure_ascii=False))


def _json_value(value, default):
    if not value: return default
    if isinstance(value, bytes): value = value.decode()
    try: return json.loads(value)
    except (TypeError, ValueError): return default


def _json_list(values):
    result = []
    for value in values or []:
        parsed = _json_value(value, None)
        if parsed is not None: result.append(translate_legacy_strategy_pick(parsed))
    return result


def _legacy_value(value):
    reverse = {value: key for key, value in LEGACY_KEY_MAP.items()}
    if isinstance(value, list): return [_legacy_value(item) for item in value]
    if not isinstance(value, dict): return value
    return {reverse.get(key, key): _legacy_value(nested) for key, nested in value.items()}


def _legacy_strategy_config(strategy):
    return {
        legacy_key: strategy.get(v1_key)
        for v1_key, legacy_key in LEGACY_STRATEGY_CONFIG_KEYS.items()
        if v1_key in strategy
    }
