import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StockCode:
    code: str
    market: str

    @property
    def tq_code(self):
        return f"{self.code}.{self.market}"

    @property
    def tdx_name(self):
        return f"{self.market.lower()}{self.code}"


def normalize_stock_code(raw: str) -> StockCode:
    value = str(raw).strip().upper().replace("_", ".").replace("-", ".")
    match = re.fullmatch(r"(SH|SZ|BJ)(\d{6})", value)
    if match:
        return StockCode(match.group(2), match.group(1))
    match = re.fullmatch(r"(\d{1,6})\.(SH|SZ|BJ)", value)
    if match:
        return StockCode(match.group(1).zfill(6), match.group(2))
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError(f"Unsupported stock code format: {raw}")
    market = "SH" if value.startswith(("6", "5", "9", "88")) else "BJ" if value.startswith(("4", "8")) else "SZ"
    return StockCode(value, market)
