# TDX Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate official TDX infrastructure and monitors into English `stock_lab` packages while retaining behavior and executable Chinese wrappers.

**Architecture:** Move reusable TDX client operations into `stock_lab.infrastructure.tdx`. Move parsing, snapshot derivation, global alerts, auction calculations, and securities-universe adaptation into focused `stock_lab.modules.tdx` modules. Thin legacy wrappers delegate to package entry points.

**Tech Stack:** Python 3.12, dataclasses, pathlib/struct, loguru, pytest, existing `Settings` and `MarketDataRepository`.

## Global Constraints

- No actual TDX installation, MySQL server, network, or PyMySQL import is required by tests.
- Official TDX code must use English file/module/function/class identifiers.
- Preserve established binary formats, field aliases, derived values, monitor thresholds, and lifecycle behavior.
- Use `MarketDataRepository.securities()` for the auction stock universe.

### Task 1: Configuration and Infrastructure

**Files:** Create `src/stock_lab/infrastructure/tdx/config.py`, `client.py`, `__init__.py`; modify `src/stock_lab/config/settings.py`; test in `tests/unit/infrastructure/tdx/test_config.py` and `test_client.py`.

- [ ] Add failing tests for validated root/plugin paths, refresh interval, and fake TQ lifecycle/subscription behavior.
- [ ] Run the focused tests and confirm failure before implementation.
- [ ] Add typed configuration helpers and move the existing TQ loading, refresh, subscription, snapshot, and close behavior behind English APIs.
- [ ] Make settings read `TDX_CACHE_REFRESH_INTERVAL_SECONDS` with validation/default behavior while retaining the existing settings field.
- [ ] Run focused tests and confirm pass.

### Task 2: Module Models, Parsing, and Snapshot Logic

**Files:** Create `src/stock_lab/modules/tdx/models.py`, `parsing.py`, `snapshot.py`, `__init__.py`; test in `tests/unit/modules/tdx/test_parsing.py` and `test_snapshot.py`.

- [ ] Add failing tests for code normalization, day/minute records, tail alignment, field aliases, number derivation, and effective quote rows.
- [ ] Run focused tests and confirm failure.
- [ ] Port the pure parsing/snapshot behavior with English identifiers and explicit dependencies for name lookup.
- [ ] Run focused tests and confirm pass.

### Task 3: Universe Adapter and Monitor Logic

**Files:** Create `universe.py`, `global_monitor.py`, `auction_monitor.py`; test in `tests/unit/modules/tdx/test_universe.py`, `test_global_monitor.py`, `test_auction_monitor.py`.

- [ ] Add failing tests for main-board non-ST filtering/limits, threshold crossing/deduplication, limit-up price rules, auction ratios, and seal deltas.
- [ ] Run focused tests and confirm failure.
- [ ] Port pure monitor behavior and make universe loading consume `MarketDataRepository` rows only.
- [ ] Add monitor runtime entry points that inject infrastructure/settings/repository dependencies.
- [ ] Run focused tests and confirm pass.

### Task 4: Compatibility Wrappers and Documentation

**Files:** Replace `实时监控/tdx_全局监控.py` and `实时监控/tdx_竞价监控.py` with wrappers; modify `README.md`, `docs/architecture.md`, `docs/migration.md`, `docs/development.md`; test `tests/unit/compatibility/test_tdx_wrappers.py`.

- [ ] Add failing import/delegation tests that ensure wrappers do not contain official implementation or direct PyMySQL/config imports.
- [ ] Run focused tests and confirm failure.
- [ ] Implement executable wrappers and update documentation.
- [ ] Run wrapper tests and the complete validation suite.

### Task 5: Verification and Commit

- [ ] Run full `pytest`.
- [ ] Run `python -m compileall` over official Python sources and wrappers.
- [ ] Run frontend tests and build using the existing package scripts.
- [ ] Run diff checks for Chinese official identifiers, direct PyMySQL/config coupling, and accidental TDX/MySQL runtime dependencies in tests.
- [ ] Inspect status/diff, stage only intended files, and commit with a concise migration message.
