from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_lab.infrastructure.market_data import BaoStockSource
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.contracts import IntradayBarSource
from stock_lab.modules.market_data.helpers import (
    normalize_symbol,
    normalize_ts_code,
    validated_trade_date,
)
from stock_lab.modules.market_data.parsing import (
    normalize_intraday_bar,
    normalize_intraday_source_ts_code,
)
from stock_lab.modules.market_data.repository import MarketDataRepository
from stock_lab.shared.errors import DataValidationError


def _default_repository():
    return create_default_repository()


def fetch_intraday_bars_5m(
    start_date, end_date, ts_code, source: IntradayBarSource | None = None
):
    start_date = validated_trade_date(start_date, "intraday start date")
    end_date = validated_trade_date(end_date, "intraday end date")
    if start_date > end_date:
        raise DataValidationError(
            f"Invalid intraday date range: {start_date}-{end_date}"
        )
    requested_ts_code = normalize_ts_code(ts_code)
    requested_symbol = normalize_symbol(requested_ts_code)
    if len(requested_symbol) != 6 or not requested_symbol.isdigit():
        raise DataValidationError(f"Invalid intraday stock code: {ts_code!r}")
    source = source or BaoStockSource()
    rows = []
    for source_row in source.fetch_5m_bars(
        start_date,
        end_date,
        ts_code,
    ):
        if normalize_intraday_source_ts_code(
            source_row.get("code")
        ) != requested_ts_code:
            raise DataValidationError(
                "Intraday response does not match requested security or date range"
            )
        row = normalize_intraday_bar(source_row)
        if (
            row["stock_code"] != requested_symbol
            or not start_date <= row["trade_date"] <= end_date
        ):
            raise DataValidationError(
                "Intraday response does not match requested security or date range"
            )
        rows.append(row)
    return rows


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
