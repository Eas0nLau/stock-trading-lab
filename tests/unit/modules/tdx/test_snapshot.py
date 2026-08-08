from datetime import datetime

from stock_lab.modules.tdx.snapshot import derive_pct, extract_snapshot_row


def test_extract_snapshot_row_derives_change_and_average():
    row = extract_snapshot_row(
        "000001.SZ",
        {"Code": "000001.SZ", "Price": 11, "PreClose": 10, "Open": 10.5, "Amount": 100000, "Volume": 1000},
        datetime(2026, 8, 6, 10, 0),
    )

    assert row["最新涨幅"] == 10.0
    assert row["均价"] == 1.0


def test_derive_pct_rejects_missing_base():
    assert derive_pct(10, None) is None


def test_snapshot_preserves_legacy_aliases_levels_auction_and_error_metadata():
    row = extract_snapshot_row(
        "000001.SZ",
        {"ErrorId": 0, "Error": "", "Data": [{
            "StockCode": "000001.SZ", "SecName": "Demo", "JinKai": 10.5, "LastPrice": 11,
            "YClose": 10, "AvgPrice": 10.8, "Max": 11.2, "Min": 9.9, "Before5MinNow": 10.7,
            "TotalAmount": 120000, "TotalVolume": 1000, "NowVol": 20, "CallAuctionAmount": 80,
            "AuctionChangePct": 10, "UnmatchedVol": 500, "Inside": 3, "Outside": 4, "TickDiff": .1,
            "Buyp": [11, 10.9, 10.8, 10.7, 10.6], "Buyv": [100, 90, 80, 70, 60],
            "Sellp": [11.1, 11.2, 11.3, 11.4, 11.5], "Sellv": [50, 40, 30, 20, 10],
        }]},
        datetime(2026, 8, 6, 9, 20),
    )

    assert row["状态"] == "OK"
    assert row["ErrorId"] == 0
    assert row["代码"] == "000001.SZ"
    assert row["竞价金额(万)"] == 80
    assert row["竞价未匹配金额(万)"] == 5500
    assert row["买一价"] == 11
    assert row["卖一价"] == 11.1
    assert row["买五量"] == 60
    assert row["卖五量"] == 10
    assert row["五档总买金额(万)"] is not None
    assert row["五档总卖金额(万)"] is not None


def test_snapshot_preserves_error_id_and_raw_payload_for_empty_response():
    payload = {"Error": "missing", "ErrorId": 7, "Data": []}

    row = extract_snapshot_row("000001.SZ", payload, datetime(2026, 8, 6, 10))

    assert row["状态"] == "ERR:missing"
    assert row["ErrorId"] == 7
    assert row["_raw"] is payload
