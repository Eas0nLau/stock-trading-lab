import pytest

from stock_lab.modules.emotion.jobs import run_hot_board_emotion_job, run_index_emotion_job
from stock_lab.shared.errors import DataValidationError


class FakeRepository:
    def index_daily_rows(self, limit):
        return [{
            "trade_date": 20260806,
            "open_price": 3500,
            "close_price": 3560,
            "high_price": 3580,
            "low_price": 3490,
            "turnover": 500,
            "change_pct": 1.2,
        }]

    def market_breadth_rows(self, limit):
        return [{
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
        }]

    def board_action_rows(self, trade_date):
        return [{
            "board_name": "机器人",
            "board_stock_count": 20,
            "stock_code": "000001",
            "stock_name": "平安银行",
        }]

    def daily_quote_rows(self, trade_date, stock_codes):
        return {"000001": {"stock_code": "000001", "previous_close": 10, "high_price": 11, "low_price": 9.8, "change_pct": 10}}


def test_index_job_writes_english_tables_and_json():
    writes = []

    def calculator(index_rows, market_rows):
        assert index_rows[0]["trade_date"] == 20260806
        return {
            "trade_date": 20260806,
            "cycle_state": "发酵",
            "cycle_score": 70,
            "index_quote": {"close_price": 3560},
            "market_breadth": {"advancing_count": 3000},
            "score_components": {},
            "moving_averages": {},
            "moving_average_slopes": {},
            "signals": [],
            "recent_trend": [],
            "volatility_chart": [],
        }

    run_index_emotion_job(20260806, FakeRepository(), calculator, lambda tables: writes.extend(tables))

    assert [table for table, _keys, _rows in writes] == ["index_market_breadth", "index_emotion_daily"]
    index_row = writes[1][2][0]
    assert index_row["trade_date"] == 20260806
    assert '"cycle_state": "发酵"' in index_row["full_result_json"]


def test_hot_board_job_writes_english_rows():
    writes = []

    def analyzer(**values):
        return {
            "trade_date": values["trade_date"],
            "board_name": values["board_name"],
            "sample_trade_date": values["sample_trade_date"],
            "current_board_count": 20,
            "overall_status": "强势延续",
            "emotion_score": 80,
            "decision_reasons": {"reason": "test"},
        }

    run_hot_board_emotion_job(20260806, 20260805, FakeRepository(), analyzer, lambda tables: writes.extend(tables))

    assert writes[0][0] == "hot_board_emotion_daily"
    row = writes[0][2][0]
    assert row["board_name"] == "机器人"
    assert row["overall_status"] == "强势延续"
    assert row["decision_reasons_json"] == '{"reason": "test"}'


def test_index_job_rejects_previous_day_market_breadth():
    repository = FakeRepository()
    repository.market_breadth_rows = lambda limit: [{"trade_date": 20260805}]

    with pytest.raises(DataValidationError, match="20260806"):
        run_index_emotion_job(20260806, repository, lambda *_args: {}, lambda _tables: None)
