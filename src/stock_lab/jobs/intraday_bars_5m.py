from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_lab.infrastructure.market_data import BaoStockSource
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.contracts import IntradayBarSource
from stock_lab.modules.market_data.helpers import normalize_ts_code
from stock_lab.modules.market_data.parsing import normalize_intraday_bar
from stock_lab.modules.market_data.repository import MarketDataRepository
from stock_lab.shared.errors import DataValidationError


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


def backfill_intraday_bars_5m(
    start_date,
    end_date,
    *,
    stock_codes=None,
    source_factory=None,
    repository=None,
    max_workers=4,
):
    repository = repository or _default_repository()
    max_workers = int(max_workers)
    if max_workers <= 0:
        raise DataValidationError("max_workers must be greater than zero")
    if stock_codes is None:
        stock_codes = [row.get("ts_code") for row in repository.securities()]
    normalized_codes = {normalize_ts_code(code) for code in stock_codes}
    codes = sorted(code for code in normalized_codes if code)
    if not codes:
        raise DataValidationError("No securities available for intraday backfill")
    source_factory = source_factory or BaoStockSource
    result = {
        "status": "success",
        "updated": 0,
        "processed_codes": [],
        "empty_codes": [],
        "failed": [],
    }

    def fetch(code):
        return fetch_intraday_bars_5m(
            start_date,
            end_date,
            code,
            source=source_factory(),
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                rows = future.result()
                if not rows:
                    result["empty_codes"].append(code)
                    continue
                result["updated"] += repository.upsert_intraday_bars_5m(rows)
                result["processed_codes"].append(code)
            except Exception as error:
                result["failed"].append({
                    "stock_code": code,
                    "error": str(error),
                })
    result["processed_codes"].sort()
    result["empty_codes"].sort()
    result["failed"].sort(key=lambda item: item["stock_code"])
    if result["failed"] or (
        not result["processed_codes"]
        and len(result["empty_codes"]) == len(codes)
    ):
        result["status"] = "failed"
    return result
