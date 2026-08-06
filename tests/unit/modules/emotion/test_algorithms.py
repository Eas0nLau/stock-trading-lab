from stock_lab.modules.emotion.hot_board import analyze_hot_board_day
from stock_lab.modules.emotion.index_cycle import calculate_index_cycle


def test_index_cycle_scores_canonical_market_fixture():
    result = calculate_index_cycle(
        [{
            "trade_date": 20260806,
            "open_price": 3500,
            "close_price": 3560,
            "high_price": 3580,
            "low_price": 3490,
            "turnover": 500,
            "change_pct": 1.2,
        }],
        [{
            "trade_date": 20260806,
            "total_count": 5000,
            "up_count": 3000,
            "down_count": 2000,
            "up_gt5_count": 300,
            "down_lt5_count": 100,
            "limit_up_count": 80,
            "limit_down_count": 5,
            "amount": 12000,
            "avg_pct_chg": 0.8,
        }],
    )

    assert result["trade_date"] == 20260806
    assert result["cycle_score"] == 81.1
    assert result["cycle_state"] == "高潮"
    assert result["score_components"] == {
        "trend": 27.0,
        "breadth": 17.1,
        "limit_structure": 20.0,
        "volume": 7.0,
        "risk_appetite": 10.0,
    }


def test_hot_board_climax_is_driven_by_board_count():
    result = analyze_hot_board_day(
        trade_date=20260806,
        board_name="机器人",
        sample_trade_date=20260805,
        previous_stocks=[{"stock_code": "000001", "stock_name": "平安银行"}],
        current_stocks=[{"stock_code": "000001", "stock_name": "平安银行"}],
        current_quotes={"000001": {"previous_close": 10, "high_price": 11, "low_price": 9.8, "change_pct": 10}},
        previous_board_count=12,
        current_board_count=20,
    )

    assert result["heat_stage"] == "高潮"
    assert result["continuation_state"] == "强势延续"
    assert result["overall_status"] == "高潮"
    assert result["emotion_score"] == 100.0
