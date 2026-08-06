from pathlib import Path

import pytest

from stock_lab.modules.research.context import ResearchExecutionError
from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import SelectionResult
from stock_lab.modules.research.source_runtime import SAFE_BUILTINS, run_source_selector


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


def test_source_runtime_injects_allowlisted_standard_imports(tmp_path):
    source = tmp_path / "standard_imports.py"
    source.write_text(
        "import json\n"
        "from decimal import Decimal, ROUND_HALF_UP\n"
        "def strategy(filtered_codes, target_date):\n"
        "    payload = json.loads('{\"ts_code\": \"1\", \"close\": \"10.55\"}')\n"
        "    close = Decimal(payload['close']).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)\n"
        "    return pd.DataFrame([{'ts_code': payload['ts_code'], 'close': float(close)}])\n",
        encoding="utf-8",
    )

    result = run_source_selector(
        "standard_imports", "标准导入", source,
        OfflineResearchProvider.builtin().context(20260102),
    )

    assert result.rows == [{"ts_code": "000001.SZ", "close": 10.6}]


def test_source_runtime_does_not_hide_name_errors(tmp_path):
    source = tmp_path / "missing_name.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    return missing_dependency(filtered_codes)\n",
        encoding="utf-8",
    )

    with pytest.raises(NameError, match="missing_dependency"):
        run_source_selector(
            "missing_name", "缺失依赖", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


def test_source_runtime_rejects_executable_class_body(tmp_path):
    source = tmp_path / "side_effect_class.py"
    marker = tmp_path / "marker"
    source.write_text(
        f"class Dangerous:\n    open({str(marker)!r}, 'w')\n"
        "def strategy(filtered_codes, target_date):\n"
        "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="class body"):
        run_source_selector(
            "side_effect_class", "副作用", source,
            OfflineResearchProvider.builtin().context(20260102),
        )
    assert not marker.exists()
    assert "open" not in SAFE_BUILTINS


def test_source_runtime_rejects_non_allowlisted_dynamic_import(tmp_path):
    source = tmp_path / "dynamic_import.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    __import__('os')\n"
        "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="not allowed: os"):
        run_source_selector(
            "dynamic_import", "动态导入", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


def test_source_runtime_rejects_executable_class_decorator(tmp_path):
    source = tmp_path / "decorated_class.py"
    source.write_text(
        "class Dangerous:\n"
        "    @side_effect()\n"
        "    def method(self):\n"
        "        pass\n"
        "def strategy(filtered_codes, target_date):\n"
        "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="class body"):
        run_source_selector(
            "decorated_class", "装饰器", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


@pytest.mark.parametrize(
    "class_definition",
    [
        "class Dangerous(side_effect()):\n    pass\n",
        "class Dangerous(object, metaclass=side_effect()):\n    pass\n",
        "@side_effect()\nclass Dangerous:\n    pass\n",
    ],
)
def test_source_runtime_rejects_executable_class_headers(tmp_path, class_definition):
    source = tmp_path / "class_header.py"
    source.write_text(
        class_definition
        + "def strategy(filtered_codes, target_date):\n"
        + "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="class definition"):
        run_source_selector(
            "class_header", "类定义", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


def test_source_runtime_allows_behaviorless_class_with_approved_base(tmp_path):
    source = tmp_path / "safe_class.py"
    source.write_text(
        "class Safe(object):\n"
        "    VALUE = 1\n"
        "    def value(self):\n"
        "        return self.VALUE\n"
        "def strategy(filtered_codes, target_date):\n"
        "    return [] if Safe().value() == 1 else filtered_codes\n",
        encoding="utf-8",
    )

    result = run_source_selector(
        "safe_class", "安全类", source,
        OfflineResearchProvider.builtin().context(20260102),
    )

    assert result.rows == []


def test_source_runtime_rejects_approved_base_name_rebinding_before_exec(tmp_path):
    marker = tmp_path / "marker"
    source = tmp_path / "rebound_base.py"
    source.write_text(
        "class Evil:\n"
        "    def __init_subclass__(cls):\n"
        f"        Path({str(marker)!r}).write_text('executed')\n"
        "object = Evil\n"
        "class Trigger(object):\n"
        "    pass\n"
        "def strategy(filtered_codes, target_date):\n"
        "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="protected class base name"):
        run_source_selector(
            "rebound_base", "重绑定", source,
            OfflineResearchProvider.builtin().context(20260102),
        )
    assert not marker.exists()


@pytest.mark.parametrize(
    "binding",
    [
        "object = tuple\n",
        "__builtins__['object'] = tuple\n",
        "import json as object\n",
        "def object():\n    pass\n",
        "class object:\n    pass\n",
    ],
)
def test_source_runtime_rejects_all_protected_base_binding_forms(tmp_path, binding):
    source = tmp_path / "protected_binding.py"
    source.write_text(
        binding
        + "def strategy(filtered_codes, target_date):\n"
        + "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="protected class base name"):
        run_source_selector(
            "protected_binding", "保护名称", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


def test_source_runtime_rejects_mutable_builtin_class_base(tmp_path):
    source = tmp_path / "mutable_base.py"
    source.write_text(
        "class Unsafe(list):\n"
        "    pass\n"
        "def strategy(filtered_codes, target_date):\n"
        "    return []\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchExecutionError, match="class definition"):
        run_source_selector(
            "mutable_base", "可变基类", source,
            OfflineResearchProvider.builtin().context(20260102),
        )


def test_source_runtime_executes_parameterized_stock_code_queries(tmp_path):
    source = tmp_path / "parameterized.py"
    source.write_text(
        "def strategy(filtered_codes, target_date):\n"
        "    clause, params = common.stock_code_filter(filtered_codes)\n"
        "    rows = db.read_sql(f'SELECT ts_code FROM daily_quotes WHERE {clause}', params)\n"
        "    return rows\n",
        encoding="utf-8",
    )

    result = run_source_selector(
        "parameterized", "参数化", source,
        OfflineResearchProvider.builtin().context(20260102),
    )

    assert result.rows == [{"ts_code": "000001.SZ"}]
