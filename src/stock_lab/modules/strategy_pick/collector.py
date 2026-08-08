import datetime
import threading
from functools import partial

from .contracts import translate_legacy_strategy_pick


_default_collector = None


class StrategyPickCollector:
    def __init__(self, repository, *, adapter=None, settings=None):
        self.repository = repository
        self.adapter = adapter or create_strategy_pick_source(repository, settings=settings)

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


def create_strategy_pick_collector(redis, *, adapter=None, settings=None, mysql_repository=None):
    from stock_lab.config.defaults import DEFAULT_STRATEGY_PICK_STRATEGIES

    from .repository import StrategyPickRepository
    from .service import StrategyPickService

    repository = StrategyPickRepository(redis, mysql_repository)
    StrategyPickService(repository, default_strategies=DEFAULT_STRATEGY_PICK_STRATEGIES).strategies()
    return StrategyPickCollector(repository, adapter=adapter, settings=settings)


def create_strategy_pick_source(repository, *, settings=None):
    from stock_lab.infrastructure.browser.client import create_page

    from .source import StrategyPickSource

    return StrategyPickSource(
        partial(create_page, settings=settings),
        repository,
        settings=settings,
    )


def run_strategy_pick_monitor(stop_event=None, *, settings=None, collector=None, adapter=None):
    stop_event = stop_event or threading.Event()
    if collector is None:
        from stock_lab.config import get_settings
        from stock_lab.infrastructure.cache.redis_client import create_redis_client
        from stock_lab.infrastructure.database import create_database_client
        from .mysql_repository import StrategyPickMySQLRepository
        settings = settings or get_settings()
        database = create_database_client(settings)
        collector = create_strategy_pick_collector(
            create_redis_client(settings),
            adapter=adapter,
            settings=settings,
            mysql_repository=StrategyPickMySQLRepository(lambda: database.resources.get_pool().get_connection()),
        )
    adapter = adapter or collector.adapter
    return adapter.run(stop_event, collector)


def get_strategy_pick_collector():
    global _default_collector
    if _default_collector is None:
        from stock_lab.config import get_settings
        from stock_lab.infrastructure.cache.redis_client import create_redis_client
        from stock_lab.infrastructure.database import create_database_client
        from .mysql_repository import StrategyPickMySQLRepository
        settings = get_settings()
        database = create_database_client(settings)

        _default_collector = create_strategy_pick_collector(
            create_redis_client(settings),
            settings=settings,
            mysql_repository=StrategyPickMySQLRepository(lambda: database.resources.get_pool().get_connection()),
        )
    return _default_collector


def refresh_strategy(strategy_id=None, max_retries=None):
    collector = get_strategy_pick_collector()
    if strategy_id is None:
        strategy_id = next(item["id"] for item in collector.repository.strategies() if item.get("enabled", True))
    return collector.refresh(strategy_id)


def refresh_all_strategies():
    return get_strategy_pick_collector().refresh_all()


def start_strategy_pick_monitor(stop_event=None):
    return run_strategy_pick_monitor(stop_event, collector=get_strategy_pick_collector())
