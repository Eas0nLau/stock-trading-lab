import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parents[4]
LEGACY_FILES = [
    ROOT / "游资溢价分析" / "溢价分析.py",
    ROOT / "游资溢价分析" / "采集" / "龙虎榜数据采集.py",
    ROOT / "游资溢价分析" / "采集" / "营业部数据采集.py",
    ROOT / "游资溢价分析" / "采集" / "游资数据采集.py",
]


def test_official_package_exports_canonical_entrypoints():
    from stock_lab.modules import dragon_tiger

    assert dragon_tiger.DragonTigerRepository is not None
    assert callable(dragon_tiger.collect_listings)
    assert callable(dragon_tiger.collect_broker_directory)
    assert callable(dragon_tiger.collect_broker_history)
    assert callable(dragon_tiger.analyze_broker_premium)


class FailOnUse:
    def __getattr__(self, name):
        raise AssertionError(f"legacy import performed I/O through {name}")


def _load(path, monkeypatch):
    fake_utils = types.ModuleType("utils")
    fake_utils.db = FailOnUse()
    monkeypatch.setitem(sys.modules, "utils", fake_utils)
    name = f"compat_{path.stem}_{id(path)}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_modules_import_without_database_network_or_cache_io(monkeypatch):
    modules = [_load(path, monkeypatch) for path in LEGACY_FILES]

    assert all(callable(module.main) for module in modules)


def test_legacy_analysis_main_delegates_to_canonical_analysis(monkeypatch):
    module = _load(LEGACY_FILES[0], monkeypatch)
    expected = [1, 600000]
    calls = []

    monkeypatch.setattr(module, "_run_analysis", lambda start, latest: calls.append((start, latest)) or expected)

    assert module.main("20260701", "20260806") == expected
    assert calls == [(20260701, 20260806)]


def test_active_python_has_no_legacy_dragon_tiger_table_references():
    offenders = []
    for root in (ROOT / "strategy", ROOT / "task", ROOT / "游资溢价分析"):
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "t_龙虎榜" in source:
                offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []
