import sys

import pytest

from stock_lab.modules.research.providers import OfflineResearchProvider
from stock_lab.modules.research.results import SelectionResult
from stock_lab.modules.research.strategies import (
    discover_strategies,
    get_strategy,
)


def test_registry_discovers_all_legacy_strategy_files_with_ascii_ids():
    entries = discover_strategies()
    assert len(entries) == 57
    assert all(entry.identifier.isascii() for entry in entries)
    assert all(entry.display_name for entry in entries)
    assert all(entry.metadata.safety_status == "runnable" for entry in entries)
    assert all(entry.metadata.adapter_family in {"source_selector", "dragon_tiger_premium"} for entry in entries)
    assert all(entry.metadata.capabilities for entry in entries)
    assert all(entry.source_path.is_file() for entry in entries)
    assert {entry.metadata.source_name for entry in entries} == {
        path.name for path in entries[0].source_path.parent.glob("*.py")
    }
    assert get_strategy(entries[0].identifier) is entries[0]


def test_registry_listing_does_not_import_legacy_modules():
    discover_strategies()
    assert not any(name.startswith("strategy_") for name in sys.modules)


def test_offline_context_runs_every_catalogued_strategy_without_legacy_import():
    context = OfflineResearchProvider.builtin().context(20260102)
    for entry in discover_strategies():
        result = entry.run(context)
        assert isinstance(result, SelectionResult), entry.identifier
        assert result.strategy_id == entry.identifier
    assert not any(name.startswith("stock_lab_legacy_") for name in sys.modules)
