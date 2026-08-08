import struct
from pathlib import Path

from .models import StockCode


def daily_path(root: Path, stock: StockCode) -> Path:
    return Path(root) / "vipdoc" / stock.market.lower() / "lday" / f"{stock.tdx_name}.day"


def minute_paths(root: Path, stock: StockCode, period: str):
    suffixes = {"1m": [("minline", ".lc1"), ("fzline", ".lc1")], "5m": [("fzline", ".lc5"), ("minline", ".lc5")], "15m": [("fzline", ".lc15"), ("minline", ".lc15")], "30m": [("fzline", ".lc30"), ("minline", ".lc30")], "60m": [("fzline", ".lc60"), ("minline", ".lc60")]}
    if period.lower() not in suffixes:
        raise ValueError(f"Unsupported minute period: {period}")
    return [Path(root) / "vipdoc" / stock.market.lower() / folder / f"{stock.tdx_name}{suffix}" for folder, suffix in suffixes[period.lower()]]


def read_tail_records(path: Path, record_size: int, tail: int):
    size = path.stat().st_size
    aligned = size - size % record_size
    if aligned <= 0:
        return []
    count = min(tail, aligned // record_size)
    with path.open("rb") as file:
        file.seek(aligned - count * record_size)
        data = file.read(count * record_size)
    return [data[index:index + record_size] for index in range(0, len(data), record_size)]


def parse_day_record(raw: bytes, stock: StockCode):
    date, open_, high, low, close, amount, volume, reserved = struct.unpack("<IIIIIfII", raw)
    return {"stock": stock.tq_code, "date": str(date), "open": open_ / 100, "high": high / 100, "low": low / 100, "close": close / 100, "amount": amount, "volume": volume, "reserved": reserved}


def parse_minute_record(raw: bytes, stock: StockCode):
    raw_date, raw_minute, open_, high, low, close, amount, volume, reserved = struct.unpack("<HHfffffII", raw)
    date_part = raw_date % 2048
    date = f"{raw_date // 2048 + 2004:04d}{date_part // 100:02d}{date_part % 100:02d}"
    return {"stock": stock.tq_code, "date": date, "time": f"{raw_minute // 60:02d}:{raw_minute % 60:02d}", "open": open_, "high": high, "low": low, "close": close, "amount": amount, "volume": volume, "reserved": reserved}
