import importlib
import json

from .contracts import translate_legacy_fund_flow


LEGACY_REDIS_PREFIXES = {
    "industry": "fund_flow",
    "concept": "fund_flow_\u6982\u5ff5",
}


class LegacyFundFlowReadAdapter:
    def __init__(self, redis):
        self.redis = redis

    def history(self, flow_type, trade_date):
        lrange = getattr(self.redis, "lrange", None)
        if lrange is None:
            return None
        key = f"{LEGACY_REDIS_PREFIXES[flow_type]}:history:{trade_date}"
        snapshots = []
        for value in lrange(key, 0, -1):
            try:
                snapshot = json.loads(value)
            except (TypeError, ValueError):
                continue
            if isinstance(snapshot, list) and snapshot:
                snapshots.append(translate_legacy_fund_flow(snapshot))
        return snapshots or None

    def dates(self, flow_type):
        keys = getattr(self.redis, "keys", None)
        if keys is None:
            return []
        prefix = LEGACY_REDIS_PREFIXES[flow_type]
        result = []
        for key in keys(f"{prefix}:history:*"):
            if isinstance(key, bytes):
                key = key.decode()
            result.append(key.rsplit(":", 1)[-1])
        return result


class LegacyFundFlowCollectorAdapter:
    def __init__(self, module=None):
        self._module = module or importlib.import_module("\u5b9e\u65f6\u76d1\u63a7.\u8d44\u91d1\u6d41\u5411")

    def collection_interval_seconds(self):
        return getattr(self._module, "\u83b7\u53d6\u8d44\u91d1\u6d41\u5411\u91c7\u96c6\u95f4\u9694\u79d2")()

    def initialize(self):
        return self._module.init_driver()

    def warm_history(self):
        return getattr(self._module, "\u9884\u70ed\u6700\u65b0\u8d44\u91d1\u6d41\u5411\u5386\u53f2")()

    def wait_until_next_run(self):
        return getattr(self._module, "\u7b49\u5f85\u5230\u4e0b\u6b21\u5bf9\u9f50\u6267\u884c")()

    def is_collection_time(self, now):
        return getattr(self._module, "\u5f53\u524d\u662f\u8d44\u91d1\u6d41\u5411\u91c7\u96c6\u65f6\u95f4")(now)

    def collect_all(self):
        return getattr(self._module, "\u91c7\u96c6\u5168\u90e8\u8d44\u91d1\u6d41\u5411")()
