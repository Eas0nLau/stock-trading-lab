from stock_lab.infrastructure.market_data import BaoStockSource
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.contracts import IntradayBarSource
from stock_lab.modules.market_data.parsing import normalize_intraday_bar
from stock_lab.modules.market_data.repository import MarketDataRepository


def _default_repository():
    return create_default_repository()


def fetch_intraday_bars_5m(
    start_date, end_date, ts_code, source: IntradayBarSource | None = None
):
    source = source or BaoStockSource()
    return [
        normalize_intraday_bar(row)
        for row in source.fetch_5m_bars(start_date, end_date, ts_code)
    ]


def update_intraday_bars_5m(
    start_date, end_date, ts_code, source: IntradayBarSource | None = None, repository=None
):
    rows = fetch_intraday_bars_5m(start_date, end_date, ts_code, source)
    return (repository or _default_repository()).upsert_intraday_bars_5m(rows)
