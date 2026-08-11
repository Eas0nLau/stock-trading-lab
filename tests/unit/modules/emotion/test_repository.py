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
        [{"trade_date": 20260806}, {"trade_date": 20260805}, {"trade_date": 20260804}],
        [
            {"trade_date": 20260804, "board_name": "机器人", "current_board_count": 8, "overall_status": "活跃", "emotion_score": 10.0},
            {"trade_date": 20260805, "board_name": "机器人", "current_board_count": 12, "overall_status": "升温", "emotion_score": 20.0},
            {"trade_date": 20260806, "board_name": "机器人", "current_board_count": 20, "overall_status": "强势延续", "emotion_score": 30.0},
            {"trade_date": 20260806, "board_name": "算力", "current_board_count": 20, "overall_status": "高潮", "emotion_score": 1.0},
        ],
    ])
    service = EmotionService(EmotionRepository(query))

    result = service.hot_board_emotion(days=30)

    assert result["available_dates"] == [20260804, 20260805, 20260806]
    assert [board["board_name"] for board in result["boards"]] == ["算力", "机器人"]
    robot = result["boards"][1]
    assert robot["recent_strength"] == 23.0
    assert robot["recent_trend"][0]["emotion_score"] == 10.0
    assert result["methodology"] == {
        "hot_board_definition": "近3个交易日内至少一天板块个股数量达到8只，排除板块：ST板块、公告、其他",
        "climax_definition": "仅当日板块数量达到20只触发，与平均涨幅、晋级率和情绪分无关",
        "ebb_definition": "上一交易日上榜而当日未上榜时，不受可跟踪样本数量限制，综合状态直接判定为退潮",
        "strong_continuation_definition": "旧池晋级家数或新增涨停家数达到上一日股票池的50%",
        "dispersion_definition": "旧池至少1只继续连板、但未达到50%强势延续门槛时判定为分化；当日未上榜仍按退潮处理",
        "positive_continuation_threshold": "强势延续或良性承接仅在板块达到8只入选阈值后生效；低热度小样本最多按活跃处理",
        "emotion_score_methodology": "当日板块数量贡献0至100分，承接指标仅按样本置信度小幅修正；高潮固定为100分",
        "continuation_methodology": "严格使用上一交易日实际落库股票池，统计本交易日平均涨幅、振幅、晋级率等指标",
        "promotion_definition": "当日涨幅达到9.5%",
        "stock_universe": "仅统计沪深主板股票，并剔除股票名称中含ST的股票",
    }
    assert all("hot_board_emotion_daily" in call[0] for call in query.calls)


def test_market_data_repository_can_supply_canonical_emotion_sources():
    class MarketData:
        def index_daily(self, start_date=None, end_date=None, limit=None):
            return [
                {"trade_date": 20260805, "close_price": 9},
                {"trade_date": 20260806, "close_price": 10},
            ]

        def daily_quotes_for_date(self, trade_date, stock_codes):
            return [{"ts_code": "000001.SZ", "previous_close": 9, "change_pct": 1}]

    repository = EmotionRepository(lambda *_args, **_kwargs: [], market_data=MarketData())

    assert repository.index_daily_rows(10)[-1]["close_price"] == 10
    assert repository.daily_quote_rows(20260806, ["000001"])["000001"]["previous_close"] == 9


def test_date_aware_history_queries_bound_before_order_and_limit():
    query = FakeQuery([[{"trade_date": 20260805}], [{"trade_date": 20260805}]])
    repository = EmotionRepository(query)

    repository.index_daily_rows_through(20260805, 180)
    repository.market_breadth_rows_through(20260805, 80)

    index_sql, index_params, _ = query.calls[0]
    breadth_sql, breadth_params, _ = query.calls[1]
    assert index_sql.index("`trade_date` <= %s") < index_sql.index("ORDER BY `trade_date` DESC")
    assert breadth_sql.index("`trade_date` <= %s") < breadth_sql.index("ORDER BY `trade_date` DESC")
    assert index_params == (20260805,)
    assert breadth_params == (20260805,)


def test_trading_calendar_and_previous_date_are_parameterized():
    query = FakeQuery([
        [{"trade_date": 20260804}, {"trade_date": 20260805}],
        [{"trade_date": 20260804}],
    ])
    repository = EmotionRepository(query)

    assert repository.trading_dates(20260804, 20260805) == [20260804, 20260805]
    assert repository.previous_trading_date(20260805) == 20260804
    assert query.calls[0][1] == (20260804, 20260805)
    assert "MAX(`trade_date`)" in query.calls[1][0]
    assert query.calls[1][1] == (20260805,)


def test_jiuyan_completeness_compares_manifest_to_action_count():
    query = FakeQuery([[{"is_complete": 1}]])

    assert EmotionRepository(query).jiuyan_date_complete(20260805) is True
    sql, params, _ = query.calls[0]
    assert "jiuyan_collection_days" in sql
    assert "accepted_stock_count" in sql
    assert "COUNT(" in sql
    assert params == (20260805,)


def test_board_actions_filter_main_board_and_st_names():
    query = FakeQuery([[]])

    EmotionRepository(query).board_action_rows(20260805)

    sql = query.calls[0][0]
    assert "`stock_code` BETWEEN '000001' AND '003999'" in sql
    assert "`stock_code` BETWEEN '600000' AND '609999'" in sql
    assert "`stock_name` IS NULL OR `stock_name` NOT LIKE '%ST%'" in sql
