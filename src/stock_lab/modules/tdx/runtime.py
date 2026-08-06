import os
import time
from datetime import datetime

from loguru import logger

from stock_lab.config import get_settings
from stock_lab.infrastructure.tdx import TdxQuoteSubscription, TdxSettings, close_tq, get_market_snapshot, load_tq, refresh_tdx_cache
from .global_monitor import can_emit_alert, crossed_above
from .snapshot import extract_snapshot_row


def _codes():
    return [item.strip().upper() for item in os.getenv("TDX_CODES", "000001.SZ").split(",") if item.strip()]


def run_global_monitor(max_loops=0, codes=None):
    tdx = TdxSettings.from_settings(get_settings())
    tq = load_tq(tdx.root)
    codes = codes or _codes()
    subscription = TdxQuoteSubscription()
    subscription.subscribe(tq, codes)
    previous = {}
    history = {}
    try:
        loops = 0
        while True:
            loops += 1
            refresh_tdx_cache(tq)
            rows = [extract_snapshot_row(code, subscription.get_latest(code) or get_market_snapshot(tq, code), datetime.now()) for code in codes]
            for row in rows:
                code = row["代码"]
                old = previous.get(code, {})
                if crossed_above(old.get("最新价"), row.get("最新价"), old.get("开盘价"), row.get("开盘价")) and can_emit_alert(history, code, "open", time.time(), 0):
                    logger.warning("TDX open-price break: {}", code)
                previous[code] = row
            if max_loops and loops >= max_loops:
                return rows
            time.sleep(2)
    finally:
        subscription.unsubscribe(tq)
        close_tq(tq)


def run_auction_monitor(max_loops=0, codes=None):
    from .auction_monitor import build_monitor_row
    return run_global_monitor(max_loops=max_loops, codes=codes)
