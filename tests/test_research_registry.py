import sys

import pytest

from stock_lab.modules.research.context import ResearchContext, ResearchConfigurationError, ResearchSafetyError
from stock_lab.modules.research.strategies import (
    StrategyEntry,
    StrategyMetadata,
    discover_strategies,
    get_strategy,
)


def test_registry_discovers_all_legacy_strategy_files_with_ascii_ids():
    entries = discover_strategies()
    assert len(entries) == 57
    assert all(entry.identifier.isascii() for entry in entries)
    assert all(entry.display_name for entry in entries)
    assert all(entry.metadata.entrypoint is not None or entry.metadata.safety_status == "unsupported" for entry in entries)
    assert all(entry.metadata.capabilities for entry in entries)
    assert all(entry.source_path.is_file() for entry in entries)
    assert {entry.metadata.source_name for entry in entries} == {
        path.name for path in entries[0].source_path.parent.glob("*.py")
    }
    assert get_strategy(entries[0].identifier) is entries[0]


def test_registry_listing_does_not_import_legacy_modules():
    discover_strategies()
    assert not any(name.startswith("strategy_") for name in sys.modules)


def test_test_context_blocks_every_catalogued_legacy_import():
    context = ResearchContext.test_context()
    for entry in discover_strategies():
        with pytest.raises(ResearchSafetyError):
            entry.run(context)
    assert not any(name.startswith("stock_lab_legacy_") for name in sys.modules)


def test_unsafe_legacy_strategy_is_rejected_before_import():
    imported = []
    metadata = StrategyMetadata(
        "unsafe", "unsafe.py", "不安全策略", "strategy", ("database",), "unsafe_legacy", True
    )
    entry = StrategyEntry(metadata, loader=lambda: imported.append(True))

    with pytest.raises(ResearchSafetyError, match="before import"):
        entry.run(ResearchContext.test_context(parameters={"target_date": 20260102}))

    assert imported == []


def test_context_aware_strategy_receives_context_without_entrypoint_guessing():
    received = []
    module = type("Module", (), {"run": lambda context: received.append(context) or {"ok": True}})
    metadata = StrategyMetadata("safe", "safe.py", "安全策略", "run", ("market_data",), "context_aware", False)
    entry = StrategyEntry(metadata, loader=lambda: module)
    context = ResearchContext.test_context()

    assert entry.run(context) == {"ok": True}
    assert received == [context]


def test_context_aware_metadata_rejects_ambiguous_entrypoint_before_import():
    imported = []
    metadata = StrategyMetadata("bad", "bad.py", "错误策略", "start", ("market_data",), "context_aware", False)
    entry = StrategyEntry(metadata, loader=lambda: imported.append(True))

    with pytest.raises(ResearchConfigurationError, match="entrypoint"):
        entry.run(ResearchContext.test_context())

    assert imported == []


def test_required_target_date_rejects_none_and_invalid_calendar_date_before_import():
    metadata = StrategyMetadata("dated", "dated.py", "日期策略", "run", ("market_data",), "context_aware", True)
    entry = StrategyEntry(metadata, loader=lambda: None)

    with pytest.raises(ResearchConfigurationError, match="target_date"):
        entry.run(ResearchContext.test_context(parameters={"target_date": None}))
    with pytest.raises(ResearchConfigurationError, match="target_date"):
        entry.run(ResearchContext.test_context(parameters={"target_date": 20260231}))
