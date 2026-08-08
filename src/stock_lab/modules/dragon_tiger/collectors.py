from .parsing import (
    listing_brokers,
    listing_history,
    parse_broker_directory_page,
    parse_broker_history_page,
    parse_listing_page,
)


def collect_listings(start_date, repository, fetch_page, end_date=None):
    listings = []
    dates = (
        repository.trading_dates(start_date)
        if end_date is None
        else repository.trading_dates(start_date, end_date)
    )
    for trade_date in dates:
        listings.extend(parse_listing_page(fetch_page(trade_date), trade_date))
    brokers = listing_brokers(listings)
    history = listing_history(listings)
    return {
        "listings": repository.upsert_listings(listings),
        "brokers": repository.upsert_brokers(brokers),
        "broker_history": repository.upsert_broker_history(history),
    }


def collect_broker_directory(repository, page_provider):
    brokers = {}
    for html in page_provider():
        for broker in parse_broker_directory_page(html):
            brokers.setdefault(broker.broker_id, broker)
    return repository.upsert_brokers(brokers.values())


def _cache_get(cache, key):
    if cache is None:
        return None
    if hasattr(cache, "get"):
        return cache.get(key)
    return None


def _cache_set(cache, key, value):
    if cache is None:
        return
    if hasattr(cache, "__setitem__"):
        cache[key] = value
    elif hasattr(cache, "set"):
        cache.set(key, value)


def collect_broker_history(repository, fetch_page, cache=None):
    rows = {}
    for broker in repository.brokers():
        page = 1
        page_count = 1
        while page <= page_count:
            key = (broker.broker_id, page)
            html = _cache_get(cache, key)
            if html is None:
                html = fetch_page(broker.broker_id, page)
                _cache_set(cache, key, html)
            parsed, page_count = parse_broker_history_page(html, broker.broker_id, broker.broker_name)
            for row in parsed:
                rows[row.data_id] = row
            page += 1
    return repository.upsert_broker_history(rows.values())
