from stock_lab.config import get_settings
from stock_lab.infrastructure.cache.redis_client import create_redis_client
from stock_lab.infrastructure.database import create_database_client
from stock_lab.infrastructure.market_data.dragon_tiger import DragonTigerHttpSource, RedisPageCache
from stock_lab.modules.market_data.repository import MarketDataRepository

from .analytics import analyze_broker_premium
from .collectors import collect_broker_directory, collect_broker_history, collect_listings
from .repository import DragonTigerRepository
from .jobs import DragonTigerCollectionJobManager


def main(start_date, latest_date, *, settings=None, database=None):
    database = database or create_database_client(settings)
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


def collect_listings_for_range(start_date, latest_date, repository=None, source=None):
    source = source or DragonTigerHttpSource()
    return collect_listings(
        int(start_date),
        repository or create_repository(),
        source.fetch_listing_page,
        end_date=int(latest_date),
    )


def analyze_premium_result(start_date, latest_date, *, settings=None, database=None):
    selected_codes = main(start_date, latest_date, settings=settings, database=database)
    selected_codes = list(selected_codes or [])
    return {
        "startDate": int(start_date),
        "latestDate": int(latest_date),
        "selectedCount": len(selected_codes),
        "selectedCodes": selected_codes,
        "sourceTables": ["dragon_tiger", "broker_listing_history", "daily_quotes"],
    }


def create_collection_job_manager(*, settings=None):
    settings = settings or get_settings()
    database = create_database_client(settings)
    repository = DragonTigerRepository(database.query, database.engine)
    source = DragonTigerHttpSource()
    redis = create_redis_client(settings)
    manager = DragonTigerCollectionJobManager(
        redis,
        run_listings=lambda start, latest: collect_listings(
            start, repository, source.fetch_listing_page, end_date=latest
        ),
        run_broker_directory=lambda *_dates: collect_broker_directory_data(repository, source),
        run_broker_history=lambda *_dates: collect_broker_history_data(repository, source, RedisPageCache(redis)),
        run_analysis=lambda start, latest: analyze_premium_result(
            start, latest, settings=settings, database=database
        ),
    )
    manager.database = database
    return manager


def collect_broker_directory_data(repository=None, source=None):
    source = source or DragonTigerHttpSource()
    return collect_broker_directory(repository or create_repository(), source.broker_directory_pages)


def collect_broker_history_data(repository=None, source=None, cache=None):
    source = source or DragonTigerHttpSource()
    cache = cache or RedisPageCache(create_redis_client(get_settings()))
    return collect_broker_history(repository or create_repository(), source.fetch_broker_history_page, cache)
