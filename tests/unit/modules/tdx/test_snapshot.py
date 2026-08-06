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
