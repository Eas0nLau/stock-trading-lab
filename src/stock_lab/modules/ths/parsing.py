from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from stock_lab.shared.errors import DataValidationError

from .contracts import (
    ThsBlockrankResult,
    ThsBoardSeed,
    ThsConstituent,
    ThsPageResult,
)


def normalize_ths_code(value) -> str:
    raw = str(value or "").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    match = re.fullmatch(r"\d{1,6}", raw)
    if match is None:
        raise DataValidationError(f"Invalid THS code: {value!r}")
    return raw.zfill(6)


def parse_board_directory(html, board_type, detail_path):
    if board_type not in {"concept", "industry"}:
        raise DataValidationError(f"Unsupported THS board type: {board_type!r}")
    soup = BeautifulSoup(str(html or ""), features="lxml")
    container = soup.find("div", class_="cate_inner")
    if container is None:
        raise DataValidationError("Missing THS board directory")
    rows = {}
    for item in container.find_all("a"):
        name = item.get_text(strip=True)
        parts = str(item.get("href") or "").strip("/").split("/")
        if not name or not parts:
            continue
        page_code = normalize_ths_code(parts[-1])
        key = (board_type, page_code, name)
        rows[key] = ThsBoardSeed(
            board_code=page_code if board_type == "industry" else "",
            board_type=board_type,
            board_name=name,
            page_code=page_code,
            detail_path=detail_path,
        )
    if not rows:
        raise DataValidationError(f"Empty THS {board_type} board directory")
    return tuple(rows[key] for key in sorted(rows))


def parse_concept_import_code(html):
    soup = BeautifulSoup(str(html or ""), features="lxml")
    item = soup.find("input", id="clid")
    if item is None:
        raise DataValidationError("Missing THS concept clid")
    try:
        return normalize_ths_code(item.get("value"))
    except DataValidationError as error:
        raise DataValidationError("Invalid THS concept clid") from error


def _constituent(board, stock_code, stock_name):
    return ThsConstituent(
        board_code=board.board_code,
        stock_code=normalize_ths_code(stock_code),
        board_type=board.board_type,
        board_name=board.board_name,
        page_code=board.page_code,
        stock_name=str(stock_name or "").strip(),
    )


def parse_blockrank_jsonp(text, board):
    raw = str(text or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise DataValidationError("Invalid THS blockrank JSONP")
    try:
        payload = json.loads(raw[start : end + 1])
        block = payload["block"]
        declared_count = int(float(block["subcodeCount"]))
        items = payload["items"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DataValidationError("Invalid THS blockrank payload") from error
    if declared_count < 0 or not isinstance(items, list):
        raise DataValidationError("Invalid THS blockrank payload")
    rows = {}
    for item in items:
        if not isinstance(item, dict):
            raise DataValidationError("Invalid THS blockrank item")
        row = _constituent(board, item.get("5"), item.get("55"))
        if not row.stock_name:
            raise DataValidationError("Invalid THS blockrank stock name")
        rows.setdefault(row.stock_code, row)
    return ThsBlockrankResult(
        declared_count=declared_count,
        constituents=tuple(rows[code] for code in sorted(rows)),
    )


def parse_page_count(html, max_pages=300):
    soup = BeautifulSoup(str(html or ""), features="lxml")
    item = soup.find("span", class_="page_info")
    if item is None:
        return 1
    match = re.search(r"/\s*(\d+)", item.get_text(strip=True))
    if match is None:
        raise DataValidationError("Invalid THS page count")
    page_count = int(match.group(1))
    if page_count < 1 or page_count > int(max_pages):
        raise DataValidationError(
            f"THS page count exceeds safety limit {int(max_pages)}"
        )
    return page_count


def parse_constituent_page(html, board):
    raw = str(html or "")
    if "暂无成份股数据" in raw:
        return ThsPageResult((), explicitly_empty=True)
    soup = BeautifulSoup(raw, features="lxml")
    target = None
    code_index = name_index = None
    for table in soup.find_all("table"):
        headers = [item.get_text(strip=True) for item in table.find_all("th")]
        if "代码" in headers and "名称" in headers:
            target = table
            code_index = headers.index("代码")
            name_index = headers.index("名称")
            break
    if target is None:
        raise DataValidationError("Missing THS constituent table")
    rows = {}
    for table_row in target.find_all("tr"):
        cells = table_row.find_all("td")
        if not cells:
            continue
        if max(code_index, name_index) >= len(cells):
            raise DataValidationError("Invalid THS constituent table row")
        row = _constituent(
            board,
            cells[code_index].get_text(strip=True),
            cells[name_index].get_text(strip=True),
        )
        if not row.stock_name:
            raise DataValidationError("Invalid THS constituent stock name")
        rows.setdefault(row.stock_code, row)
    if not rows:
        raise DataValidationError("Empty THS constituent table")
    return ThsPageResult(tuple(rows[code] for code in sorted(rows)))
