"""通达信数据读取测试脚本。

这个文件刻意做成“单文件可运行”的测试脚本，方便直接在 PyCharm 里运行：
- 不写入、不修改通达信安装目录下的行情或配置文件；
- 本地 K 线读取只读 vipdoc 下的 .day/.lc* 文件；
- 实时快照通过通达信 PYPlugins/user/tqcenter.py 读取，适合交易时间监控一批股票。

注意：实时快照来自通达信客户端/插件侧缓存。客户端没有订阅、没有刷新到某只股票时，
Python 读到的也可能是旧数据，所以脚本提供 refresh_cache 调用来尽量推动缓存刷新。
"""

import json
import re
import struct
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from loguru import logger


SCRIPT_DIR = Path(__file__).resolve().parent

# 脚本可能放在项目根目录，也可能放在“实时监控”子目录。
# 数据库配置在项目根目录 config.py 下，这里自动兼容脚本位于“实时监控”子目录的情况。
PROJECT_ROOT = SCRIPT_DIR if (SCRIPT_DIR / "data").exists() else SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.tdx_util import (
    DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS,
    DEFAULT_TDX_ROOT,
    TdxCacheRefresher,
    TdxQuoteSubscription,
    close_tq,
    load_tq,
    read_tdx_snapshot_row,
)

# 通达信本地二进制行情文件的固定记录长度。
DAY_RECORD_SIZE = 32
MINUTE_RECORD_SIZE = 32

# 股票名称缓存只在本进程内使用，避免每一轮实时快照都访问数据库/本地配置文件。
STOCK_NAME_CACHE: Optional[Dict[str, str]] = None
TDX_INDEX_NAME_CACHE: Optional[Dict[str, str]] = None

# snapshot/alert 输出表的固定列顺序。
# 有些字段不是所有通达信版本都会返回；缺失时打印 "--"，不影响其它字段读取。
SNAPSHOT_COLUMNS = [
    "读取时间",
    "代码",
    "名称",
    "状态",
    "ErrorId",
    "最新价",
    "最新涨幅",
    "开盘价",
    "均价",
    "昨收价",
    "最高价",
    "最低价",
    "竞价涨幅",
    "成交额(万)",
    "竞价金额(万)",
    "竞价未匹配金额(万)",
]
PERCENT_COLUMNS = {"最新涨幅", "竞价涨幅"}

# 通达信 Python 插件不同版本、不同行情源返回的字段名不完全一致。
# 这里把同一个含义的英文名、拼音名、中文名都放到一组，读取时会逐个匹配。
SNAPSHOT_FIELD_ALIASES = {
    "code": ["Code", "StockCode", "StockID", "证券代码", "代码", "股票代码"],
    "name": ["Name", "StockName", "SecName", "证券名称", "名称", "股票名称"],
    "open": ["Open", "OpenPrice", "JinKai", "今开", "开盘", "开盘价"],
    "latest": ["Price", "Now", "Last", "LastPrice", "Close", "NewPrice", "ZuiXinJia", "最新", "最新价", "现价", "当前价"],
    "pre_close": ["PreClose", "PreClosePrice", "LastClose", "YClose", "YesterdayClose", "ZuoShou", "昨收", "昨收价"],
    "avg_price": ["Average", "AveragePrice", "AvgPrice", "Avg", "JunJia", "均价", "平均价"],
    "high": ["Max", "High", "HighPrice", "最高", "最高价"],
    "low": ["Min", "Low", "LowPrice", "最低", "最低价"],
    "before_5_min": ["Before5MinNow", "5分钟前价"],
    "now_volume": ["NowVol", "现手", "现量"],
    "volume": ["Volume", "Vol", "TotalVolume", "ChengJiaoLiang", "成交量", "总成交量"],
    "amount": ["Amount", "TotalAmount", "Turnover", "Money", "ChengJiaoE", "成交额", "总成交额"],
    "auction_amount": [
        "AuctionAmount",
        "CallAuctionAmount",
        "OpenAuctionAmount",
        "JingJiaAmount",
        "JingJiaJinE",
        "竞价金额",
        "集合竞价金额",
        "竞价成交额",
    ],
    "auction_pct": [
        "AuctionPct",
        "AuctionChangePct",
        "CallAuctionPct",
        "JingJiaZhangFu",
        "竞价涨幅",
        "集合竞价涨幅",
    ],
    "unmatched_amount": [
        "UnmatchedAmount",
        "UnmatchAmount",
        "AuctionUnmatchedAmount",
        "WeiPiPeiJinE",
        "未匹配金额",
        "竞价未匹配金额",
        "集合竞价未匹配金额",
    ],
    "unmatched_volume": [
        "UnmatchedVolume",
        "UnmatchVolume",
        "UnmatchedVol",
        "UnmatchVol",
        "WeiPiPeiLiang",
        "未匹配量",
        "未匹配数量",
        "竞价未匹配量",
    ],
    "buy_volume_1": ["Buyv", "BuyVol", "BuyVolume", "BidVolume", "买量", "买盘量", "委买量"],
    "sell_volume_1": ["Sellv", "SellVol", "SellVolume", "AskVolume", "卖量", "卖盘量", "委卖量"],
    "inside": ["Inside", "内盘"],
    "outside": ["Outside", "外盘"],
    "tick_diff": ["TickDiff", "价差", "跳动差值"],
}


@dataclass(frozen=True)
class StockCode:
    """统一保存股票代码的三种常用写法。"""

    code: str
    market: str

    @property
    def tdx_prefix(self) -> str:
        """通达信 vipdoc 目录使用小写市场前缀，如 sh/sz/bj。"""
        return self.market.lower()

    @property
    def tq_code(self) -> str:
        """通达信插件实时接口使用 603399.SH 这种后缀格式。"""
        return f"{self.code}.{self.market}"

    @property
    def tdx_name(self) -> str:
        """通达信本地文件名使用 sh603399 这种前缀格式。"""
        return f"{self.tdx_prefix}{self.code}"


def normalize_stock_code(raw: str) -> StockCode:
    """把用户输入的代码统一成 StockCode。

    支持：
    - 603399
    - 603399.SH
    - SH603399
    - 603399-SH / 603399_SH
    - 880652（通达信板块/概念指数，自动识别为 880652.SH）

    纯数字时自动推断市场，便于 PyCharm 配置里只维护 6 位代码。
    """
    value = raw.strip().upper().replace("_", ".")
    value = value.replace("-", ".")

    prefix_match = re.fullmatch(r"(SH|SZ|BJ)(\d{6})", value)
    if prefix_match:
        return StockCode(code=prefix_match.group(2), market=prefix_match.group(1))

    suffix_match = re.fullmatch(r"(\d{6})\.(SH|SZ|BJ)", value)
    if suffix_match:
        return StockCode(code=suffix_match.group(1), market=suffix_match.group(2))

    bare_match = re.fullmatch(r"\d{6}", value)
    if not bare_match:
        raise ValueError(f"Unsupported stock code format: {raw}")

    code = value
    if code.startswith("88"):
        # 通达信板块/概念指数通常是 88xxxx，本地 K 线在 vipdoc/sh 下。
        market = "SH"
    elif code.startswith(("6", "5", "9")):
        market = "SH"
    elif code.startswith(("4", "8")):
        market = "BJ"
    else:
        market = "SZ"
    return StockCode(code=code, market=market)


def daily_path(tdx_root: Path, stock: StockCode) -> Path:
    """返回某只股票通达信日线 .day 文件路径。"""
    return tdx_root / "vipdoc" / stock.tdx_prefix / "lday" / f"{stock.tdx_name}.day"


def minute_paths(tdx_root: Path, stock: StockCode, period: str) -> List[Path]:
    """返回某只股票指定周期的分钟线候选路径。

    不同通达信版本或设置下，1 分钟/5 分钟数据可能落在 minline 或 fzline。
    这里返回候选路径，读取时选择第一个真实存在的文件。
    """
    period = period.lower()
    period_map = {
        "1m": [("minline", ".lc1"), ("fzline", ".lc1")],
        "5m": [("fzline", ".lc5"), ("minline", ".lc5")],
        "15m": [("fzline", ".lc15"), ("minline", ".lc15")],
        "30m": [("fzline", ".lc30"), ("minline", ".lc30")],
        "60m": [("fzline", ".lc60"), ("minline", ".lc60")],
    }
    if period not in period_map:
        raise ValueError(f"Unsupported minute period: {period}")

    return [
        tdx_root / "vipdoc" / stock.tdx_prefix / folder / f"{stock.tdx_name}{suffix}"
        for folder, suffix in period_map[period]
    ]


def zst_cache_path(tdx_root: Path, stock: StockCode) -> Path:
    """返回分时/竞价缓存候选路径，仅用于 probe/watch_files 观察是否更新。"""
    return tdx_root / "T0002" / "zst_cache" / f"{stock.tdx_name}.auc2"


def read_tail_records(path: Path, record_size: int, tail: int) -> List[bytes]:
    """从二进制行情文件尾部读取最近 tail 条记录。

    通达信 .day/.lc* 文件是固定长度记录，尾部就是最新数据。
    如果文件大小不是记录长度的整数倍，只读取对齐部分，避免半条记录解析失败。
    """
    if not path.exists():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    aligned_size = size - (size % record_size)
    if aligned_size <= 0:
        return []
    count = min(tail, aligned_size // record_size)
    offset = aligned_size - count * record_size
    with path.open("rb") as file:
        file.seek(offset)
        data = file.read(count * record_size)
    return [data[index : index + record_size] for index in range(0, len(data), record_size)]


def parse_day_record(raw: bytes, stock: StockCode) -> Dict[str, Any]:
    """解析通达信日线 .day 的单条 32 字节记录。"""
    date, open_, high, low, close, amount, volume, reserved = struct.unpack("<IIIIIfII", raw)
    return {
        "stock": stock.tq_code,
        "date": str(date),
        "open": open_ / 100,
        "high": high / 100,
        "low": low / 100,
        "close": close / 100,
        "amount": amount,
        "volume": volume,
        "reserved": reserved,
    }


def decode_minute_date(raw_date: int) -> str:
    """解码通达信分钟线日期字段。"""
    year = raw_date // 2048 + 2004
    month = (raw_date % 2048) // 100
    day = (raw_date % 2048) % 100
    return f"{year:04d}{month:02d}{day:02d}"


def decode_minute_time(raw_minute: int) -> str:
    """解码通达信分钟线分钟数字段。"""
    hour = raw_minute // 60
    minute = raw_minute % 60
    return f"{hour:02d}:{minute:02d}"


def parse_minute_record(raw: bytes, stock: StockCode) -> Dict[str, Any]:
    """解析通达信分钟线 .lc* 的单条 32 字节记录。"""
    raw_date, raw_minute, open_, high, low, close, amount, volume, reserved = struct.unpack(
        "<HHfffffII", raw
    )
    return {
        "stock": stock.tq_code,
        "date": decode_minute_date(raw_date),
        "time": decode_minute_time(raw_minute),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "amount": amount,
        "volume": volume,
        "reserved": reserved,
    }


def print_json(data: Any) -> None:
    """统一按中文友好的 JSON 格式打印调试结果。"""
    logger.info(json.dumps(data, ensure_ascii=False, default=str))


def build_stock_name_cache_from_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """把 stock_basic 行数据转成按 ts_code 和纯数字代码都能查的缓存。"""
    cache: Dict[str, str] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        if ts_code:
            cache[ts_code] = name
        if symbol and symbol.isdigit():
            cache[symbol.zfill(6)] = name
        elif symbol:
            cache[symbol] = name
    return cache


def load_stock_name_cache_from_db() -> Dict[str, str]:
    """从项目 config.py 配置的 MySQL stock_basic 表读取股票名称。

    失败时返回空字典，名称列会显示为空。
    """
    try:
        import pymysql
        import config

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
                cursor.execute("SELECT ts_code, symbol, name FROM stock_basic")
                return build_stock_name_cache_from_rows(cursor.fetchall())
        finally:
            connection.close()
    except Exception as exc:
        logger.warning("读取数据库股票名称失败：{}", exc)
        return {}


def load_stock_name_cache() -> Dict[str, str]:
    """按 STOCK_NAME_SOURCE 加载并缓存股票名称。"""
    global STOCK_NAME_CACHE
    if STOCK_NAME_CACHE is not None:
        return STOCK_NAME_CACHE

    cache: Dict[str, str] = {}
    if STOCK_NAME_SOURCE == "db":
        cache.update(load_stock_name_cache_from_db())
    STOCK_NAME_CACHE = cache
    return cache


def load_tdx_index_name_cache(tdx_root: Path = DEFAULT_TDX_ROOT) -> Dict[str, str]:
    """从通达信本地板块指数配置中读取 88xxxx 名称。

    例如 tdxzs.cfg 中常见行格式：
    创新药|880652|4|2|0|创新药
    """
    global TDX_INDEX_NAME_CACHE
    if TDX_INDEX_NAME_CACHE is not None:
        return TDX_INDEX_NAME_CACHE

    cache: Dict[str, str] = {}
    candidate_files = [
        tdx_root / "T0002" / "hq_cache" / "tdxzs.cfg",
        tdx_root / "T0002" / "hq_cache" / "tdxzs3.cfg",
    ]
    for path in candidate_files:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="gbk", errors="ignore") as file:
                for line in file:
                    parts = [part.strip() for part in line.split("|")]
                    if len(parts) >= 2 and re.fullmatch(r"88\d{4}", parts[1]) and parts[0]:
                        cache[parts[1]] = parts[0]
                        cache[f"{parts[1]}.SH"] = parts[0]
        except Exception as exc:
            logger.warning("读取通达信板块指数名称失败：{}，文件：{}", exc, path)

    TDX_INDEX_NAME_CACHE = cache
    return cache


def lookup_stock_name(code: str) -> str:
    """按实时接口代码或纯数字代码查股票名称，查不到返回空字符串。"""
    names = load_stock_name_cache()
    index_names = load_tdx_index_name_cache()
    normalized = normalize_stock_code(code)
    return (
        names.get(normalized.tq_code)
        or names.get(normalized.code)
        or index_names.get(normalized.tq_code)
        or index_names.get(normalized.code)
        or ""
    )



def normalize_field_name(value: Any) -> str:
    """把字段名标准化，减少大小写、空格、下划线和中文括号差异的影响。"""
    return re.sub(r"[\s_\-./()（）:：]+", "", str(value)).lower()


def get_snapshot_record(snapshot_data: Any) -> Dict[str, Any]:
    """从通达信快照返回值里取真正的行情字段字典。

    有的版本直接返回字段字典，有的版本包在 Data/Result 里。
    """
    if not isinstance(snapshot_data, dict):
        return {}

    for key in ("Data", "data", "Result", "result"):
        value = snapshot_data.get(key)
        if isinstance(value, list):
            return value[0] if value and isinstance(value[0], dict) else {}
        if isinstance(value, dict):
            return value
    return snapshot_data


def find_field(record: Dict[str, Any], field_key: str) -> Any:
    """按 SNAPSHOT_FIELD_ALIASES 从快照记录里查一个语义字段。"""
    aliases = SNAPSHOT_FIELD_ALIASES.get(field_key, [])
    for alias in aliases:
        if alias in record:
            return record[alias]

    normalized_record = {normalize_field_name(key): value for key, value in record.items()}
    for alias in aliases:
        value = normalized_record.get(normalize_field_name(alias))
        if value is not None:
            return value
    return None


def to_number(value: Any) -> Optional[float]:
    """把通达信返回的数字、字符串、百分号、万/亿单位统一转成 float。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text in {"--", "-", "None", "null", "NULL"}:
        return None

    multiplier = 1.0
    if text.endswith("%"):
        text = text[:-1]
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]

    text = text.replace(",", "").strip()
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def round_number(value: Optional[float], digits: int = 3) -> Optional[float]:
    """安全四舍五入；None 保持 None，便于表格打印成 --。"""
    if value is None:
        return None
    return round(value, digits)


def is_auction_time(now: datetime) -> bool:
    """判断是否处于 A 股集合竞价相关时间段。"""
    hhmmss = now.strftime("%H:%M:%S")
    return "09:15:00" <= hhmmss <= "09:30:00"


def derive_average_price(amount: Optional[float], volume: Optional[float], ref_price: Optional[float]) -> Optional[float]:
    """在接口没有直接给均价时，用成交额和成交量估算均价。

    通达信不同字段口径里，成交额可能是元或万元，成交量可能是股或手。
    这里计算多个候选值，再选最接近最新价的那个，尽量避免单位误判。
    """
    if not amount or not volume or amount <= 0 or volume <= 0:
        return None

    candidates = [
        amount / volume,
        amount / (volume * 100),
        amount * 10000 / volume,
        amount * 10000 / (volume * 100),
    ]
    candidates = [item for item in candidates if 0 < item < 100000]
    if not candidates:
        return None
    if ref_price and ref_price > 0:
        return min(candidates, key=lambda item: abs(item - ref_price))
    return candidates[0]


def derive_pct(price: Optional[float], base: Optional[float]) -> Optional[float]:
    """根据价格和基准价计算涨幅百分比。"""
    if price is None or base is None or base == 0:
        return None
    return (price / base - 1) * 100


def derive_unmatched_amount(unmatched_volume: Optional[float], latest_price: Optional[float]) -> Optional[float]:
    """用未匹配量和最新价估算未匹配金额。"""
    if unmatched_volume is None or latest_price is None:
        return None
    return unmatched_volume * latest_price


def first_number(value: Any) -> Optional[float]:
    """取列表/元组中的第一个数；非列表时直接按数值解析。"""
    if isinstance(value, (list, tuple)) and value:
        return to_number(value[0])
    return to_number(value)


def level_value(value: Any, index: int) -> Optional[float]:
    """从五档买卖价/量数组中取指定档位的数值。"""
    if isinstance(value, (list, tuple)) and len(value) > index:
        return to_number(value[index])
    if index == 0:
        return to_number(value)
    return None


def five_level_amount_wan(prices: Any, volumes: Any) -> Optional[float]:
    """计算五档盘口金额，输出万元。

    通达信五档量通常是“手”，所以金额 = 价格 * 手数 * 100 股 / 10000。
    如果只有买一/卖一单值，也会按第一档计算。
    """
    total = 0.0
    has_value = False
    for index in range(5):
        price = level_value(prices, index)
        volume_lots = level_value(volumes, index)
        if price is None or volume_lots is None:
            continue
        total += price * volume_lots / 100
        has_value = True
    return total if has_value else None


def derive_auction_unmatched_amount(
    buy_volume_1: Optional[float],
    sell_volume_1: Optional[float],
    auction_price: Optional[float],
) -> Optional[float]:
    """用买一量/卖一量差额估算竞价未匹配金额，输出万元口径。"""
    if buy_volume_1 is None or sell_volume_1 is None or auction_price is None:
        return None
    # 通达信快照里的买卖量通常是“手”，Amount 是“万元”。这里输出万元口径。
    return abs(buy_volume_1 - sell_volume_1) * auction_price / 100


def extract_snapshot_row(code: str, snapshot_data: Any, read_time: datetime) -> Dict[str, Any]:
    """把一次实时快照整理成表格行。

    优先使用通达信接口直接返回的字段；如果某些字段缺失，就用已有字段推导：
    - 最新涨幅 = 最新价 / 昨收价 - 1
    - 均价 = 成交额 / 成交量，并自动尝试不同单位口径
    - 竞价涨幅 = 集合竞价阶段按最新价算，非竞价阶段按开盘价算
    - 竞价未匹配金额 = 未匹配量或买卖一档量差估算
    """
    record = get_snapshot_record(snapshot_data)
    error = snapshot_data.get("Error") if isinstance(snapshot_data, dict) else None
    error_id = snapshot_data.get("ErrorId") if isinstance(snapshot_data, dict) else None

    latest = to_number(find_field(record, "latest"))
    open_price = to_number(find_field(record, "open"))
    pre_close = to_number(find_field(record, "pre_close"))
    high = to_number(find_field(record, "high"))
    low = to_number(find_field(record, "low"))
    before_5_min = to_number(find_field(record, "before_5_min"))
    amount = to_number(find_field(record, "amount"))
    volume = to_number(find_field(record, "volume"))
    now_volume = to_number(find_field(record, "now_volume"))
    inside = to_number(find_field(record, "inside"))
    outside = to_number(find_field(record, "outside"))
    tick_diff = to_number(find_field(record, "tick_diff"))
    avg_price = to_number(find_field(record, "avg_price"))
    auction_amount = to_number(find_field(record, "auction_amount"))
    auction_pct = to_number(find_field(record, "auction_pct"))
    unmatched_amount = to_number(find_field(record, "unmatched_amount"))
    unmatched_volume = to_number(find_field(record, "unmatched_volume"))
    buy_prices = record.get("Buyp")
    buy_volumes = record.get("Buyv")
    sell_prices = record.get("Sellp")
    sell_volumes = record.get("Sellv")
    buy_volume_1 = first_number(buy_volumes)
    sell_volume_1 = first_number(sell_volumes)
    five_buy_amount = five_level_amount_wan(buy_prices, buy_volumes)
    five_sell_amount = five_level_amount_wan(sell_prices, sell_volumes)
    five_amount_ratio = (
        five_buy_amount / five_sell_amount
        if five_buy_amount is not None and five_sell_amount is not None and five_sell_amount > 0
        else None
    )

    # 最新涨幅通常不是所有接口都会给，直接按昨收价推导更稳定。
    latest_pct = derive_pct(latest, pre_close)
    if avg_price is None:
        avg_price = derive_average_price(amount, volume, latest)
    if auction_amount is None and is_auction_time(read_time):
        # 集合竞价阶段如果没有单独的竞价金额字段，先用当前成交额兜底。
        auction_amount = amount
    if auction_pct is None:
        # 竞价阶段用最新价近似开盘竞价价；盘中则用开盘价作为竞价结果价。
        auction_price = latest if is_auction_time(read_time) else open_price
        auction_pct = derive_pct(auction_price, pre_close)
    if unmatched_amount is None:
        unmatched_amount = derive_unmatched_amount(unmatched_volume, latest)
    if unmatched_amount is None and is_auction_time(read_time):
        # 买一量和卖一量差额可近似看作未匹配量，金额统一折算为万元。
        auction_price = latest if latest is not None else open_price
        unmatched_amount = derive_auction_unmatched_amount(buy_volume_1, sell_volume_1, auction_price)

    status = "OK" if error_id in (None, "0", 0) and record else f"ERR:{error or error_id or 'empty'}"

    name = find_field(record, "name") or lookup_stock_name(code)

    row = {
        "读取时间": read_time.strftime("%Y-%m-%d %H:%M:%S"),
        "代码": find_field(record, "code") or code,
        "名称": name,
        "状态": status,
        "ErrorId": error_id,
        "开盘价": round_number(open_price),
        "最新价": round_number(latest),
        "最新涨幅": round_number(latest_pct, 3),
        "均价": round_number(avg_price),
        "昨收价": round_number(pre_close),
        "最高价": round_number(high),
        "最低价": round_number(low),
        "5分钟前价": round_number(before_5_min),
        "竞价涨幅": round_number(auction_pct, 3),
        "成交量(手)": round_number(volume, 0),
        "成交额(万)": round_number(amount, 2),
        "现手": round_number(now_volume, 0),
        "竞价金额(万)": round_number(auction_amount, 2),
        "竞价未匹配金额(万)": round_number(unmatched_amount, 2),
        "内盘": round_number(inside, 0),
        "外盘": round_number(outside, 0),
        "价差": round_number(tick_diff),
        "InOutFlag": record.get("InOutFlag"),
        "ItemNum": record.get("ItemNum"),
        "CJBS": record.get("CJBS"),
        "Jjjz": record.get("Jjjz"),
        "ZAFPre3": record.get("ZAFPre3"),
        "Zangsu": record.get("Zangsu"),
        "xsflag": record.get("xsflag"),
        "RefreshNum": record.get("RefreshNum"),
        "五档总买金额(万)": round_number(five_buy_amount, 2),
        "五档总卖金额(万)": round_number(five_sell_amount, 2),
        "五档买卖金额比": round_number(five_amount_ratio, 3),
        "_raw": snapshot_data,
        "_raw_keys": list(record.keys()),
    }
    labels = ["一", "二", "三", "四", "五"]
    for index, label in enumerate(labels):
        row[f"买{label}价"] = round_number(level_value(buy_prices, index))
        row[f"买{label}量"] = round_number(level_value(buy_volumes, index), 0)
        row[f"卖{label}价"] = round_number(level_value(sell_prices, index))
        row[f"卖{label}量"] = round_number(level_value(sell_volumes, index), 0)
    return row


def format_cell(column: str, value: Any) -> str:
    """把表格单元格格式化为适合命令行阅读的文本。"""
    if value is None or value == "":
        return "--"
    if isinstance(value, float):
        if column in PERCENT_COLUMNS:
            return f"{value:.3f}%"
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if column in PERCENT_COLUMNS:
        numeric_value = to_number(value)
        if numeric_value is not None:
            return f"{numeric_value:.3f}%"
    return str(value)


def display_width(value: Any) -> int:
    """计算字符串在等宽终端中的显示宽度。

    Python 的 len() 只算字符数，但中文、全角括号等在终端里通常占 2 格。
    表格列宽必须按显示宽度计算，否则中文表头会和数据错位。
    """
    width = 0
    for char in str(value):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def ljust_display(value: Any, width: int) -> str:
    """按终端显示宽度右侧补空格。"""
    text = str(value)
    return text + " " * max(0, width - display_width(text))


def build_text_table(
    columns: List[str],
    rows: List[Dict[str, Any]],
    formatter: Callable[[str, Any], str],
) -> str:
    """构建按中文显示宽度对齐的文本表格。"""
    widths = {
        column: max(display_width(column), *(display_width(formatter(column, row.get(column))) for row in rows))
        for column in columns
    }
    lines = [
        " | ".join(ljust_display(column, widths[column]) for column in columns),
        "-+-".join("-" * widths[column] for column in columns),
    ]
    for row in rows:
        lines.append(
            " | ".join(ljust_display(formatter(column, row.get(column)), widths[column]) for column in columns)
        )
    return "\n".join(lines)


def print_snapshot_table(rows: List[Dict[str, Any]]) -> None:
    """按固定列宽打印实时快照表。"""
    if not rows:
        return
    logger.info("\n{}", build_text_table(SNAPSHOT_COLUMNS, rows, format_cell))


def crossed_above(
    previous_price: Optional[float],
    current_price: Optional[float],
    previous_level: Optional[float],
    current_level: Optional[float],
) -> bool:
    """判断价格是否从阈值下方/等于阈值，穿越到阈值上方。"""
    if current_price is None or current_level is None:
        return False
    if previous_price is None or previous_level is None:
        return False
    return previous_price <= previous_level and current_price > current_level


def can_emit_alert(
    alert_history: Dict[tuple, float],
    stock_code: str,
    signal: str,
    now_ts: float,
    repeat_after_seconds: int,
) -> bool:
    """控制同一股票同一信号的重复提醒频率。"""
    key = (stock_code, signal)
    previous_alert_at = alert_history.get(key)
    if previous_alert_at is None:
        alert_history[key] = now_ts
        return True
    if repeat_after_seconds > 0 and now_ts - previous_alert_at >= repeat_after_seconds:
        alert_history[key] = now_ts
        return True
    return False


def emit_alert(message: str, beep: bool = True) -> None:
    """输出提醒，并在 Windows 下尝试发出提示音。"""
    logger.warning(message)
    if not beep:
        return
    try:
        import winsound

        winsound.Beep(1200, 300)
    except Exception:
        pass


def build_alert_message(row: Dict[str, Any], signal: str, level_name: str, level: float) -> str:
    """生成统一的突破提醒文本。"""
    latest = row.get("最新价")
    latest_pct = format_cell("最新涨幅", row.get("最新涨幅"))
    return (
        f"ALERT {row.get('读取时间')} {row.get('代码')} {row.get('名称')} "
        f"{signal}: 最新价 {format_cell('最新价', latest)} > {level_name} {format_cell(level_name, level)} "
        f"最新涨幅 {latest_pct}"
    )


def check_alerts(
    rows: List[Dict[str, Any]],
    previous_rows: Dict[str, Dict[str, Any]],
    alert_history: Dict[tuple, float],
    break_open: bool,
    break_average: bool,
    repeat_after_seconds: int,
    beep: bool,
) -> None:
    """检查所有股票是否触发开盘价/分时均价突破提醒。

    第一轮只建立 previous_rows 基准，不触发提醒；之后每轮都和上一轮快照比较。
    这样可以避免脚本刚启动时因为价格本来已经在阈值上方而误报。
    """
    now_ts = time.time()
    for row in rows:
        if row.get("状态") != "OK":
            continue
        stock_code = str(row.get("代码") or "")
        previous = previous_rows.get(stock_code)
        current_price = to_number(row.get("最新价"))
        previous_price = to_number(previous.get("最新价")) if previous else None

        # 开盘价突破：上一轮最新价 <= 上一轮开盘价，且本轮最新价 > 本轮开盘价。
        if break_open:
            current_open = to_number(row.get("开盘价"))
            previous_open = to_number(previous.get("开盘价")) if previous else None
            if crossed_above(previous_price, current_price, previous_open, current_open):
                signal = "突破开盘价"
                if can_emit_alert(alert_history, stock_code, signal, now_ts, repeat_after_seconds):
                    emit_alert(build_alert_message(row, signal, "开盘价", current_open), beep)

        # 分时均价突破：用同样的穿越逻辑，避免价格一直在均价上方时重复提醒。
        if break_average:
            current_average = to_number(row.get("均价"))
            previous_average = to_number(previous.get("均价")) if previous else None
            if crossed_above(previous_price, current_price, previous_average, current_average):
                signal = "突破分时均价"
                if can_emit_alert(alert_history, stock_code, signal, now_ts, repeat_after_seconds):
                    emit_alert(build_alert_message(row, signal, "均价", current_average), beep)

        # 每轮结束后更新基准，下一轮才能判断“刚刚突破”。
        previous_rows[stock_code] = row


def read_day(tdx_root: Path, code: str, tail: int) -> None:
    """读取本地日线文件尾部数据，适合验证通达信本地文件解析是否正确。"""
    stock = normalize_stock_code(code)
    path = daily_path(tdx_root, stock)
    records = [parse_day_record(raw, stock) for raw in read_tail_records(path, DAY_RECORD_SIZE, tail)]
    print_json({"source": str(path), "records": records})


def read_minute(tdx_root: Path, code: str, period: str, tail: int) -> None:
    """读取本地分钟线文件尾部数据，适合验证分钟 K 文件是否在更新。"""
    stock = normalize_stock_code(code)
    candidates = minute_paths(tdx_root, stock, period)
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError("No minute file found. Tried: " + ", ".join(str(item) for item in candidates))
    records = [
        parse_minute_record(raw, stock) for raw in read_tail_records(path, MINUTE_RECORD_SIZE, tail)
    ]
    print_json({"source": str(path), "records": records})


def snapshot_error_row(code: str, read_time: datetime, exc: Exception) -> Dict[str, Any]:
    """生成统一的快照读取失败行。"""
    row = {column: None for column in SNAPSHOT_COLUMNS}
    row.update(
        {
            "读取时间": read_time.strftime("%Y-%m-%d %H:%M:%S"),
            "代码": code,
            "名称": lookup_stock_name(code),
            "状态": f"ERR:{exc}",
        }
    )
    return row


def is_effective_quote_row(row: Dict[str, Any]) -> bool:
    """判断一行行情是否有可用于监控的有效实时字段。

    订阅回调偶尔会只带 Code，解析后状态仍可能是 OK，但价格、盘口、成交字段全是空。
    这种行不能用于监控，也不能覆盖上一条有效快照。
    """
    if row.get("状态") != "OK":
        return False

    price_fields = [
        "最新价",
        "开盘价",
        "最高价",
        "最低价",
        "买一价",
        "卖一价",
    ]
    volume_fields = [
        "成交量(手)",
        "成交额(万)",
        "现手",
        "买一量",
        "卖一量",
        "内盘",
        "外盘",
    ]
    return any((to_number(row.get(field)) or 0) > 0 for field in price_fields + volume_fields)


def read_snapshot_row_prefer_subscription(
    tq: Any,
    code: str,
    read_time: datetime,
    subscription: Optional[TdxQuoteSubscription],
    prefer_subscribe_data: bool,
    subscribe_max_age_seconds: Optional[float] = None,
    print_raw: bool = False,
) -> tuple[Dict[str, Any], bool]:
    """读取一行实时快照，优先使用 subscribe_hq 推送数据。

    subscribe_hq 的回调数据通常比 get_market_snapshot 的报表缓存更及时。
    如果还没收到该股票回调，就退回原来的 get_market_snapshot。
    返回值第二项表示本次是否已经打印过原始字段。
    """
    if prefer_subscribe_data and subscription is not None:
        subscribed_data = subscription.get_latest(code, max_age_seconds=subscribe_max_age_seconds)
        if subscribed_data:
            subscribed_row = extract_snapshot_row(code, subscribed_data, read_time)
            if not is_effective_quote_row(subscribed_row):
                subscribed_row = None
            if subscribed_row is not None:
                if print_raw:
                    print_json(
                        {
                            "raw_snapshot_source": "subscribe_hq",
                            "raw_snapshot_sample": subscribed_data,
                            "raw_keys": list(get_snapshot_record(subscribed_data).keys()),
                        }
                    )
                return subscribed_row, print_raw

    fallback_row = read_tdx_snapshot_row(
        tq,
        code,
        extract_snapshot_row,
        read_time,
        print_raw=print_raw,
        record_getter=get_snapshot_record,
    )
    if print_raw:
        return fallback_row, True
    return fallback_row, False


def snapshot(
    tdx_root: Path,
    codes: Iterable[str],
    watch: bool,
    interval: float,
    max_loops: int = 0,
    print_raw_first: bool = True,
    auto_refresh_cache: bool = True,
    refresh_cache_interval: float = DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS,
    print_refresh_result: bool = False,
    force_refresh_every_loop: bool = False,
    subscribe_hq: bool = True,
    subscribe_warmup_seconds: float = 2.0,
    prefer_subscribe_data: bool = True,
    subscribe_max_age_seconds: Optional[float] = 5.0,
    print_subscribe_result: bool = False,
) -> None:
    """读取一批股票实时快照，并按表格输出。

    watch=False 时只读一次；watch=True 时按 interval 循环读取。
    """
    normalized = [normalize_stock_code(code).tq_code for code in codes]
    tq = load_tq(tdx_root, Path(__file__).resolve())
    subscription = TdxQuoteSubscription(
        enabled=subscribe_hq,
        warmup_seconds=subscribe_warmup_seconds,
        print_result=print_subscribe_result,
    )
    subscription.subscribe(tq, normalized)
    raw_printed = False
    loop_count = 0
    cache_refresher = TdxCacheRefresher(auto_refresh_cache, refresh_cache_interval, print_refresh_result)
    try:
        while True:
            loop_count += 1
            if force_refresh_every_loop:
                cache_refresher.refresh_now(tq)
            else:
                cache_refresher.maybe_refresh(tq)
            rows = []
            for code in normalized:
                read_time = datetime.now()
                try:
                    print_raw = print_raw_first and not raw_printed
                    row, printed_raw = read_snapshot_row_prefer_subscription(
                        tq=tq,
                        code=code,
                        read_time=read_time,
                        subscription=subscription,
                        prefer_subscribe_data=prefer_subscribe_data,
                        subscribe_max_age_seconds=subscribe_max_age_seconds,
                        print_raw=print_raw,
                    )
                    rows.append(row)
                    raw_printed = raw_printed or printed_raw
                except Exception as exc:
                    rows.append(snapshot_error_row(code, read_time, exc))
            print_snapshot_table(rows)
            if not watch:
                break
            if max_loops > 0 and loop_count >= max_loops:
                break
            time.sleep(interval)
    finally:
        subscription.unsubscribe(tq)
        close_tq(tq)


def alert_monitor(
    tdx_root: Path,
    codes: Iterable[str],
    interval: float,
    max_loops: int = 0,
    auto_refresh_cache: bool = True,
    refresh_cache_interval: float = DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS,
    print_refresh_result: bool = False,
    break_open: bool = True,
    break_average: bool = True,
    repeat_after_seconds: int = 0,
    beep: bool = True,
    print_table: bool = True,
    subscribe_hq: bool = True,
    subscribe_warmup_seconds: float = 2.0,
    prefer_subscribe_data: bool = True,
    subscribe_max_age_seconds: Optional[float] = 5.0,
    print_subscribe_result: bool = False,
) -> None:
    """实时监控一批股票快照，并在突破开盘价/分时均价时提醒。"""
    normalized = [normalize_stock_code(code).tq_code for code in codes]
    tq = load_tq(tdx_root, Path(__file__).resolve())
    subscription = TdxQuoteSubscription(
        enabled=subscribe_hq,
        warmup_seconds=subscribe_warmup_seconds,
        print_result=print_subscribe_result,
    )
    subscription.subscribe(tq, normalized)
    previous_rows: Dict[str, Dict[str, Any]] = {}
    # 记录已提醒过的 (股票, 信号) 和时间戳，用来做去重或限频。
    alert_history: Dict[tuple, float] = {}
    loop_count = 0
    cache_refresher = TdxCacheRefresher(auto_refresh_cache, refresh_cache_interval, print_refresh_result)
    try:
        while True:
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
                        prefer_subscribe_data=prefer_subscribe_data,
                        subscribe_max_age_seconds=subscribe_max_age_seconds,
                    )
                    rows.append(row)
                except Exception as exc:
                    rows.append(snapshot_error_row(code, read_time, exc))

            if print_table:
                print_snapshot_table(rows)

            check_alerts(
                rows=rows,
                previous_rows=previous_rows,
                alert_history=alert_history,
                break_open=break_open,
                break_average=break_average,
                repeat_after_seconds=repeat_after_seconds,
                beep=beep,
            )

            if max_loops > 0 and loop_count >= max_loops:
                break
            time.sleep(interval)
    finally:
        subscription.unsubscribe(tq)
        close_tq(tq)


def subscribe(tdx_root: Path, codes: Iterable[str], seconds: int) -> None:
    """测试通达信订阅式行情回调。

    当前主流程仍以轮询 snapshot 为主，因为轮询更容易控制字段、频率和报警逻辑。
    """
    normalized = [normalize_stock_code(code).tq_code for code in codes]
    tq = load_tq(tdx_root, Path(__file__).resolve())

    def on_data(data_str: str) -> None:
        print_json({"callback_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "event": json.loads(data_str)})

    try:
        result = tq.subscribe_hq(stock_list=normalized, callback=on_data)
        print_json({"subscribe_result": result, "stocks": normalized, "seconds": seconds})
        deadline = time.time() + seconds
        while time.time() < deadline:
            time.sleep(0.2)
    finally:
        try:
            tq.unsubscribe_hq(stock_list=normalized)
        finally:
            close_tq(tq)


def stat_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    """读取文件大小和修改时间，不读取内容，用于观察通达信缓存是否变化。"""
    if not path.exists():
        return None
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def probe(tdx_root: Path, code: str) -> None:
    """列出某只股票可能涉及的本地数据文件及其状态。"""
    stock = normalize_stock_code(code)
    files = [daily_path(tdx_root, stock), zst_cache_path(tdx_root, stock)]
    for period in ("1m", "5m", "15m", "30m", "60m"):
        files.extend(minute_paths(tdx_root, stock, period))
    print_json(
        {
            "stock": stock.tq_code,
            "files": [stat_snapshot(path) or {"path": str(path), "exists": False} for path in files],
        }
    )


def watch_files(tdx_root: Path, code: str, seconds: int, interval: float) -> None:
    """只观察本地文件大小/mtime 是否变化，用来判断客户端是否在写缓存。"""
    stock = normalize_stock_code(code)
    files = [daily_path(tdx_root, stock), zst_cache_path(tdx_root, stock)]
    for period in ("1m", "5m"):
        files.extend(minute_paths(tdx_root, stock, period))

    last: Dict[str, Optional[Dict[str, Any]]] = {}
    deadline = time.time() + seconds
    while time.time() < deadline:
        changed = []
        for path in files:
            current = stat_snapshot(path)
            key = str(path)
            if key not in last:
                last[key] = current
                changed.append(current or {"path": key, "exists": False})
            elif last[key] != current:
                last[key] = current
                changed.append(current or {"path": key, "exists": False})
        if changed:
            print_json({"watch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "changed": changed})
        time.sleep(interval)


def run_configured() -> None:
    """直接运行入口，参数全部来自文件底部的运行配置。"""
    tdx_root = Path(TDX_ROOT)
    mode = PYCHARM_RUN_MODE.lower()

    if mode == "alert":
        # 默认推荐模式：实时读快照并检查突破提醒。
        alert_monitor(
            tdx_root=tdx_root,
            codes=PYCHARM_STOCK_CODES,
            interval=PYCHARM_INTERVAL_SECONDS,
            max_loops=PYCHARM_MAX_LOOPS,
            auto_refresh_cache=PYCHARM_AUTO_REFRESH_CACHE,
            refresh_cache_interval=PYCHARM_REFRESH_CACHE_INTERVAL_SECONDS,
            print_refresh_result=PYCHARM_PRINT_REFRESH_RESULT,
            break_open=PYCHARM_ALERT_BREAK_OPEN,
            break_average=PYCHARM_ALERT_BREAK_AVERAGE,
            repeat_after_seconds=PYCHARM_ALERT_REPEAT_AFTER_SECONDS,
            beep=PYCHARM_ALERT_BEEP,
            print_table=PYCHARM_ALERT_PRINT_TABLE,
            subscribe_hq=PYCHARM_SUBSCRIBE_HQ_BEFORE_READ,
            subscribe_warmup_seconds=PYCHARM_SUBSCRIBE_WARMUP_SECONDS,
            prefer_subscribe_data=PYCHARM_PREFER_SUBSCRIBE_DATA,
            subscribe_max_age_seconds=PYCHARM_SUBSCRIBE_MAX_AGE_SECONDS,
            print_subscribe_result=PYCHARM_PRINT_SUBSCRIBE_RESULT,
        )
    elif mode == "snapshot":
        # 只想看通达信当前能返回哪些字段时，用 snapshot 更直观。
        snapshot(
            tdx_root=tdx_root,
            codes=PYCHARM_STOCK_CODES,
            watch=PYCHARM_LOOP_FOREVER,
            interval=PYCHARM_INTERVAL_SECONDS,
            max_loops=PYCHARM_MAX_LOOPS,
            print_raw_first=PYCHARM_PRINT_RAW_FIRST_SNAPSHOT,
            auto_refresh_cache=PYCHARM_AUTO_REFRESH_CACHE,
            refresh_cache_interval=PYCHARM_REFRESH_CACHE_INTERVAL_SECONDS,
            print_refresh_result=PYCHARM_PRINT_REFRESH_RESULT,
            force_refresh_every_loop=PYCHARM_SNAPSHOT_FORCE_REFRESH_EVERY_LOOP,
            subscribe_hq=PYCHARM_SUBSCRIBE_HQ_BEFORE_READ,
            subscribe_warmup_seconds=PYCHARM_SUBSCRIBE_WARMUP_SECONDS,
            prefer_subscribe_data=PYCHARM_PREFER_SUBSCRIBE_DATA,
            subscribe_max_age_seconds=PYCHARM_SUBSCRIBE_MAX_AGE_SECONDS,
            print_subscribe_result=PYCHARM_PRINT_SUBSCRIBE_RESULT,
        )
    elif mode == "day":
        # 读取本地日线文件，不依赖通达信实时接口。
        read_day(tdx_root, PYCHARM_DAY_CODE, PYCHARM_TAIL)
    elif mode == "minute":
        # 读取本地分钟线文件，不依赖通达信实时接口。
        read_minute(tdx_root, PYCHARM_MINUTE_CODE, PYCHARM_MINUTE_PERIOD, PYCHARM_TAIL)
    elif mode == "probe":
        # 查看某批股票在通达信目录中有哪些候选数据文件。
        for code in PYCHARM_STOCK_CODES:
            probe(tdx_root, code)
    elif mode == "watch_files":
        # 观察本地缓存文件是否在变化，用于排查客户端是否更新数据。
        for code in PYCHARM_STOCK_CODES:
            watch_files(tdx_root, code, PYCHARM_SUBSCRIBE_SECONDS, PYCHARM_INTERVAL_SECONDS)
    elif mode == "subscribe":
        # 测试订阅回调能力；实际监控仍建议先用 alert/snapshot 轮询。
        subscribe(tdx_root, PYCHARM_STOCK_CODES, PYCHARM_SUBSCRIBE_SECONDS)
    else:
        raise ValueError(f"Unsupported PYCHARM_RUN_MODE: {PYCHARM_RUN_MODE}")


def main() -> None:
    """程序入口：直接使用文件底部配置变量，不读取命令行参数。"""
    run_configured()


# ========== 运行配置 ==========

# 通达信安装目录；默认读取 config.py 中的 tdx_root，也可以改成 Path(r"D:\new_tdx64")。
TDX_ROOT = DEFAULT_TDX_ROOT

# 股票名称来源；"db" 从 config.py 配置的 MySQL stock_basic 读取，"none" 表示只打印代码。
STOCK_NAME_SOURCE = "db"

# 运行模式：alert/snapshot/day/minute/probe/watch_files/subscribe。
PYCHARM_RUN_MODE = "snapshot"

# snapshot/alert/subscribe/probe/watch_files 使用的股票代码；可以只填纯数字，不需要手动写 SH/SZ。
PYCHARM_STOCK_CODES = [
    "002428",
    "880652",
    "603399",
    "300014",
    "600487",
    "688119",
]

# day 模式读取的股票代码。
PYCHARM_DAY_CODE = "000001"

# minute 模式读取的股票代码。
PYCHARM_MINUTE_CODE = "000001"

# minute 模式读取的分钟周期，可选 1m/5m/15m/30m/60m。
PYCHARM_MINUTE_PERIOD = "5m"

# day/minute 模式打印最后多少条记录。
PYCHARM_TAIL = 5

# snapshot/alert/watch_files 的轮询间隔秒数。
PYCHARM_INTERVAL_SECONDS = 2.0

# snapshot 模式是否持续循环读取。
PYCHARM_LOOP_FOREVER = True

# snapshot/alert 最大循环次数；0 表示不限制。
PYCHARM_MAX_LOOPS = 0

# subscribe/watch_files 模式持续观察秒数。
PYCHARM_SUBSCRIBE_SECONDS = 60

# 第一次 snapshot 是否打印通达信接口返回的原始字段。
PYCHARM_PRINT_RAW_FIRST_SNAPSHOT = False

# snapshot 模式是否每轮读取前都强制调用 refresh_cache。
PYCHARM_SNAPSHOT_FORCE_REFRESH_EVERY_LOOP = True

# 是否主动调用通达信插件 refresh_cache，实时监控建议开启。
PYCHARM_AUTO_REFRESH_CACHE = True

# refresh_cache 的最小调用间隔秒数，默认来自 config.py。
PYCHARM_REFRESH_CACHE_INTERVAL_SECONDS = DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS

# 是否打印 refresh_cache 的返回结果。
PYCHARM_PRINT_REFRESH_RESULT = False

# 是否在读取前先调用 subscribe_hq 订阅实时行情。
PYCHARM_SUBSCRIBE_HQ_BEFORE_READ = True

# subscribe_hq 后等待通达信缓存回调的秒数。
PYCHARM_SUBSCRIBE_WARMUP_SECONDS = 2.0

# 是否优先使用 subscribe_hq 回调拿到的新数据。
PYCHARM_PREFER_SUBSCRIBE_DATA = True

# subscribe_hq 回调数据的最大可接受年龄秒数，超过后回退到快照。
PYCHARM_SUBSCRIBE_MAX_AGE_SECONDS = 5.0

# 是否打印 subscribe_hq 的返回结果。
PYCHARM_PRINT_SUBSCRIBE_RESULT = False

# alert 模式是否监控突破开盘价。
PYCHARM_ALERT_BREAK_OPEN = True

# alert 模式是否监控突破分时均价。
PYCHARM_ALERT_BREAK_AVERAGE = True

# alert 模式同一股票同一信号的重复提醒间隔秒数；0 表示只提醒一次。
PYCHARM_ALERT_REPEAT_AFTER_SECONDS = 0

# alert 模式触发信号时是否蜂鸣。
PYCHARM_ALERT_BEEP = True

# alert 模式是否打印每轮表格。
PYCHARM_ALERT_PRINT_TABLE = True


if __name__ == "__main__":
    main()
