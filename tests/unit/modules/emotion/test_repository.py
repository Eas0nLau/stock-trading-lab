import json

from stock_lab.modules.emotion.repository import EmotionRepository
from stock_lab.modules.emotion.service import EmotionService


class FakeQuery:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, sql, params=None, fetch=False):
        self.calls.append((sql, params, fetch))
        return self.responses.pop(0)


def test_latest_index_emotion_queries_only_english_table():
    query = FakeQuery([[{"trade_date": 20260806}]])
    repository = EmotionRepository(query)

    row = repository.latest_index_emotion()

    assert row["trade_date"] == 20260806
    assert "FROM `index_emotion_daily`" in query.calls[0][0]
    assert "t_指数" not in query.calls[0][0]


def test_service_translates_persisted_legacy_index_json():
    query = FakeQuery([[
        {
            "trade_date": 20260806,
            "full_result_json": json.dumps(
                {"状态": "success", "周期状态": "发酵", "市场宽度": {"上涨家数": 3000}},
                ensure_ascii=False,
            ),
        }
    ]])
    service = EmotionService(EmotionRepository(query))

    result = service.current_index_emotion()

    assert result["status"] == "success"
    assert result["index_cycle"]["cycle_state"] == "发酵"
    assert result["index_cycle"]["market_breadth"]["advancing_count"] == 3000


def test_hot_board_service_groups_english_rows():
    query = FakeQuery([
        [{"trade_date": 20260806}, {"trade_date": 20260805}],
        [{
            "trade_date": 20260806,
            "board_name": "机器人",
            "current_board_count": 20,
            "overall_status": "强势延续",
            "emotion_score": 80.0,
        }],
    ])
    service = EmotionService(EmotionRepository(query))

    result = service.hot_board_emotion(days=30)

    assert result["available_dates"] == [20260805, 20260806]
    assert result["boards"][0]["board_name"] == "机器人"
    assert result["boards"][0]["recent_trend"][0]["emotion_score"] == 80.0
    assert all("hot_board_emotion_daily" in call[0] for call in query.calls)


def test_market_data_repository_can_supply_canonical_emotion_sources():
    class MarketData:
        def index_daily(self, limit=None):
            return [{"trade_date": 20260806, "close_price": 10}]

        def daily_quotes_for_date(self, trade_date, stock_codes):
            return [{"ts_code": "000001.SZ", "previous_close": 9, "change_pct": 1}]

    repository = EmotionRepository(lambda *_args, **_kwargs: [], market_data=MarketData())

    assert repository.index_daily_rows(10)[0]["close_price"] == 10
    assert repository.daily_quote_rows(20260806, ["000001"])["000001"]["previous_close"] == 9
