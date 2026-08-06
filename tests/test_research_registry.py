import importlib
import sys

from stock_lab.modules.research.context import ResearchContext
from stock_lab.modules.research.strategies import discover_strategies, get_strategy


def test_registry_discovers_all_legacy_strategy_files_with_ascii_ids():
    entries = discover_strategies()
    assert len(entries) == 57
    assert all(entry.identifier.isascii() for entry in entries)
    assert all(entry.display_name for entry in entries)
    assert get_strategy(entries[0].identifier) is entries[0]


def test_registry_listing_does_not_import_legacy_modules():
    discover_strategies()
    assert not any(name.startswith("strategy_") for name in sys.modules)


def test_selected_strategy_runs_through_uniform_adapter(monkeypatch):
    entry = get_strategy("strategy_demo")
    assert entry is not None
    context = ResearchContext.test_context()
    monkeypatch.setattr(entry, "loader", lambda: type("Module", (), {"run": lambda context: {"ok": True}}))
    assert entry.run(context) == {"ok": True}
