from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Security:
    ts_code: str
    symbol: str
    name: str
    area: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[int] = None
    list_status: Optional[str] = None


@dataclass(frozen=True)
class DailyQuote:
    data_id: str
    ts_code: str
    trade_date: int
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    previous_close: Optional[float] = None
    change_amount: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    total_market_value: Optional[float] = None
    circulating_market_value: Optional[float] = None
    free_float_shares: Optional[float] = None
    free_float_market_value: Optional[float] = None
    stock_name: Optional[str] = None
    dde_net_amount: Optional[float] = None


@dataclass(frozen=True)
class IndexDaily:
    trade_date: int
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    amplitude_pct: Optional[float] = None
    change_pct: Optional[float] = None
    change_amount: Optional[float] = None
    turnover_rate: Optional[float] = None
