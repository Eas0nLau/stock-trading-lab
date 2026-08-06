from datetime import datetime
from typing import Any

ALIASES = {
    "code": ("Code", "StockCode", "StockID", "证券代码", "代码", "股票代码"),
    "name": ("Name", "StockName", "SecName", "证券名称", "名称", "股票名称"),
    "open": ("Open", "OpenPrice", "JinKai", "今开", "开盘", "开盘价"),
    "latest": ("Price", "Now", "Last", "LastPrice", "Close", "NewPrice", "最新", "最新价", "现价", "当前价"),
    "pre_close": ("PreClose", "PreClosePrice", "LastClose", "YClose", "YesterdayClose", "ZuoShou", "昨收", "昨收价"),
    "avg_price": ("Average", "AveragePrice", "AvgPrice", "Avg", "JunJia", "均价", "平均价"),
    "high": ("Max", "High", "HighPrice", "最高", "最高价"),
    "low": ("Min", "Low", "LowPrice", "最低", "最低价"),
    "before_5_min": ("Before5MinNow", "5分钟前价"),
    "now_volume": ("NowVol", "现手", "现量"),
    "volume": ("Volume", "Vol", "TotalVolume", "ChengJiaoLiang", "成交量", "总成交量"),
    "amount": ("Amount", "TotalAmount", "Turnover", "Money", "ChengJiaoE", "成交额", "总成交额"),
    "auction_amount": ("AuctionAmount", "CallAuctionAmount", "OpenAuctionAmount", "JingJiaAmount", "JingJiaJinE", "竞价金额", "集合竞价金额", "竞价成交额"),
    "auction_pct": ("AuctionPct", "AuctionChangePct", "CallAuctionPct", "JingJiaZhangFu", "竞价涨幅", "集合竞价涨幅"),
    "unmatched_amount": ("UnmatchedAmount", "UnmatchAmount", "AuctionUnmatchedAmount", "WeiPiPeiJinE", "未匹配金额", "竞价未匹配金额", "集合竞价未匹配金额"),
    "unmatched_volume": ("UnmatchedVolume", "UnmatchVolume", "UnmatchedVol", "UnmatchVol", "WeiPiPeiLiang", "未匹配量", "未匹配数量", "竞价未匹配量"),
    "inside": ("Inside", "内盘"),
    "outside": ("Outside", "外盘"),
    "tick_diff": ("TickDiff", "价差", "跳动差值"),
}


def to_number(value: Any):
    if value is None or isinstance(value, bool) or value in ("", "--", "-", "None", "null", "NULL"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    multiplier = 100000000 if text.endswith("亿") else 10000 if text.endswith("万") else 1
    text = text.rstrip("亿万%").strip()
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def get_snapshot_record(payload):
    if not isinstance(payload, dict):
        return {}
    for key in ("Data", "data", "Result", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return value[0] if value and isinstance(value[0], dict) else {}
        if isinstance(value, dict):
            return value
    return payload


def _field(record, key):
    aliases = ALIASES[key]
    for alias in aliases:
        if alias in record:
            return record[alias]
    normalized = {"".join(char for char in str(name).lower() if char.isalnum()): value for name, value in record.items()}
    for alias in aliases:
        result = normalized.get("".join(char for char in alias.lower() if char.isalnum()))
        if result is not None:
            return result
    return None


def derive_pct(price, base):
    if price is None or base in (None, 0):
        return None
    return round((price / base - 1) * 100, 3)


def derive_average_price(amount, volume, ref_price):
    if not amount or not volume or amount <= 0 or volume <= 0:
        return None
    candidates = [amount / volume, amount / (volume * 100), amount * 10000 / volume, amount * 10000 / (volume * 100)]
    candidates = [value for value in candidates if 0 < value < 100000]
    return min(candidates, key=lambda value: abs(value - ref_price)) if candidates and ref_price else candidates[0] if candidates else None


def _level(value, index):
    if isinstance(value, (list, tuple)) and len(value) > index:
        return to_number(value[index])
    return to_number(value) if index == 0 else None


def _first(value):
    return _level(value, 0)


def five_level_amount_wan(prices, volumes):
    values = [(_level(prices, index), _level(volumes, index)) for index in range(5)]
    values = [price * volume / 100 for price, volume in values if price is not None and volume is not None]
    return sum(values) if values else None


def is_auction_time(read_time):
    return "09:15:00" <= read_time.strftime("%H:%M:%S") <= "09:30:00"


def derive_auction_unmatched_amount(buy_volume, sell_volume, price):
    if buy_volume is None or sell_volume is None or price is None:
        return None
    return abs(buy_volume - sell_volume) * price / 100


def extract_snapshot_row(code: str, snapshot_data: Any, read_time: datetime, name_lookup=None):
    record = get_snapshot_record(snapshot_data)
    latest = to_number(_field(record, "latest"))
    open_price = to_number(_field(record, "open"))
    pre_close = to_number(_field(record, "pre_close"))
    amount = to_number(_field(record, "amount"))
    volume = to_number(_field(record, "volume"))
    avg_price = to_number(_field(record, "avg_price")) or derive_average_price(amount, volume, latest)
    auction_amount = to_number(_field(record, "auction_amount"))
    auction_amount = amount if auction_amount is None and is_auction_time(read_time) else auction_amount
    auction_price = latest if is_auction_time(read_time) else open_price
    auction_pct = to_number(_field(record, "auction_pct")) or derive_pct(auction_price, pre_close)
    unmatched_volume = to_number(_field(record, "unmatched_volume"))
    unmatched_amount = to_number(_field(record, "unmatched_amount")) or (unmatched_volume * latest if unmatched_volume and latest else None)
    buy_prices, buy_volumes = record.get("Buyp"), record.get("Buyv")
    sell_prices, sell_volumes = record.get("Sellp"), record.get("Sellv")
    buy_amount = five_level_amount_wan(buy_prices, buy_volumes)
    sell_amount = five_level_amount_wan(sell_prices, sell_volumes)
    if unmatched_amount is None and is_auction_time(read_time):
        unmatched_amount = derive_auction_unmatched_amount(_first(buy_volumes), _first(sell_volumes), latest or open_price)
    error = snapshot_data.get("Error") if isinstance(snapshot_data, dict) else None
    error_id = snapshot_data.get("ErrorId") if isinstance(snapshot_data, dict) else None
    row = {
        "读取时间": read_time.strftime("%Y-%m-%d %H:%M:%S"), "代码": _field(record, "code") or code,
        "名称": _field(record, "name") or (name_lookup(code) if name_lookup else ""),
        "状态": "OK" if error_id in (None, "0", 0) and record else f"ERR:{error or error_id or 'empty'}", "ErrorId": error_id,
        "开盘价": open_price, "最新价": latest, "最新涨幅": derive_pct(latest, pre_close), "均价": avg_price,
        "昨收价": pre_close, "最高价": to_number(_field(record, "high")), "最低价": to_number(_field(record, "low")),
        "5分钟前价": to_number(_field(record, "before_5_min")), "竞价涨幅": auction_pct, "成交量(手)": volume,
        "成交额(万)": amount, "现手": to_number(_field(record, "now_volume")), "竞价金额(万)": auction_amount,
        "竞价未匹配金额(万)": unmatched_amount, "内盘": to_number(_field(record, "inside")), "外盘": to_number(_field(record, "outside")),
        "价差": to_number(_field(record, "tick_diff")), "五档总买金额(万)": buy_amount, "五档总卖金额(万)": sell_amount,
        "五档买卖金额比": buy_amount / sell_amount if buy_amount and sell_amount else None,
        "_raw": snapshot_data, "_raw_keys": list(record.keys()),
    }
    for index, label in enumerate(("一", "二", "三", "四", "五")):
        row[f"买{label}价"] = _level(buy_prices, index)
        row[f"买{label}量"] = _level(buy_volumes, index)
        row[f"卖{label}价"] = _level(sell_prices, index)
        row[f"卖{label}量"] = _level(sell_volumes, index)
    return row
