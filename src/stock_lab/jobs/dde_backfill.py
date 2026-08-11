import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_lab.infrastructure.market_data import KplDdeSource
from stock_lab.modules.market_data.collectors import create_default_repository
from stock_lab.modules.market_data.helpers import (
    dde_from_source,
    normalize_trade_date,
    normalize_ts_code,
)


def update_dde(
    start_date=None,
    end_date=None,
    *,
    source=None,
    repository=None,
    force=False,
    max_workers=4,
    timeout=20,
    retries=3,
):
    today = int(dt.date.today().strftime("%Y%m%d"))
    start_date = normalize_trade_date(start_date or today)
    end_date = normalize_trade_date(end_date or start_date)
    if not start_date or not end_date or start_date > end_date:
        raise ValueError(f"Invalid DDE date range: {start_date}-{end_date}")
    max_workers = int(max_workers)
    if max_workers <= 0:
        raise ValueError("max_workers must be greater than zero")
    source = source or KplDdeSource()
    repository = repository or create_default_repository()
    quotes = repository.daily_quotes(start_date=start_date, end_date=end_date)
    codes = sorted({
        normalize_ts_code(row.get("ts_code"))
        for row in quotes
        if row.get("ts_code")
        and (force or row.get("dde_net_amount") is None)
    })
    result = {
        "status": "success",
        "updated": 0,
        "processed_codes": [],
        "empty_codes": [],
        "failed": [],
    }

    def fetch(code):
        return source.fetch_daily_dde(
            code,
            start_date=start_date,
            end_date=end_date,
            timeout=timeout,
            retries=retries,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                source_rows = future.result()
                if not source_rows:
                    result["empty_codes"].append(code)
                    continue
                rows = []
                for source_row in source_rows:
                    row = dde_from_source(source_row)
                    if row["dde_net_amount"] is not None:
                        rows.append(row)
                if not rows:
                    result["empty_codes"].append(code)
                    continue
                result["updated"] += repository.update_daily_quote_enrichment(
                    rows,
                    ("dde_net_amount",),
                    only_missing=not force,
                )
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
        codes
        and not result["processed_codes"]
        and len(result["empty_codes"]) == len(codes)
    ):
        result["status"] = "failed"
    return result
