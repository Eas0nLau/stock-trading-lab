from __future__ import annotations

import hashlib
import json

import pytest

from stock_lab.modules.market_data.jiuyan_parsing import (
    IncompleteJiuyanResponse,
    parse_batch,
    parse_response,
)


def _stock(
    code: str,
    *,
    name: str = "Sample",
    shares_range: int = 1001,
    time: str = "09:35:00",
):
    return {
        "code": code,
        "name": name,
        "article": {
            "action_info": {
                "time": time,
                "num": "2 days 2 boards",
                "shares_range": shares_range,
                "expound": "Reason",
            }
        },
    }


def _group(name="Robotics", count=2, stocks=None, date="2026-08-05"):
    return {
        "date": date,
        "name": name,
        "count": count,
        "list": stocks if stocks is not None else [_stock("sz000001")],
    }


def test_parse_grouped_response_returns_canonical_batch_and_fingerprint() -> None:
    response = {
        "date": "2026-08-05",
        "data": [
            _group(stocks=[_stock("sz000001"), _stock("sh600000", shares_range=949)]),
            _group(name="Computing", count=1, stocks=[_stock("bj430001")]),
        ],
    }

    batch = parse_batch(response, 20260805)

    assert batch.source_board_count == 2
    assert batch.source_stock_count == 3
    assert batch.accepted_stock_count == 2
    assert len(batch.rows) == 2
    assert batch.rows[0]["stock_code"] == "000001"
    assert batch.rows[0]["data_id"].startswith("20260805_")
    assert len(batch.rows[0]["data_id"]) <= 64
    expected = hashlib.sha256(
        json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert batch.source_fingerprint == expected
    assert parse_response(response, 20260805) == list(batch.legacy_rows)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        ({"data": [_group(date=None)]}, "date proof"),
        ({"date": "2026-08-06", "data": [_group()]}, "date mismatch"),
        ({"date": "2026-08-05", "data": "bad"}, "data must be a list"),
        ({"date": "2026-08-05", "data": []}, "empty boards"),
        ({"data": [_group(name="")]}, "blank board name"),
        ({"data": [_group(count=0)]}, "positive board count"),
        ({"data": [{**_group(), "list": "bad"}]}, "stocks must be a list"),
        ({"data": [_group(stocks=[_stock("")])]}, "stock code"),
        ({"data": [_group(stocks=[_stock("sz000001", name="")])]}, "stock name"),
        (
            {"data": [_group(stocks=[{"code": "sz000001", "name": "Sample"}])]},
            "action info",
        ),
        (
            {
                "data": [
                    _group(
                        stocks=[{
                            **_stock("sz000001"),
                            "article": {"action_info": {"time": "09:35:00"}},
                        }]
                    )
                ]
            },
            "change range",
        ),
        (
            {
                "date": "2026-08-05",
                "data": [{
                    "trade_date": 20260805,
                    "board_name": "Robotics",
                    "board_stock_count": 1,
                    "stock_code": "000001",
                    "stock_name": "Sample",
                    "change_pct": 10.0,
                    "limit_up_at": "09:35:00",
                }],
            },
            "source code",
        ),
        (
            {"data": [_group(stocks=[_stock("sz000001"), _stock("sz000001")])]},
            "duplicate stock",
        ),
        ({"data": [_group(stocks=[_stock("sz000001", time="9:35")])]}, "limit-up time"),
        ({"data": [_group(stocks=[_stock("sz000001", shares_range=949)])]}, "accepted rows"),
    ],
)
def test_parse_batch_rejects_incomplete_responses(response, reason) -> None:
    with pytest.raises(IncompleteJiuyanResponse, match=reason):
        parse_batch(response, 20260805)


@pytest.mark.parametrize(
    ("shares_range", "accepted"),
    [(950, True), (1020, True), (949, False), (1021, False)],
)
def test_parse_batch_applies_filter_after_structural_validation(
    shares_range: int, accepted: bool
) -> None:
    stocks = [_stock("sz000001", shares_range=shares_range)]
    if not accepted:
        stocks.append(_stock("sh600000", shares_range=1000))
    batch = parse_batch({"data": [_group(stocks=stocks)]}, 20260805)

    assert batch.source_stock_count == len(stocks)
    assert any(row["stock_code"] == "000001" for row in batch.rows) is accepted


def test_parse_flat_canonical_response_requires_and_preserves_date_proof() -> None:
    response = {
        "data": {
            "date": "20260805",
            "rows": [{
                "board_name": "Robotics",
                "board_stock_count": 1,
                "stock_code": "1",
                "stock_name": "Sample",
                "source_code": "sz000001",
                "change_pct": 10.0,
                "limit_up_at": "09:35",
                "board_streak": "first",
                "limit_up_reason": "Reason",
            }],
        }
    }

    batch = parse_batch(response, 20260805)

    assert batch.rows[0]["stock_code"] == "000001"
    assert batch.rows[0]["limit_up_at"] == "2026-08-05 09:35:00"
