import sys
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.tdx_util import (
    DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS,
    DEFAULT_TDX_ROOT,
    TdxCacheRefresher,
    TdxQuoteSubscription,
    close_tq,
    load_tq,
)
from tdx_全局监控 import (
    build_text_table,
    extract_snapshot_row,
    format_cell,
    lookup_stock_name,
    normalize_stock_code,
    read_snapshot_row_prefer_subscription,
    snapshot_error_row,
    to_number,
)

MONITOR_COLUMNS = [
    "读取时间",
    "竞价阶段",
    "代码",
    "名称",
    "最新价",
    "最新涨幅",
    "昨收价",
    "涨停价",
    "竞价金额(万)",
    "买一价",
    "买一量",
    "卖一价",
    "卖一量",
    "买卖量比",
    "五档总买金额(万)",
    "五档总卖金额(万)",
    "五档买卖金额比",
    "封单金额(万)",
    "封单变化(万)",
    "抢筹",
    "封板",
]


def now_hhmmss() -> str:
    return datetime.now().strftime("%H:%M:%S")


def is_in_time_window(start: str, end: str) -> bool:
    current = now_hhmmss()
    return start <= current <= end


def current_auction_phase() -> str:
    """返回当前集合竞价监控阶段。

    09:15-09:20 允许撤单，封单增加和减少都要看；
    09:20-09:25 不允许撤单，封单继续增加更有参考价值。
    """
    current = now_hhmmss()
    if AUCTION_START <= current < AUCTION_PHASE_1_END:
        return "09:15-09:20"
    if AUCTION_PHASE_2_START <= current <= AUCTION_END:
        return "09:20-09:25"
    return ""


def wait_until_time(start: str) -> None:
    while now_hhmmss() < start:
        logger.info("等待竞价开始 {} ...", start)
        time.sleep(5)


def is_non_st_name(name: str) -> bool:
    upper_name = (name or "").upper()
    return "ST" not in upper_name and "退" not in name


def load_mainboard_non_st_codes(limit: int = 0) -> List[str]:
    """从数据库 stock_basic 加载全部主板、上市、非 ST 股票。"""
    import config
    import pymysql

    sql = """
        SELECT ts_code, symbol, name
        FROM stock_basic
        WHERE market = '主板'
          AND list_status = 'L'
          AND UPPER(name) NOT LIKE '%%ST%%'
          AND name NOT LIKE '%%退%%'
          AND (ts_code LIKE '%%.SH' OR ts_code LIKE '%%.SZ')
        ORDER BY ts_code
    """
    if limit > 0:
        sql += " LIMIT %s"
        params = (limit,)
    else:
        params = ()

    connection = pymysql.connect(
        host=config.mysql_localhost_host,
        port=config.mysql_localhost_port,
        user=config.mysql_localhost_user,
        password=config.mysql_localhost_password,
        database=config.mysql_localhost_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3,
        read_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    finally:
        connection.close()

    codes: List[str] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()
        name = str(row.get("name") or "").strip()
        if ts_code.endswith((".SH", ".SZ")) and symbol.isdigit() and is_non_st_name(name):
            codes.append(ts_code)
    return codes


def resolve_watch_codes(config_codes: List[str], use_all_mainboard_non_st: bool, limit: int) -> List[str]:
    """决定本次监控使用全市场股票池，还是文件底部 WATCH_STOCK_CODES。"""
    if use_all_mainboard_non_st:
        codes = load_mainboard_non_st_codes(limit=limit)
    else:
        codes = config_codes

    if limit > 0 and not use_all_mainboard_non_st:
        return codes[:limit]
    return codes


def decimal_round_2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def stock_limit_rate(code: str, name: str) -> float:
    stock = normalize_stock_code(code)
    upper_name = (name or "").upper()
    if "ST" in upper_name or "退" in upper_name:
        return 0.05
    if stock.market == "BJ":
        return 0.30
    if stock.code.startswith(("300", "301", "688", "689")):
        return 0.20
    return 0.10


def limit_up_price(code: str, name: str, pre_close: Optional[float]) -> Optional[float]:
    if pre_close is None or pre_close <= 0:
        return None
    return decimal_round_2(pre_close * (1 + stock_limit_rate(code, name)))


def amount_from_lots(volume_lots: Optional[float], price: Optional[float]) -> Optional[float]:
    if volume_lots is None or price is None:
        return None
    # 手 * 100股 * 元 / 10000 = 万元
    return volume_lots * price / 100


def safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def truthy_label(value: bool) -> str:
    return "Y" if value else ""


def format_monitor_cell(column: str, value: Any) -> str:
    if column == "最新涨幅" and value is not None:
        return format_cell("最新涨幅", value)
    return format_cell(column, value)


def print_monitor_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    logger.info("\n{}", build_text_table(MONITOR_COLUMNS, rows, format_monitor_cell))


def emit_alert(message: str, beep: bool = True) -> None:
    logger.warning(message)
    if not beep:
        return
    try:
        import winsound

        winsound.Beep(1600, 450)
    except Exception:
        pass


def build_monitor_row(row: Dict[str, Any]) -> Dict[str, Any]:
    code = str(row.get("代码") or "")
    name = str(row.get("名称") or lookup_stock_name(code))
    latest = to_number(row.get("最新价"))
    latest_pct = to_number(row.get("最新涨幅"))
    pre_close = to_number(row.get("昨收价"))
    buy1_price = to_number(row.get("买一价"))
    buy1_lots = to_number(row.get("买一量"))
    sell1_lots = to_number(row.get("卖一量"))
    five_buy_amount = to_number(row.get("五档总买金额(万)"))
    five_sell_amount = to_number(row.get("五档总卖金额(万)"))
    auction_amount = to_number(row.get("竞价金额(万)"))
    if auction_amount is None:
        auction_amount = to_number(row.get("成交额(万)"))
    up_price = limit_up_price(code, name, pre_close)
    buy_sell_ratio = safe_ratio(buy1_lots, sell1_lots)
    seal_amount = amount_from_lots(buy1_lots, buy1_price)
    is_limit_bid = (
        up_price is not None
        and buy1_price is not None
        and buy1_price >= up_price - LIMIT_PRICE_TOLERANCE
        and latest is not None
        and latest >= up_price - LIMIT_PRICE_TOLERANCE
    )
    is_grab = (
        latest_pct is not None
        and latest_pct >= GRAB_MIN_PCT
        and auction_amount is not None
        and auction_amount >= GRAB_MIN_AMOUNT_WAN
        and (buy_sell_ratio is None or buy_sell_ratio >= GRAB_MIN_BUY_SELL_RATIO)
    )
    is_sealed = is_limit_bid and seal_amount is not None and seal_amount >= SEAL_MIN_AMOUNT_WAN

    return {
        "读取时间": row.get("读取时间"),
        "竞价阶段": "",
        "代码": code,
        "名称": name,
        "最新价": latest,
        "最新涨幅": latest_pct,
        "昨收价": pre_close,
        "涨停价": up_price,
        "竞价金额(万)": auction_amount,
        "买一价": buy1_price,
        "买一量": buy1_lots,
        "卖一价": to_number(row.get("卖一价")),
        "卖一量": sell1_lots,
        "买卖量比": buy_sell_ratio,
        "五档总买金额(万)": five_buy_amount,
        "五档总卖金额(万)": five_sell_amount,
        "五档买卖金额比": safe_ratio(five_buy_amount, five_sell_amount),
        "封单金额(万)": seal_amount,
        "封单变化(万)": None,
        "抢筹": truthy_label(is_grab),
        "封板": truthy_label(is_sealed),
        "_is_grab": is_grab,
        "_is_sealed": is_sealed,
    }


def alert_text(row: Dict[str, Any], signal: str, note: str = "") -> str:
    pieces = [
        "ALERT",
        str(row.get("读取时间")),
        str(row.get("代码")),
        str(row.get("名称")),
        signal,
        f"最新价={format_monitor_cell('最新价', row.get('最新价'))}",
        f"最新涨幅={format_monitor_cell('最新涨幅', row.get('最新涨幅'))}",
        f"竞价金额={format_monitor_cell('竞价金额(万)', row.get('竞价金额(万)'))}万",
        f"五档买={format_monitor_cell('五档总买金额(万)', row.get('五档总买金额(万)'))}万",
        f"五档卖={format_monitor_cell('五档总卖金额(万)', row.get('五档总卖金额(万)'))}万",
        f"封单={format_monitor_cell('封单金额(万)', row.get('封单金额(万)'))}万",
    ]
    if note:
        pieces.append(note)
    return " ".join(pieces)


def write_alert(row: Dict[str, Any], signal: str, note: str, beep: bool) -> None:
    emit_alert(alert_text(row, signal, note), beep)


def monitor_auction(
    codes: Iterable[str],
    tdx_root: Path,
    wait_for_auction: bool,
    max_loops: int,
    interval: float,
    refresh_cache_interval: float,
    beep: bool,
    print_table: bool,
    print_cycle_summary: bool,
) -> None:
    normalized = [normalize_stock_code(code).tq_code for code in codes]
    logger.info(
        "竞价监控启动：股票数={}，目标周期={:.2f}s，阶段={}~{} / {}~{}，数据源=通达信客户端缓存快照",
        len(normalized),
        interval,
        AUCTION_START,
        AUCTION_PHASE_1_END,
        AUCTION_PHASE_2_START,
        AUCTION_END,
    )
    logger.warning("当前通达信 PYPlugins 快照接口无法绕过客户端缓存，也无法保证交易所级无延时。")
    if wait_for_auction:
        wait_until_time(AUCTION_START)

    tq = load_tq(tdx_root, Path(__file__).resolve())
    loop_count = 0
    cache_refresher = TdxCacheRefresher(AUTO_REFRESH_CACHE, refresh_cache_interval)
    subscription = TdxQuoteSubscription(
        enabled=SUBSCRIBE_HQ_BEFORE_READ,
        warmup_seconds=SUBSCRIBE_WARMUP_SECONDS,
    )
    subscription.subscribe(tq, normalized)
    grab_alerted = set()
    # 按 (竞价阶段, 股票代码) 记录封单基准，9:20 切换阶段后重新比较。
    last_seal_amount: Dict[tuple, float] = {}

    try:
        while True:
            if STOP_AFTER_AUCTION_END and now_hhmmss() > AUCTION_END:
                logger.info("{} 竞价窗口结束，停止监控。", AUCTION_END)
                break
            phase = current_auction_phase()
            if not phase:
                time.sleep(min(interval, 1.0))
                continue

            cycle_started = time.time()
            loop_count += 1

            cache_refresher.maybe_refresh(tq)

            rows = []
            for code in normalized:
                read_time = datetime.now()
                try:
                    row, _ = read_snapshot_row_prefer_subscription(
                        tq=tq,
                        code=code,
                        read_time=read_time,
                        subscription=subscription,
                        prefer_subscribe_data=PREFER_SUBSCRIBE_DATA,
                        subscribe_max_age_seconds=SUBSCRIBE_MAX_AGE_SECONDS,
                    )
                    rows.append(build_monitor_row(row))
                except Exception as exc:
                    row = build_monitor_row(snapshot_error_row(code, read_time, exc))
                    row["_error"] = str(exc)
                    rows.append(row)

            alert_count = 0
            for row in rows:
                row["竞价阶段"] = phase
                code = str(row.get("代码") or "")
                if row.get("_is_grab") and code not in grab_alerted:
                    grab_alerted.add(code)
                    write_alert(row, "竞价抢筹", f"{phase} 首次达到抢筹阈值", beep)
                    alert_count += 1

                seal_amount = to_number(row.get("封单金额(万)"))
                current_seal_amount = seal_amount if row.get("_is_sealed") and seal_amount is not None else 0.0
                seal_key = (phase, code)
                previous_seal_amount = last_seal_amount.get(seal_key)

                if previous_seal_amount is None:
                    last_seal_amount[seal_key] = current_seal_amount
                    if current_seal_amount > 0:
                        write_alert(row, "竞价封板", f"{phase} 首次达到封板阈值", beep)
                        alert_count += 1
                    continue

                delta = current_seal_amount - previous_seal_amount
                if previous_seal_amount <= 0 and current_seal_amount > 0:
                    row["封单变化(万)"] = delta
                    last_seal_amount[seal_key] = current_seal_amount
                    write_alert(row, "竞价封板", f"{phase} 从无封单到 {current_seal_amount:.2f}万", beep)
                    alert_count += 1
                elif delta >= ADD_SEAL_MIN_DELTA_WAN:
                    row["封单变化(万)"] = delta
                    last_seal_amount[seal_key] = current_seal_amount
                    write_alert(row, "竞价加封", f"{phase} 封单增加 {delta:.2f}万", beep)
                    alert_count += 1
                elif delta <= -REDUCE_SEAL_MIN_DELTA_WAN:
                    row["封单变化(万)"] = delta
                    last_seal_amount[seal_key] = current_seal_amount
                    signal = "竞价撤封" if current_seal_amount <= 0 else "竞价减封"
                    write_alert(row, signal, f"{phase} 封单减少 {abs(delta):.2f}万", beep)
                    alert_count += 1

            if print_table:
                print_monitor_table(rows)

            if max_loops > 0 and loop_count >= max_loops:
                break

            elapsed = time.time() - cycle_started
            if print_cycle_summary:
                logger.info(
                    "第{}轮完成：阶段={}，读取={}只，提醒={}条，耗时={:.2f}s",
                    loop_count,
                    phase,
                    len(rows),
                    alert_count,
                    elapsed,
                )
            sleep_seconds = max(0.0, interval - elapsed)
            if sleep_seconds == 0.0 and elapsed > interval:
                logger.warning(
                    "本轮耗时 {:.2f}s 超过目标周期 {:.2f}s，当前接口无法做到全量每 {:.0f} 秒刷新。",
                    elapsed,
                    interval,
                    interval,
                )
            time.sleep(sleep_seconds)
    finally:
        subscription.unsubscribe(tq)
        close_tq(tq)


def main() -> None:
    """程序入口：直接使用文件底部配置变量，不读取命令行参数。"""
    codes = resolve_watch_codes(WATCH_STOCK_CODES, WATCH_ALL_MAINBOARD_NON_ST, MAX_CODES_FOR_TEST)
    if LIST_UNIVERSE_ONLY:
        logger.info("股票池数量：{}\n{}", len(codes), "\n".join(codes))
        return

    monitor_auction(
        codes=codes,
        tdx_root=Path(TDX_ROOT),
        wait_for_auction=WAIT_FOR_AUCTION_WINDOW,
        max_loops=MAX_LOOPS,
        interval=POLL_INTERVAL_SECONDS,
        refresh_cache_interval=REFRESH_CACHE_INTERVAL_SECONDS,
        beep=ALERT_BEEP,
        print_table=PRINT_MONITOR_TABLE,
        print_cycle_summary=PRINT_CYCLE_SUMMARY,
    )


# ========== 运行配置 ==========

# 通达信安装目录；默认读取 config.py 中的 tdx_root，也可以改成 Path(r"D:\new_tdx64")。
TDX_ROOT = DEFAULT_TDX_ROOT

# 是否监控数据库中的全部主板、上市、非 ST 股票。
WATCH_ALL_MAINBOARD_NON_ST = True

# WATCH_ALL_MAINBOARD_NON_ST 为 False 时，使用这里配置的股票代码；可以只填纯数字。
WATCH_STOCK_CODES = [
    "603399",
    "300014",
    "601138",
    "688119",
]

# 调试用股票数量上限；0 表示不限制，填 20/100 可以先小范围测试。
MAX_CODES_FOR_TEST = 0

# 是否只打印本次股票池，不连接通达信、不进入监控循环。
LIST_UNIVERSE_ONLY = False

# 最大监控循环次数；0 表示不限制。
MAX_LOOPS = 0

# 每轮读取目标间隔秒数；全市场监控时实际耗时可能超过这个值。
POLL_INTERVAL_SECONDS = 3.0

# 是否在竞价开始前等待到 AUCTION_START。
WAIT_FOR_AUCTION_WINDOW = True

# 集合竞价开始时间。
AUCTION_START = "09:15:00"

# 第一阶段结束时间；09:15-09:20 允许撤单。
AUCTION_PHASE_1_END = "09:20:00"

# 第二阶段开始时间；09:20-09:25 不允许撤单。
AUCTION_PHASE_2_START = "09:20:00"

# 集合竞价结束时间。
AUCTION_END = "09:25:00"

# 到达 AUCTION_END 后是否自动停止监控。
STOP_AFTER_AUCTION_END = True

# 是否主动调用通达信插件 refresh_cache，竞价实时监控建议开启。
AUTO_REFRESH_CACHE = True

# refresh_cache 的最小调用间隔秒数，默认来自 config.py。
REFRESH_CACHE_INTERVAL_SECONDS = DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS

# 是否在读取前先调用 subscribe_hq 订阅实时行情。
SUBSCRIBE_HQ_BEFORE_READ = True

# subscribe_hq 后等待通达信缓存回调的秒数。
SUBSCRIBE_WARMUP_SECONDS = 2.0

# 是否优先使用 subscribe_hq 回调拿到的新数据。
PREFER_SUBSCRIBE_DATA = True

# subscribe_hq 回调数据的最大可接受年龄秒数，超过后回退到快照。
SUBSCRIBE_MAX_AGE_SECONDS = 5.0

# 竞价抢筹的最低涨幅阈值，单位是百分比。
GRAB_MIN_PCT = 2.0

# 竞价抢筹的最低竞价金额阈值，单位是万元。
GRAB_MIN_AMOUNT_WAN = 1000.0

# 竞价抢筹的买一量/卖一量最低比例。
GRAB_MIN_BUY_SELL_RATIO = 1.5

# 竞价封板的最低封单金额阈值，单位是万元。
SEAL_MIN_AMOUNT_WAN = 300.0

# 触发“竞价加封”的最低封单增加金额，单位是万元。
ADD_SEAL_MIN_DELTA_WAN = 300.0

# 触发“竞价减封/撤封”的最低封单减少金额，单位是万元。
REDUCE_SEAL_MIN_DELTA_WAN = 300.0

# 判断买一价是否贴近涨停价的允许误差，单位是元。
LIMIT_PRICE_TOLERANCE = 0.01

# 触发提醒时是否蜂鸣。
ALERT_BEEP = True

# 是否每轮打印监控表格；全市场时建议 False，避免日志过多。
PRINT_MONITOR_TABLE = False

# 是否每轮打印读取数量、提醒数量、耗时等摘要。
PRINT_CYCLE_SUMMARY = True


if __name__ == "__main__":
    main()
