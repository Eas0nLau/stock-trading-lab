from stock_lab.config import get_settings
from stock_lab.infrastructure.cache.redis_client import create_redis_client
from stock_lab.infrastructure.database import create_database_client
from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource, RedisPageCache
from stock_lab.modules.market_data.repository import MarketDataRepository

from .analytics import analyze_broker_premium
from .collectors import collect_broker_directory, collect_broker_history, collect_listings
from .repository import DragonTigerRepository


def main(start_date, latest_date):
    database = create_database_client()
    return analyze_broker_premium(
        int(start_date),
        int(latest_date),
        DragonTigerRepository(database.query, database.engine),
        MarketDataRepository(database.query, database.engine),
    )


def create_repository():
    database = create_database_client()
    return DragonTigerRepository(database.query, database.engine)


def collect_listings_for_date(trade_date, repository=None, source=None):
    source = source or DragonTigerHttpSource()
    return collect_listings(int(trade_date), repository or create_repository(), source.fetch_listing_page)


def collect_broker_directory_data(repository=None, source=None):
    source = source or DragonTigerHttpSource()
    return collect_broker_directory(repository or create_repository(), source.broker_directory_pages)


def collect_broker_history_data(repository=None, source=None, cache=None):
    source = source or DragonTigerHttpSource()
    cache = cache or RedisPageCache(create_redis_client(get_settings()))
    return collect_broker_history(repository or create_repository(), source.fetch_broker_history_page, cache)
