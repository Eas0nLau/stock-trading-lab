from stock_lab.modules.tdx.auction_monitor import build_monitor_row, limit_up_price, safe_ratio
from stock_lab.modules.tdx.global_monitor import can_emit_alert, crossed_above, is_effective_quote_row


def test_crossed_above_only_emits_on_transition():
    assert crossed_above(9.9, 10.1, 10, 10)
    assert not crossed_above(10.1, 10.2, 10, 10)


def test_alert_history_deduplicates_until_interval():
    history = {}
    assert can_emit_alert(history, "000001.SZ", "open", 10, 0)
    assert not can_emit_alert(history, "000001.SZ", "open", 11, 0)


def test_auction_math_preserves_board_rules():
    assert limit_up_price("300001.SZ", "Good", 10) == 12.0
    assert safe_ratio(3, 2) == 1.5


def test_build_monitor_row_marks_qualifying_grab_and_seal():
    row = build_monitor_row({"代码": "300001.SZ", "名称": "Good", "最新价": 12, "最新涨幅": 20, "昨收价": 10, "竞价金额(万)": 1200, "买一价": 12, "买一量": 3000, "卖一量": 1000})

    assert row["抢筹"] == "Y"
    assert row["封板"] == "Y"


def test_effective_quote_row_rejects_code_only_rows():
    assert not is_effective_quote_row({"状态": "OK", "代码": "000001.SZ"})
