from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Sequence

from .helpers import normalize_symbol, validated_trade_date


class IncompleteJiuyanResponse(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedJiuyanBatch:
    rows: Sequence[dict[str, object]]
    legacy_rows: Sequence[dict[str, object]]
    source_board_count: int
    source_stock_count: int
    accepted_stock_count: int
    source_fingerprint: str


def _fail(reason: str) -> None:
    raise IncompleteJiuyanResponse(reason)


def _value(row, *names, default=None):
    return next(
        (row[name] for name in names if name in row and row[name] not in (None, "")),
        default,
    )


def _strict_date(value) -> int:
    raw = str(value or "").strip()
    if not re.fullmatch(r"(?:\d{8}|\d{4}-\d{2}-\d{2})", raw):
        _fail(f"invalid Jiuyan date proof: {value!r}")
    try:
        return validated_trade_date(raw, "Jiuyan response date")
    except ValueError as error:
        raise IncompleteJiuyanResponse(f"invalid Jiuyan date proof: {value!r}") from error
    except Exception as error:
        raise IncompleteJiuyanResponse(f"invalid Jiuyan date proof: {value!r}") from error


def _positive_int(value, reason: str) -> int:
    raw = str(value or "").strip()
    if not re.fullmatch(r"\d+", raw) or int(raw) <= 0:
        _fail(reason)
    return int(raw)


def _percentage(value, *, scaled: bool) -> float:
    try:
        number = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError) as error:
        raise IncompleteJiuyanResponse("missing or invalid change range") from error
    if not math.isfinite(number):
        _fail("missing or invalid change range")
    return number / 100 if scaled else number


def _symbol(source_code) -> tuple[str, str]:
    raw = str(source_code or "").strip()
    if not raw:
        _fail("missing stock code or source code")
    candidate = raw
    prefix_match = re.fullmatch(r"(?i)(?:sh|sz|bj)(\d{6})", raw)
    if prefix_match:
        candidate = prefix_match.group(1)
    symbol = normalize_symbol(candidate)
    if not re.fullmatch(r"\d{6}", symbol):
        _fail("missing or invalid stock code")
    return symbol, raw


def _limit_up_at(trade_date: int, value) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", raw):
        _fail("missing or malformed limit-up time")
    parsed = None
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = dt.datetime.strptime(raw, pattern)
            break
        except ValueError:
            continue
    if parsed is None:
        _fail("missing or malformed limit-up time")
    date_text = dt.datetime.strptime(str(trade_date), "%Y%m%d").strftime("%Y-%m-%d")
    return f"{date_text} {parsed.strftime('%H:%M:%S')}"


def _date_candidates(response: dict, data, records: list[dict]) -> list[object]:
    candidates = []
    if response.get("date") not in (None, ""):
        candidates.append(response["date"])
    if isinstance(data, dict) and data.get("date") not in (None, ""):
        candidates.append(data["date"])
    for record in records:
        if record.get("date") not in (None, ""):
            candidates.append(record["date"])
        elif record.get("trade_date") not in (None, ""):
            candidates.append(record["trade_date"])
    return candidates


def _records(response: object) -> tuple[dict, object, list[dict]]:
    if not isinstance(response, dict):
        _fail("Jiuyan response must be an object")
    data = response.get("data")
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = next(
            (
                data[key]
                for key in ("rows", "list", "items", "records", "data", "diff")
                if isinstance(data.get(key), list)
            ),
            None,
        )
        if records is None:
            _fail("Jiuyan data must be a list")
    else:
        _fail("Jiuyan data must be a list")
    if not records:
        _fail("Jiuyan response contains empty boards")
    if not all(isinstance(record, dict) for record in records):
        _fail("Jiuyan board rows must be objects")
    return response, data, records


def _canonical_row(
    trade_date: int,
    board_name: str,
    board_stock_count: int,
    stock_code: str,
    stock_name: str,
    source_code: str,
    limit_up_at: str,
    board_streak,
    change_pct: float,
    limit_up_reason,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = f"{trade_date}|{board_name}|{stock_code}"
    data_id = f"{trade_date}_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"
    canonical = {
        "data_id": data_id,
        "trade_date": trade_date,
        "board_name": board_name,
        "board_stock_count": board_stock_count,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "source_code": source_code,
        "limit_up_at": limit_up_at,
        "board_streak": board_streak,
        "change_pct": change_pct,
        "limit_up_reason": limit_up_reason or "",
    }
    legacy = {
        "data_id": data_id,
        "date": trade_date,
        "板块": board_name,
        "板块个股数量": board_stock_count,
        "股票代码": int(stock_code),
        "股票名称": stock_name,
        "code": source_code,
        "涨停时间": limit_up_at,
        "几天几板": board_streak,
        "涨幅": change_pct,
        "涨停解析": limit_up_reason or "",
    }
    return canonical, legacy


def parse_batch(response: object, trade_date) -> ParsedJiuyanBatch:
    try:
        target_date = validated_trade_date(trade_date, "Jiuyan trade date")
    except Exception as error:
        raise IncompleteJiuyanResponse(f"invalid requested trade date: {trade_date!r}") from error
    response, data, records = _records(response)
    candidates = _date_candidates(response, data, records)
    if not candidates:
        _fail("Jiuyan response has no date proof")
    if any(_strict_date(candidate) != target_date for candidate in candidates):
        _fail(f"Jiuyan response date mismatch for {target_date}")

    canonical_rows = []
    legacy_rows = []
    source_stock_count = 0
    source_board_count = 0
    for record in records:
        board_name = str(
            _value(record, "name", "板块", "板块名称", "board", "board_name", default="")
        ).strip()
        if not board_name:
            _fail("Jiuyan response contains a blank board name")
        board_count = _positive_int(
            _value(record, "count", "板块个股数量", "板块数量", "board_stock_count"),
            "Jiuyan board must report a positive board count",
        )
        source_board_count += 1

        grouped = "list" in record
        stocks = record.get("list") if grouped else [record]
        if not isinstance(stocks, list):
            _fail("Jiuyan board stocks must be a list")
        if not stocks:
            _fail("Jiuyan board stocks must not be empty")
        seen_codes = set()
        for stock in stocks:
            if not isinstance(stock, dict):
                _fail("Jiuyan stock rows must be objects")
            source_stock_count += 1
            if grouped:
                source_value = stock.get("code")
                symbol, source_code = _symbol(source_value)
                stock_name = str(stock.get("name") or "").strip()
                if not stock_name:
                    _fail("Jiuyan row is missing stock name")
                article = stock.get("article")
                action = article.get("action_info") if isinstance(article, dict) else None
                if not isinstance(action, dict):
                    _fail("Jiuyan row is missing action info")
                if action.get("shares_range") in (None, ""):
                    _fail("Jiuyan row is missing change range")
                change_pct = _percentage(action["shares_range"], scaled=True)
                limit_up_at = _limit_up_at(target_date, action.get("time"))
                board_streak = action.get("num")
                reason = action.get("expound") or action.get("reason")
            else:
                raw_stock_code = _value(stock, "股票代码", "stock_code", "symbol")
                source_value = _value(stock, "source_code", "code", "原始代码")
                symbol, source_code = _symbol(source_value)
                if raw_stock_code in (None, "") or normalize_symbol(raw_stock_code) != symbol:
                    _fail("Jiuyan row is missing or has invalid stock code")
                stock_name = str(_value(stock, "股票名称", "stock_name", "name", default="")).strip()
                if not stock_name:
                    _fail("Jiuyan row is missing stock name")
                raw_change = _value(stock, "涨幅", "涨跌幅", "change_pct", "pct_chg", "pct")
                if raw_change in (None, ""):
                    _fail("Jiuyan row is missing change range")
                change_pct = _percentage(raw_change, scaled=False)
                limit_up_at = _limit_up_at(
                    target_date,
                    _value(stock, "涨停时间", "涨停时间文本", "limit_up_at", "limit_up_time"),
                )
                board_streak = _value(stock, "几天几板", "连板", "board_streak", "board_count_text")
                reason = _value(stock, "涨停解析", "解析", "limit_up_reason", "description", default="")
            if symbol in seen_codes:
                _fail(f"Jiuyan board contains duplicate stock {symbol}")
            seen_codes.add(symbol)
            if not 9.5 <= change_pct <= 10.2:
                continue
            canonical, legacy = _canonical_row(
                target_date,
                board_name,
                board_count,
                symbol,
                stock_name,
                source_code,
                limit_up_at,
                board_streak,
                change_pct,
                reason,
            )
            canonical_rows.append(canonical)
            legacy_rows.append(legacy)

    if not canonical_rows:
        _fail(f"Jiuyan response has no accepted rows for {target_date}")
    fingerprint = hashlib.sha256(
        json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ParsedJiuyanBatch(
        rows=tuple(canonical_rows),
        legacy_rows=tuple(legacy_rows),
        source_board_count=source_board_count,
        source_stock_count=source_stock_count,
        accepted_stock_count=len(canonical_rows),
        source_fingerprint=fingerprint,
    )


def parse_response(response: object, trade_date) -> list[dict[str, object]]:
    return list(parse_batch(response, trade_date).legacy_rows)
