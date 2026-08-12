from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ThsBoardSeed:
    board_code: str
    board_type: str
    board_name: str
    page_code: str
    detail_path: str


@dataclass(frozen=True)
class ThsConstituent:
    board_code: str
    stock_code: str
    board_type: str
    board_name: str
    page_code: str
    stock_name: str


@dataclass(frozen=True)
class ThsBlockrankResult:
    declared_count: int
    constituents: tuple[ThsConstituent, ...]


@dataclass(frozen=True)
class ThsPageResult:
    constituents: tuple[ThsConstituent, ...]
    explicitly_empty: bool = False


@dataclass(frozen=True)
class ThsBoardCollection:
    board: ThsBoardSeed
    constituents: tuple[ThsConstituent, ...]
    explicitly_empty: bool
    source: Literal["blockrank", "html", "explicit_empty"]


@dataclass(frozen=True)
class ThsBoardFailure:
    board: ThsBoardSeed
    error: str


@dataclass(frozen=True)
class ThsSnapshot:
    boards: tuple[ThsBoardSeed, ...]
    constituents: tuple[ThsConstituent, ...]
    stock_relations: tuple[dict[str, object], ...]
    empty_board_count: int


@dataclass(frozen=True)
class ThsCollectionResult:
    snapshot: ThsSnapshot | None
    failed_boards: tuple[ThsBoardFailure, ...]
    errors: tuple[str, ...]
    observed_board_count: int
    observed_constituent_count: int
