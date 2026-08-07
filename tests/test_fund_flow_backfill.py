import datetime as dt

import pandas as pd

from task import fund_flow_backfill


class FakeAkShare:
    def __init__(self):
        self.rank_calls = []
        self.history_calls = []

    def stock_sector_fund_flow_rank(self, indicator, sector_type):
        self.rank_calls.append((indicator, sector_type))
        return pd.DataFrame([
            {
                "板块代码": "BK0420",
                "名称": "机器人",
                "今日主力净流入最大股": "示例股份",
            }
        ])

    def stock_sector_fund_flow_hist(self, symbol):
        self.history_calls.append(symbol)
        return pd.DataFrame([
            {"日期": "2026-08-07", "主力净流入-净额": 325_000_000},
        ])


class FakeSource:
    def __init__(self, fail_history_times=0):
        self.fail_history_times = fail_history_times
        self.history_attempts = 0

    def list_boards(self, flow_type):
        return [{"board_code": f"{flow_type}-1", "board_name": f"{flow_type}-board", "leader": "leader"}]

    def board_history(self, board_name):
        self.history_attempts += 1
        if self.history_attempts <= self.fail_history_times:
            raise ConnectionError("source unavailable")
        return pd.DataFrame([
            {"trade_date": 20250807, "f62": 100_000_000},
            {"trade_date": 20260806, "f62": 200_000_000},
            {"trade_date": 20260807, "f62": 300_000_000},
        ])


def test_adapter_uses_injected_akshare_and_maps_board_metadata():
    fake_akshare = FakeAkShare()
    source = fund_flow_backfill.AkShareFundFlowSource(fake_akshare)

    boards = source.list_boards("industry")
    history = source.board_history("机器人")

    assert boards == [{"board_code": "BK0420", "board_name": "机器人", "leader": "示例股份"}]
    assert history.to_dict("records") == [{"日期": "2026-08-07", "主力净流入-净额": 325_000_000}]
    assert fake_akshare.rank_calls == [("今日", "行业资金流")]
    assert fake_akshare.history_calls == ["机器人"]


def test_normalize_history_rows_converts_f62_like_yuan_to_100m():
    frame = pd.DataFrame([
        {"日期": "2026-08-07", "主力净流入-净额": 325_000_000},
        {"日期": dt.date(2026, 8, 6), "f62": -50_000_000},
    ])
    board = {"board_code": "BK0420", "board_name": "机器人", "leader": "示例股份"}

    rows = fund_flow_backfill.normalize_history_rows(frame, board, "concept")

    assert rows == [
        {
            "trade_date": 20260807,
            "board_code": "BK0420",
            "board_name": "机器人",
            "leader": "示例股份",
            "net_inflow_100m": 3.25,
            "flow_type": "concept",
        },
        {
            "trade_date": 20260806,
            "board_code": "BK0420",
            "board_name": "机器人",
            "leader": "示例股份",
            "net_inflow_100m": -0.5,
            "flow_type": "concept",
        },
    ]


def test_backfill_uses_calendar_year_bounds_and_writes_newest_first():
    writes = []
    sleeps = []

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20250806, 20250807, 20260806, 20260807, 20260808],
        source=FakeSource(),
        now=dt.date(2026, 8, 7),
        retries=0,
        rate_delay=0.25,
        sleep=sleeps.append,
        writer=lambda prefix, date, snapshot_time, records: writes.append(
            (prefix, date, snapshot_time, records)
        ),
    )

    assert result["status"] == "success"
    assert result["processed_dates"] == [20260807, 20260806, 20250807]
    assert result["failed_dates"] == []
    assert [(prefix, date) for prefix, date, _, _ in writes] == [
        ("fund_flow", "20260807"),
        ("fund_flow_概念", "20260807"),
        ("fund_flow", "20260806"),
        ("fund_flow_概念", "20260806"),
        ("fund_flow", "20250807"),
        ("fund_flow_概念", "20250807"),
    ]
    assert all(snapshot_time == "15:00:00" for _, _, snapshot_time, _ in writes)
    assert writes[0][3][0] == {
        "时间": "15:00:00",
        "板块代码": "industry-1",
        "板块名称": "industry-board",
        "龙头": "leader",
        "资金净流入(亿)": 3.0,
    }
    assert sleeps == [0.25, 0.25, 0.25]


def test_backfill_injects_retry_delay_before_success():
    sleeps = []
    source = FakeSource(fail_history_times=1)

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260807],
        source=source,
        now=dt.date(2026, 8, 7),
        retries=1,
        retry_delay=1.5,
        rate_delay=0,
        sleep=sleeps.append,
        writer=lambda *args: None,
    )

    assert result["status"] == "success"
    assert source.history_attempts == 3
    assert sleeps == [1.5]


def test_exhausted_network_failure_reports_dates_without_writing():
    writes = []

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260806, 20260807],
        source=FakeSource(fail_history_times=10),
        now=dt.date(2026, 8, 7),
        retries=1,
        retry_delay=0,
        rate_delay=0,
        sleep=lambda seconds: None,
        writer=lambda *args: writes.append(args),
    )

    assert result["status"] == "failed"
    assert result["processed_dates"] == []
    assert result["failed_dates"] == [20260807, 20260806]
    assert "source unavailable" in result["errors"][0]["error"]
    assert writes == []


def test_write_network_failure_is_reported_and_older_dates_continue():
    writes = []

    def writer(prefix, date, snapshot_time, records):
        if date == "20260807":
            raise ConnectionError("redis unavailable")
        writes.append((prefix, date))

    result = fund_flow_backfill.backfill_fund_flow(
        trading_dates=[20260806, 20260807],
        source=FakeSource(),
        now=dt.date(2026, 8, 7),
        retries=0,
        rate_delay=0,
        writer=writer,
    )

    assert result["status"] == "failed"
    assert result["processed_dates"] == [20260806]
    assert result["failed_dates"] == [20260807]
    assert result["errors"] == [
        {"trade_date": 20260807, "error": "redis unavailable"}
    ]
    assert writes == [
        ("fund_flow", "20260806"),
        ("fund_flow_概念", "20260806"),
    ]
