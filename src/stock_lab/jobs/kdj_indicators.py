from stock_lab.modules.market_data.indicators import calculate_kdj
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.repository import MarketDataRepository


def _default_repository():
    return create_default_repository()


def update_kdj_indicators(start_date, end_date, stock_codes=None, repository=None, period=9):
    repository = repository or _default_repository()
    daily_quotes = repository.daily_quotes(stock_codes, end_date=end_date)
    rows = [
        row for row in calculate_kdj(daily_quotes, period=period)
        if int(start_date) <= row["trade_date"] <= int(end_date)
    ]
    return repository.upsert_kdj_indicators(rows)
