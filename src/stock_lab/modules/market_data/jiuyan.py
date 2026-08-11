import os

from loguru import logger

from .jiuyan_parsing import IncompleteJiuyanResponse, ParsedJiuyanBatch, parse_batch, parse_response
from .jiuyan_source import (
    HumanVerificationRequired,
    JiuyanBrowserSource,
    LISTEN_TARGET,
    MAX_REQUEST_INTERVAL_SECONDS,
    MIN_REQUEST_INTERVAL_SECONDS,
    PAGE_TEMPLATE,
    decode_response as _decode_response,
    format_page_date,
    page_requires_human_verification,
    random,
    time,
    wait_for_request_slot,
)


MAX_ATTEMPTS = max(int(os.getenv("JIUYAN_MAX_ATTEMPTS", "2")), 1)


class JiuyanCollector:
    def __init__(self, repository, response_source, parser=parse_response, max_attempts=MAX_ATTEMPTS):
        self.repository = repository
        self.response_source = response_source
        self.parser = parser
        self.max_attempts = max(int(max_attempts), 1)

    def collect(self, trade_date):
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                rows = self.parser(self.response_source(int(trade_date)), int(trade_date))
                canonical = [{
                    "data_id": row.get("data_id"), "trade_date": row.get("date"),
                    "board_name": row.get("板块"), "board_stock_count": row.get("板块个股数量"),
                    "stock_code": str(row.get("股票代码") or "").zfill(6), "stock_name": row.get("股票名称"),
                    "source_code": row.get("code"), "limit_up_at": row.get("涨停时间"),
                    "board_streak": row.get("几天几板"), "change_pct": row.get("涨幅"),
                    "limit_up_reason": row.get("涨停解析"),
                } for row in rows]
                return self.repository.upsert_jiuyan_actions(canonical)
            except HumanVerificationRequired:
                raise
            except Exception as error:
                last_error = error
                logger.warning("Jiuyan collection attempt {}/{} failed: {}", attempt, self.max_attempts, error)
        raise IncompleteJiuyanResponse(f"Jiuyan collection failed for {trade_date}: {last_error}") from last_error


def create_default_collector():
    from stock_lab.infrastructure.browser import close_page, create_page

    from .collectors import create_default_repository

    return JiuyanCollector(
        create_default_repository(),
        JiuyanBrowserSource(create_page, close_page),
    )


def collect_jiuyan_actions(trade_date):
    return create_default_collector().collect(trade_date)
