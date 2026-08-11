import datetime as dt
import time

from stock_lab.infrastructure.cache import RedisJobLock
from stock_lab.shared.errors import JobExecutionError


DAILY_UPDATE_LOCK_KEY = "stock_lab:jobs:v1:daily_update:lock"
DAILY_UPDATE_COMPLETION_PREFIX = "stock_lab:jobs:v1:daily_update:completed"
LOCK_TTL_SECONDS = 6 * 60 * 60
COMPLETION_TTL_SECONDS = 7 * 24 * 60 * 60


def daily_update_completion_key(trade_date) -> str:
    return f"{DAILY_UPDATE_COMPLETION_PREFIX}:{normalize_trade_date(trade_date)}"


def run_daily_update(
    trade_date,
    *,
    collector=None,
    state=None,
    run_hot_board=None,
    run_index=None,
) -> dict:
    trade_date = normalize_trade_date(trade_date)
    collector, state, run_hot_board, run_index = _dependencies(
        collector,
        state,
        run_hot_board,
        run_index,
    )
    completion_key = daily_update_completion_key(trade_date)
    if state.exists(completion_key):
        return _skipped_result(trade_date)

    lock = RedisJobLock(state, DAILY_UPDATE_LOCK_KEY, LOCK_TTL_SECONDS)
    if not lock.acquire():
        raise JobExecutionError("Daily update is already running")

    try:
        if state.exists(completion_key):
            return _skipped_result(trade_date)

        trading_dates = _trading_dates(collector)
        if trade_date not in trading_dates:
            collector.update_index_daily(max(1, trade_date - 10000), trade_date)
            trading_dates = _trading_dates(collector)
        if trade_date not in trading_dates:
            raise JobExecutionError(f"No trading date available for {trade_date}")

        previous_dates = [date for date in trading_dates if date < trade_date]
        if not previous_dates:
            raise JobExecutionError(f"No previous trading date available for {trade_date}")
        source_trade_date = previous_dates[-1]
        date_index = trading_dates.index(trade_date)
        start_date = trading_dates[max(0, date_index - 159)]

        index_count = collector.update_index_daily(start_date, trade_date)
        securities_count = collector.update_securities()
        quote_count = collector.update_daily_quotes(start_date, trade_date)
        market_cap_result = collector.update_market_cap(trade_date)
        market_cap_count = _enrichment_count("market_cap", market_cap_result)
        dde_result = collector.update_dde(trade_date)
        dde_count = _enrichment_count("dde", dde_result)
        counts = {
            "index_daily": index_count,
            "securities": securities_count,
            "daily_quotes": quote_count,
            "market_cap": market_cap_count,
            "dde": dde_count,
            "board_actions": collector.collect_board_actions(trade_date),
            "hot_board_emotion": run_hot_board(trade_date, source_trade_date),
            "index_emotion": run_index(trade_date),
        }
        state.set(completion_key, str(int(time.time())), ex=COMPLETION_TTL_SECONDS)
        return {
            "status": "success",
            "trade_date": trade_date,
            "source_trade_date": source_trade_date,
            "counts": counts,
        }
    finally:
        lock.release()


def backfill_daily_updates(
    days=60,
    *,
    collector=None,
    state=None,
    run_hot_board=None,
    run_index=None,
    runner=run_daily_update,
) -> dict:
    collector, state, run_hot_board, run_index = _dependencies(
        collector,
        state,
        run_hot_board,
        run_index,
    )
    requested_days = max(int(days), 1)
    dates = _trading_dates(collector)[-requested_days:]
    results = []
    for trade_date in dates:
        try:
            results.append(
                runner(
                    trade_date,
                    collector=collector,
                    state=state,
                    run_hot_board=run_hot_board,
                    run_index=run_index,
                )
            )
        except Exception as error:
            results.append(
                {
                    "status": "failed",
                    "trade_date": trade_date,
                    "error": str(error),
                }
            )
    status = "success" if all(item["status"] in {"success", "skipped"} for item in results) else "failed"
    return {"status": status, "results": results}


class DailyUpdateCollector:
    def trading_dates(self, limit):
        from stock_lab.modules.market_data.collectors import trading_dates

        return trading_dates(limit)

    def update_securities(self):
        from stock_lab.modules.market_data.collectors import update_securities

        return update_securities()

    def update_daily_quotes(self, start_date, end_date):
        from stock_lab.modules.market_data.collectors import update_daily_quotes

        return update_daily_quotes(start_date, end_date)

    def update_index_daily(self, start_date, end_date):
        from stock_lab.modules.market_data.collectors import update_index_daily

        return update_index_daily(start_date, end_date)

    def update_market_cap(self, trade_date):
        from stock_lab.jobs.market_cap_backfill import update_market_cap

        return update_market_cap(trade_date, trade_date)

    def update_dde(self, trade_date):
        from stock_lab.jobs.dde_backfill import update_dde

        return update_dde(trade_date, trade_date)

    def collect_board_actions(self, trade_date):
        from stock_lab.modules.market_data.jiuyan import collect_jiuyan_actions

        return collect_jiuyan_actions(trade_date)


def _dependencies(collector, state, run_hot_board, run_index):
    if collector is None:
        collector = DailyUpdateCollector()
    if state is None:
        from stock_lab.config import get_settings
        from stock_lab.infrastructure.cache.redis_client import create_redis_client

        state = create_redis_client(get_settings())
    if run_hot_board is None or run_index is None:
        from stock_lab.modules.emotion.jobs import (
            run_hot_board_emotion_job,
            run_index_emotion_job,
        )

        run_hot_board = run_hot_board or run_hot_board_emotion_job
        run_index = run_index or run_index_emotion_job
    return collector, state, run_hot_board, run_index


def _trading_dates(collector) -> list[int]:
    return sorted({normalize_trade_date(value) for value in collector.trading_dates(160)})


def normalize_trade_date(value) -> int:
    text = str(value or "").strip().replace("-", "")
    try:
        parsed = dt.datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"Invalid trade date: {value}") from error
    return int(parsed.strftime("%Y%m%d"))


def _skipped_result(trade_date: int) -> dict:
    return {
        "status": "skipped",
        "trade_date": trade_date,
        "reason": "already completed",
    }


def _enrichment_count(stage, result):
    if not isinstance(result, dict) or result.get("status") != "success":
        raise JobExecutionError(f"{stage} update failed: {result}")
    return int(result.get("updated", 0))
