import pytest

from stock_lab.modules.research.backtest import run_backtest
from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import BacktestResult, SelectionResult


def test_backtest_reuses_single_date_selector_and_prices_next_session():
    provider = OfflineResearchProvider({
        "securities": [{"ts_code": "000001.SZ", "symbol": "000001", "name": "Fixture"}],
        "daily_quotes": [
            {"ts_code": "000001.SZ", "trade_date": 20260102, "open_price": 9, "close_price": 9.5},
            {"ts_code": "000001.SZ", "trade_date": 20260105, "open_price": 10, "close_price": 11},
        ],
    })

    class Entry:
        identifier = "fixture"
        display_name = "样例"

        def run(self, context):
            rows = [{"ts_code": "000001.SZ"}] if context.target_date == 20260102 else []
            return SelectionResult(self.identifier, self.display_name, context.target_date, rows)

    result = run_backtest(Entry(), provider.context, 20260102, 20260105)

    assert isinstance(result, BacktestResult)
    assert [selection.target_date for selection in result.selections] == [20260102, 20260105]
    assert result.trades == [{
        "ts_code": "000001.SZ", "signal_date": 20260102, "trade_date": 20260105,
        "entry_price": 10, "exit_price": 11, "return_pct": 10.0,
    }]
    assert result.summary["compounded_return"] == pytest.approx(10.0)


def test_backtest_prices_end_date_signal_on_following_session():
    provider = OfflineResearchProvider({
        "securities": [{"ts_code": "1", "symbol": "1", "name": "Fixture"}],
        "daily_quotes": [
            {"ts_code": "1", "trade_date": 20260102, "open_price": 9, "close_price": 9.5},
            {"ts_code": "1", "trade_date": 20260105, "open_price": 10, "close_price": 11},
        ],
    })

    class Entry:
        identifier = "end-date"

        def run(self, context):
            return SelectionResult(
                self.identifier, "结束日", context.target_date,
                [{"ts_code": "1"}],
            )

    result = run_backtest(Entry(), provider.context, 20260102, 20260102)

    assert result.trades[0]["trade_date"] == 20260105
    assert result.trades[0]["ts_code"] == "000001.SZ"
