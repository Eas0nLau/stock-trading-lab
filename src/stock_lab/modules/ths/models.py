from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ThsBoard:
    board_code: str
    board_type: str
    board_name: str
    page_code: str
    detail_path: str
    collected_date: int
    updated_at: datetime


@dataclass(frozen=True)
class ThsBoardConstituent:
    board_code: str
    stock_code: str
    board_type: str
    board_name: str
    page_code: str
    stock_name: str
    collected_date: int
    updated_at: datetime


@dataclass(frozen=True)
class ThsStockRelation:
    stock_code: str
    stock_name: str
    industry_names: Optional[str]
    industry_codes: Optional[str]
    concept_names: Optional[str]
    concept_codes: Optional[str]
    collected_date: int
    updated_at: datetime
