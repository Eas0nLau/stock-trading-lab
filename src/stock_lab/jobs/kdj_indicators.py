from stock_lab.modules.market_data.indicators import calculate_kdj
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.helpers import validated_trade_date
from stock_lab.modules.market_data.repository import MarketDataRepository
from stock_lab.shared.errors import DataValidationError


def _default_repository():
    return create_default_repository()


def update_kdj_indicators(start_date, end_date, stock_codes=None, repository=None, period=9):
    start_date = validated_trade_date(start_date, "KDJ start date")
    end_date = validated_trade_date(end_date, "KDJ end date")
    if start_date > end_date:
        raise DataValidationError(
            f"Invalid KDJ date range: {start_date}-{end_date}"
        )
    repository = repository or _default_repository()
    daily_quotes = repository.daily_quotes(stock_codes, end_date=end_date)
    rows = [
        row for row in calculate_kdj(daily_quotes, period=period)
        if int(start_date) <= row["trade_date"] <= int(end_date)
    ]
    return repository.upsert_kdj_indicators(rows)


def update_latest_kdj_indicators(stock_codes=None, repository=None, period=9):
    repository = repository or _default_repository()
    dates = repository.trading_dates(1)
    if not dates:
        raise DataValidationError("No trading date available for KDJ update")
    trade_date = max(int(value) for value in dates)
    return update_kdj_indicators(
        trade_date,
        trade_date,
        stock_codes=stock_codes,
        repository=repository,
        period=period,
    )
