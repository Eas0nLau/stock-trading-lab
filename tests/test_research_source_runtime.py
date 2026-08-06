from pathlib import Path

import pytest

from stock_lab.modules.research.context import ResearchExecutionError
from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import SelectionResult
from stock_lab.modules.research.source_runtime import run_source_selector


def test_source_runtime_skips_imports_and_top_level_calls_but_preserves_literals(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        "from utils import db, common\n"
        "network_result = forbidden_network_call()\n"
        "THRESHOLD = 4\n"
        "def strategy(filtered_codes, target_date):\n"
        "    rows = common.load_daily_quotes_data(filtered_codes, target_date, target_date)\n"
        "    return rows[rows['pct_chg'] >= THRESHOLD][['ts_code', 'stock_name', 'trade_date', 'close']]\n",
        encoding="utf-8",
    )
    context = OfflineResearchProvider.builtin().context(20260102)

    result = run_source_selector("sample", "样例", source, context)

    assert isinstance(result, SelectionResult)
    assert result.target_date == 20260102
    assert result.rows[0]["ts_code"] == "000001.SZ"
    assert result.rows[0]["close"] == 10.5


def test_source_runtime_returns_shaped_empty_selection(tmp_path):
    source = tmp_path / "empty.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    return common.load_daily_quotes_data([], target_date, target_date)\n",
        encoding="utf-8",
    )
    context = OfflineResearchProvider.builtin().context(20260103)
    result = run_source_selector("empty", "空", source, context)
    assert result.rows == []


def test_source_runtime_wraps_selector_failure_with_strategy_identity(tmp_path):
    source = tmp_path / "broken.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    raise TypeError('bad fixture shape')\n",
        encoding="utf-8",
    )
    context = OfflineResearchProvider.builtin().context(20260102)
    with pytest.raises(ResearchExecutionError, match="broken.*bad fixture shape"):
        run_source_selector("broken", "错误", source, context)


def test_source_runtime_uses_cache_injected_by_provider(tmp_path):
    source = tmp_path / "cached.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    values = db.redis_con_localhost.lrange('fixture', 0, -1)\n"
        "    return pd.DataFrame([{'ts_code': values[0]}]) if values else pd.DataFrame()\n",
        encoding="utf-8",
    )
    context = OfflineResearchProvider.builtin().context(20260102)
    context.query_provider.cache = type("Cache", (), {"lrange": lambda self, key, start, end: ["000001.SZ"]})()

    result = run_source_selector("cached", "缓存", source, context)

    assert result.rows == [{"ts_code": "000001.SZ"}]
