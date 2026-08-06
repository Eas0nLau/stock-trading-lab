from stock_lab.modules.fund_flow.collector import save_legacy_snapshot


class Repository:
    def __init__(self):
        self.saved = None
        self.published = None

    def save_history(self, flow_type, trade_date, records):
        self.saved = (flow_type, trade_date, records)

    def publish_snapshot(self, flow_type, trade_date, collected_at, record_count):
        self.published = (flow_type, trade_date, collected_at, record_count)


def test_collector_adapter_writes_and_publishes_english_v1_snapshot():
    repository = Repository()
    save_legacy_snapshot(
        repository,
        "concept",
        "20260806",
        "10:00:00",
        [{"时间": "10:00:00", "板块名称": "机器人", "资金净流入(亿)": 3}],
    )

    assert repository.saved == (
        "concept",
        "20260806",
        [{"time": "10:00:00", "board_name": "机器人", "net_inflow_100m": 3}],
    )
    assert repository.published == ("concept", "20260806", "10:00:00", 1)
