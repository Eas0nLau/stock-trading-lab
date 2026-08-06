import datetime
import importlib
import threading

from .contracts import translate_legacy_strategy_pick


class LegacyStrategyPickCollectorAdapter:
    def __init__(self, module=None):
        self._module = module

    @property
    def module(self):
        if self._module is None: self._module = importlib.import_module("实时监控.策略选股")
        return self._module

    def collect(self, strategy_id):
        return getattr(self.module, "\u7b56\u7565\u9009\u80a1\u91c7\u96c6")(strategy_id)

    def run(self, stop_event, collector):
        getattr(self.module, "\u521d\u59cb\u5316\u7b56\u7565\u914d\u7f6e")()
        slots = {}; log_slots = {}
        while not stop_event.is_set():
            snapshots = getattr(self.module, "\u91c7\u96c6\u5230\u671f\u7b56\u7565")(datetime.datetime.now(), slots, log_slots)
            for snapshot in snapshots:
                collector.persist_legacy_snapshot(snapshot)
            stop_event.wait(1)


class StrategyPickCollector:
    def __init__(self, repository, *, adapter=None):
        self.repository = repository
        self.adapter = adapter or LegacyStrategyPickCollectorAdapter()

    def refresh(self, strategy_id):
        return self.persist_legacy_snapshot(self.adapter.collect(strategy_id))

    def persist_legacy_snapshot(self, legacy_snapshot):
        snapshot = translate_legacy_strategy_pick(legacy_snapshot)
        strategy_id = snapshot.get("strategyId")
        date = snapshot.get("collectedDate") or datetime.datetime.now().strftime("%Y%m%d")
        snapshot["collectedDate"] = date
        added = snapshot.get("addedStocks") or []
        stock_info = {stock.get("code"): stock for stock in snapshot.get("stocks") or [] if stock.get("code")}
        self.repository.save_snapshot(strategy_id, snapshot, update_latest=snapshot.get("status") == "success", write_legacy=False)
        self.repository.save_events(strategy_id, date, added, write_legacy=False)
        self.repository.save_selected_state(strategy_id, stock_info.keys(), stock_info, write_legacy=False)
        self.repository.publish_snapshot(snapshot)
        return snapshot

    def refresh_all(self):
        results = []
        for strategy in self.repository.strategies():
            if strategy.get("enabled", True): results.append(self.refresh(strategy["id"]))
        return results


def run_strategy_pick_monitor(stop_event=None, *, collector=None, adapter=None):
    stop_event = stop_event or threading.Event()
    if collector is None:
        from utils import db
        from .repository import StrategyPickRepository
        collector = StrategyPickCollector(StrategyPickRepository(db.redis_con_localhost), adapter=adapter)
    adapter = adapter or collector.adapter
    return adapter.run(stop_event, collector)
