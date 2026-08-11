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
    def __init__(
        self,
        repository,
        response_source,
        parser=parse_batch,
        max_attempts=MAX_ATTEMPTS,
        total_timeout_seconds=180,
        monotonic=time.monotonic,
        exporter=None,
    ):
        self.repository = repository
        self.response_source = response_source
        self.parser = parser
        self.max_attempts = max(int(max_attempts), 1)
        self.total_timeout_seconds = max(float(total_timeout_seconds), 0.0)
        self.monotonic = monotonic
        self.exporter = exporter

    def collect(self, trade_date):
        trade_date = int(trade_date)
        deadline = self.monotonic() + self.total_timeout_seconds
        last_error = None
        batch = None
        for attempt in range(1, self.max_attempts + 1):
            if self.monotonic() >= deadline:
                break
            try:
                response = self.response_source(
                    trade_date,
                    deadline=deadline,
                    attempt=attempt,
                )
                batch = self.parser(response, trade_date)
                break
            except HumanVerificationRequired:
                raise
            except Exception as error:
                last_error = error
                logger.warning("Jiuyan collection attempt {}/{} failed: {}", attempt, self.max_attempts, error)
        if batch is None:
            detail = last_error or "deadline exceeded"
            raise IncompleteJiuyanResponse(
                f"Jiuyan collection failed for {trade_date}: {detail}"
            ) from last_error

        manifest = {
            "trade_date": trade_date,
            "status": "complete",
            "source_board_count": batch.source_board_count,
            "source_stock_count": batch.source_stock_count,
            "accepted_stock_count": batch.accepted_stock_count,
            "source_fingerprint": batch.source_fingerprint,
        }
        updated = self.repository.replace_jiuyan_actions(
            trade_date,
            list(batch.rows),
            manifest,
        )
        result = {
            "status": "success",
            "updated": updated,
            "trade_date": trade_date,
            "export_paths": [],
            "warnings": [],
        }
        if self.exporter is not None:
            try:
                result["export_paths"] = [
                    str(path)
                    for path in self.exporter(trade_date, repository=self.repository)
                ]
            except Exception as error:
                result["status"] = "succeeded_with_warnings"
                result["warnings"].append(str(error))
        return result


def create_default_collector():
    from stock_lab.infrastructure.browser import close_page, create_page

    from .collectors import create_default_repository

    return JiuyanCollector(
        create_default_repository(),
        JiuyanBrowserSource(create_page, close_page),
    )


def collect_jiuyan_actions(trade_date):
    return create_default_collector().collect(trade_date)
