import datetime
import threading

from .contracts import translate_legacy_strategy_pick


class StrategyPickCollector:
    def __init__(self, repository, *, adapter=None):
        self.repository = repository
        self.adapter = adapter or create_strategy_pick_source(repository)

    def refresh(self, strategy_id):
        return self.persist_legacy_snapshot(self.adapter.collect(strategy_id))

    def persist_legacy_snapshot(self, legacy_snapshot):
        snapshot = translate_legacy_strategy_pick(legacy_snapshot)
        strategy_id = snapshot.get("strategyId")
        date = snapshot.get("collectedDate") or datetime.datetime.now().strftime("%Y%m%d")
        snapshot["collectedDate"] = date
        added = snapshot.get("addedStocks") or []
        stock_info = {stock.get("code"): stock for stock in snapshot.get("stocks") or [] if stock.get("code")}
        self.repository.save_snapshot(strategy_id, snapshot, update_latest=snapshot.get("status") == "success")
        self.repository.save_events(strategy_id, date, added)
        self.repository.save_selected_state(strategy_id, stock_info.keys(), stock_info)
        self.repository.publish_snapshot(snapshot)
        return snapshot

    def refresh_all(self):
        results = []
        for strategy in self.repository.strategies():
            if strategy.get("enabled", True): results.append(self.refresh(strategy["id"]))
        return results


def create_strategy_pick_collector(redis, *, adapter=None):
    from stock_lab.config.defaults import DEFAULT_STRATEGY_PICK_STRATEGIES

    from .repository import StrategyPickRepository
    from .service import StrategyPickService

    repository = StrategyPickRepository(redis)
    StrategyPickService(repository, default_strategies=DEFAULT_STRATEGY_PICK_STRATEGIES).strategies()
    return StrategyPickCollector(repository, adapter=adapter)


def create_strategy_pick_source(repository):
    from stock_lab.infrastructure.browser.client import create_page

    from .source import StrategyPickSource

    return StrategyPickSource(create_page, repository)


def run_strategy_pick_monitor(stop_event=None, *, collector=None, adapter=None):
    stop_event = stop_event or threading.Event()
    if collector is None:
        from utils import db
        collector = create_strategy_pick_collector(db.redis_con_localhost, adapter=adapter)
    adapter = adapter or collector.adapter
    return adapter.run(stop_event, collector)
