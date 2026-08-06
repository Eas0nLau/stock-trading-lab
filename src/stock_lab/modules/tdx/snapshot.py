from datetime import datetime
from typing import Any


def to_number(value: Any):
    if value is None or isinstance(value, bool) or value in ("", "--", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_pct(price, base):
    if price is None or base in (None, 0):
        return None
    return round((price / base - 1) * 100, 3)


def extract_snapshot_row(code: str, snapshot_data: dict, read_time: datetime, name_lookup=None):
    record = snapshot_data.get("Data", snapshot_data)
    if isinstance(record, list):
        record = record[0] if record else {}
    latest = to_number(record.get("Price") or record.get("Now"))
    pre_close = to_number(record.get("PreClose"))
    amount = to_number(record.get("Amount"))
    volume = to_number(record.get("Volume"))
    average = to_number(record.get("Average") or record.get("AvgPrice"))
    if average is None and amount and volume:
        candidates = [amount / volume, amount / (volume * 100), amount * 10000 / volume, amount * 10000 / (volume * 100)]
        candidates = [value for value in candidates if 0 < value < 100000]
        if candidates:
            average = min(candidates, key=lambda value: abs(value - latest)) if latest else candidates[0]
    return {"读取时间": read_time.strftime("%Y-%m-%d %H:%M:%S"), "代码": record.get("Code") or code, "名称": record.get("Name") or (name_lookup(code) if name_lookup else ""), "状态": "OK" if record else "ERR:empty", "最新价": latest, "最新涨幅": derive_pct(latest, pre_close), "开盘价": to_number(record.get("Open")), "均价": average, "昨收价": pre_close, "成交额(万)": amount, "成交量(手)": volume, "买一价": to_number(record.get("Buyp", [None])[0] if isinstance(record.get("Buyp"), list) else record.get("Buyp")), "买一量": to_number(record.get("Buyv", [None])[0] if isinstance(record.get("Buyv"), list) else record.get("Buyv"))}
