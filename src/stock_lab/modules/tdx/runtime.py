import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from loguru import logger

from stock_lab.infrastructure.tdx import TdxQuoteSubscription, TdxSettings, close_tq, get_market_snapshot, load_tq, refresh_tdx_cache
from .auction_monitor import AuctionState, build_monitor_row, current_auction_phase, process_auction_rows
from .global_monitor import check_alerts
from .snapshot import extract_snapshot_row


def configured_codes() -> list[str]:
    return [item.strip().upper() for item in os.getenv("TDX_CODES", "000001.SZ").split(",") if item.strip()]


def run_global_monitor(
    settings: Any,
    codes: Iterable[str] | None = None,
    max_loops: int = 0,
    interval: float = 2.0,
    client_factory: Callable[[Path], Any] = load_tq,
    quote_reader: Callable[[Any, str], dict[str, Any]] = get_market_snapshot,
    refresh: Callable[[Any], Any] = refresh_tdx_cache,
    subscription_factory: Callable[[], TdxQuoteSubscription] = TdxQuoteSubscription,
    sleep: Callable[[float], None] = time.sleep,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    tdx = TdxSettings.from_settings(settings)
    tq = client_factory(tdx.root)
    codes = list(codes or configured_codes())
    subscription = None
    subscribed = False
    previous, history = {}, {}
    emit = emit or (lambda event: logger.warning(event["message"]))
    try:
        subscription = subscription_factory()
        subscription.subscribe(tq, codes)
        subscribed = True
        for loop in range(1, max_loops + 1 if max_loops else 2**31):
            refresh(tq)
            rows = [extract_snapshot_row(code, subscription.get_latest(code) or quote_reader(tq, code), datetime.now()) for code in codes]
            check_alerts(rows, previous, history, True, True, 0, emit)
            if max_loops and loop >= max_loops:
                return rows
            sleep(interval)
    finally:
        try:
            if subscribed and subscription is not None:
                subscription.unsubscribe(tq)
        finally:
            close_tq(tq)


def run_auction_monitor(
    settings: Any,
    repository: Any,
    codes: Iterable[str] | None = None,
    max_loops: int = 0,
    interval: float = 3.0,
    client_factory: Callable[[Path], Any] = load_tq,
    quote_reader: Callable[[Any, str], dict[str, Any]] = get_market_snapshot,
    refresh: Callable[[Any], Any] = refresh_tdx_cache,
    subscription_factory: Callable[[], TdxQuoteSubscription] = TdxQuoteSubscription,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], str] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    from .universe import load_mainboard_non_st_codes

    tdx = TdxSettings.from_settings(settings)
    codes = list(codes or load_mainboard_non_st_codes(repository))
    tq = client_factory(tdx.root)
    normalized = codes
    subscription = None
    subscribed = False
    state, alerted = AuctionState(), set()
    clock = clock or (lambda: datetime.now().strftime("%H:%M:%S"))
    emit = emit or (lambda event: logger.warning("TDX auction {} {}", event["signal"], event["code"]))
    try:
        subscription = subscription_factory()
        subscription.subscribe(tq, normalized)
        subscribed = True
        loops = 0
        while True:
            phase = current_auction_phase(clock())
            if not phase:
                if clock() > "09:25:00":
                    return []
                sleep(min(interval, 1.0))
                continue
            loops += 1
            refresh(tq)
            rows = [build_monitor_row(extract_snapshot_row(code, subscription.get_latest(code) or quote_reader(tq, code), datetime.now())) for code in normalized]
            process_auction_rows(rows, phase, state, alerted, emit)
            if max_loops and loops >= max_loops:
                return rows
            sleep(interval)
    finally:
        try:
            if subscribed and subscription is not None:
                subscription.unsubscribe(tq)
        finally:
            close_tq(tq)
