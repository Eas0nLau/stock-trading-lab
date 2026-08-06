from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DragonTigerListing:
    data_id: str
    trade_date: int
    source_id: str
    detail_type: str
    date_type: str
    stock_code: str
    stock_name: str
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    turnover: Optional[float] = None
    net_buy_amount: Optional[float] = None
    total_buy_amount: Optional[float] = None
    total_sell_amount: Optional[float] = None
    buy_1_broker_id: Optional[str] = None
    buy_1_broker_name: Optional[str] = None
    buy_1_buy_amount: Optional[float] = None
    buy_1_sell_amount: Optional[float] = None
    buy_1_net_amount: Optional[float] = None
    buy_2_broker_id: Optional[str] = None
    buy_2_broker_name: Optional[str] = None
    buy_2_buy_amount: Optional[float] = None
    buy_2_sell_amount: Optional[float] = None
    buy_2_net_amount: Optional[float] = None
    buy_3_broker_id: Optional[str] = None
    buy_3_broker_name: Optional[str] = None
    buy_3_buy_amount: Optional[float] = None
    buy_3_sell_amount: Optional[float] = None
    buy_3_net_amount: Optional[float] = None
    buy_4_broker_id: Optional[str] = None
    buy_4_broker_name: Optional[str] = None
    buy_4_buy_amount: Optional[float] = None
    buy_4_sell_amount: Optional[float] = None
    buy_4_net_amount: Optional[float] = None
    buy_5_broker_id: Optional[str] = None
    buy_5_broker_name: Optional[str] = None
    buy_5_buy_amount: Optional[float] = None
    buy_5_sell_amount: Optional[float] = None
    buy_5_net_amount: Optional[float] = None
    sell_1_broker_id: Optional[str] = None
    sell_1_broker_name: Optional[str] = None
    sell_1_buy_amount: Optional[float] = None
    sell_1_sell_amount: Optional[float] = None
    sell_1_net_amount: Optional[float] = None
    sell_2_broker_id: Optional[str] = None
    sell_2_broker_name: Optional[str] = None
    sell_2_buy_amount: Optional[float] = None
    sell_2_sell_amount: Optional[float] = None
    sell_2_net_amount: Optional[float] = None
    sell_3_broker_id: Optional[str] = None
    sell_3_broker_name: Optional[str] = None
    sell_3_buy_amount: Optional[float] = None
    sell_3_sell_amount: Optional[float] = None
    sell_3_net_amount: Optional[float] = None
    sell_4_broker_id: Optional[str] = None
    sell_4_broker_name: Optional[str] = None
    sell_4_buy_amount: Optional[float] = None
    sell_4_sell_amount: Optional[float] = None
    sell_4_net_amount: Optional[float] = None
    sell_5_broker_id: Optional[str] = None
    sell_5_broker_name: Optional[str] = None
    sell_5_buy_amount: Optional[float] = None
    sell_5_sell_amount: Optional[float] = None
    sell_5_net_amount: Optional[float] = None


@dataclass(frozen=True)
class BrokerListingHistory:
    data_id: str
    broker_id: str
    broker_name: str
    trade_date: int
    stock_name: str
    stock_code: str
    listing_reason: str
    change_pct: Optional[float] = None
    buy_amount: Optional[float] = None
    sell_amount: Optional[float] = None
    net_amount: Optional[float] = None
    board_name: Optional[str] = None


@dataclass(frozen=True)
class BrokerTopStats:
    broker_id: str
    broker_name: Optional[str] = None
    listing_count: Optional[int] = None
    total_capital_used: Optional[float] = None
    year_listing_count: Optional[int] = None
    year_stock_count: Optional[int] = None
    three_day_follow_success_rate: Optional[float] = None


@dataclass(frozen=True)
class Broker:
    broker_id: str
    broker_name: Optional[str] = None
