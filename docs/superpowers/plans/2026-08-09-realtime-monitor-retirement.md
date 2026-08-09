# Realtime Monitor Directory Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the legacy `实时监控/` wrapper directory while keeping the canonical realtime monitoring modules and supported application entrypoints intact.

**Architecture:** The change is a cutover-only cleanup. Existing runtime behavior remains in `stock_lab.modules.fund_flow`, `stock_lab.modules.strategy_pick`, `stock_lab.modules.emotion`, `stock_lab.modules.tdx`, and `stock_lab.jobs.realtime_monitor`; only wrapper files, stale commands, and wrapper-specific tests are removed.

**Tech Stack:** Python 3.12, FastAPI, pytest, Vue/Vite frontend, Git.

## Global Constraints

- Do not modify `task/`, `utils/`, strategy files, or canonical realtime algorithms.
- Do not add a replacement Chinese wrapper directory.
- Keep canonical realtime module tests and worker-manager tests.
- Remove active README commands that execute files below `实时监控/`.
- Generated `__pycache__` files are not committed.

---

### Task 1: Update Cutover Documentation And Contracts

**Files:**
- Modify: `README.md:184-191, 237` to remove executable `实时监控/` commands and describe canonical realtime modules.
- Modify: `tests/test_cutover_contracts.py:38-50, 180-230` to remove wrapper line-limit entries and add the directory-retirement assertion.
- Test: `tests/test_cutover_contracts.py`

**Interfaces:**
- Consumes: The existing canonical module names and application entrypoint already documented in the repository.
- Produces: A contract that requires `ROOT / "实时监控"` to be absent and rejects active README wrapper commands.

- [ ] **Step 1: Write the failing contract test**

Add a test next to the existing legacy-directory contracts:

```python
def test_realtime_monitor_legacy_directory_is_retired():
    assert not (ROOT / "实时监控").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "实时监控/tdx_全局监控.py" not in readme
    assert "实时监控/tdx_竞价监控.py" not in readme
```

Remove the four non-TDX wrapper entries from `WRAPPER_LIMITS`; those files will be deleted in Task 2. Keep the legacy import-root scan because it still protects canonical code from importing legacy packages elsewhere.

- [ ] **Step 2: Run the contract to verify it fails**

Run:

```powershell
uv run pytest --import-mode=importlib tests/test_cutover_contracts.py::test_realtime_monitor_legacy_directory_is_retired -q
```

Expected: FAIL because the directory exists and README still documents the TDX wrapper commands.

- [ ] **Step 3: Update active README entrypoints**

Replace the TDX wrapper command paragraph with the supported canonical entrypoint:

```text
`stock_lab.infrastructure.tdx` 和 `stock_lab.modules.tdx` 是正式的通达信监控实现。通过应用入口或对应模块运行函数启动，不再执行 `实时监控/` 下的兼容脚本。
```

Keep the architecture description and migration table, but describe `实时监控/` as retired rather than as a usable compatibility directory.

- [ ] **Step 4: Run the contract and inspect the diff**

Run:

```powershell
uv run pytest --import-mode=importlib tests/test_cutover_contracts.py::test_realtime_monitor_legacy_directory_is_retired -q
git diff --check
```

Expected: The test still fails only because the wrapper directory has not yet been deleted; README assertions pass.

- [ ] **Step 5: Commit the documentation/contract preparation**

```powershell
git add README.md tests/test_cutover_contracts.py
git commit -m "准备退役实时监控旧入口"
```

### Task 2: Delete Legacy Realtime Wrappers And Compatibility Tests

**Files:**
- Delete: `实时监控/__init__.py`
- Delete: `实时监控/资金流向.py`
- Delete: `实时监控/策略选股.py`
- Delete: `实时监控/情绪周期.py`
- Delete: `实时监控/热门板块情绪.py`
- Delete: `实时监控/tdx_全局监控.py`
- Delete: `实时监控/tdx_竞价监控.py`
- Delete: `tests/unit/compatibility/test_tdx_wrappers.py`
- Modify: compatibility tests that import the four deleted non-TDX wrappers, if present after the contract search.

**Interfaces:**
- Consumes: Canonical modules tested independently by `tests/unit/jobs/test_realtime_monitor.py`, `tests/unit/modules/fund_flow`, `tests/unit/modules/strategy_pick`, `tests/unit/modules/emotion`, and `tests/unit/modules/tdx`.
- Produces: No importable or executable files below `实时监控/`.

- [ ] **Step 1: Confirm wrapper-only test coverage**

Run:

```powershell
uv run pytest --import-mode=importlib tests/unit/compatibility/test_tdx_wrappers.py tests/unit/jobs/test_realtime_monitor.py tests/unit/modules/tdx/test_monitors.py -q
```

Expected: Existing wrapper tests pass before deletion, proving the files being removed are compatibility coverage rather than canonical behavior coverage.

- [ ] **Step 2: Delete wrapper files and wrapper-only tests**

Use `apply_patch` delete operations for all seven files under `实时监控/` and `tests/unit/compatibility/test_tdx_wrappers.py`. Remove any additional compatibility test only if its complete purpose is importing one of the deleted four wrapper files; keep tests that exercise canonical modules or shared compatibility behavior.

- [ ] **Step 3: Remove generated caches**

Run:

```powershell
if (Test-Path -LiteralPath "实时监控") { Remove-Item -LiteralPath "实时监控" -Recurse -Force }
```

Expected: `实时监控/` no longer exists. This removes only the deleted directory and generated caches; it does not touch `task/`, `utils/`, or strategy files.

- [ ] **Step 4: Run the retirement contract**

Run:

```powershell
uv run pytest --import-mode=importlib tests/test_cutover_contracts.py::test_realtime_monitor_legacy_directory_is_retired -q
```

Expected: PASS.

- [ ] **Step 5: Commit the wrapper deletion**

```powershell
git add -A -- "实时监控" tests/unit/compatibility/test_tdx_wrappers.py
git commit -m "退役实时监控旧入口"
```

### Task 3: Verify Canonical Realtime Behavior And Full Cutover

**Files:**
- Test only: `tests/test_cutover_contracts.py`, canonical realtime test directories, and frontend test files.

**Interfaces:**
- Consumes: The canonical realtime worker, fund-flow, strategy-pick, emotion, and TDX modules.
- Produces: Evidence that deleting wrappers did not remove official functionality or introduce stale active references.

- [ ] **Step 1: Search for active deleted-path references**

Run:

```powershell
rg -n "实时监控/(资金流向|策略选股|情绪周期|热门板块情绪|tdx_全局监控|tdx_竞价监控)\.py" README.md docs src front shell tests
```

Expected: No active command or runtime reference. Historical design/spec text may mention the migration source, but no executable command may depend on it.

- [ ] **Step 2: Run canonical realtime tests**

Run:

```powershell
uv run pytest --import-mode=importlib tests/unit/jobs/test_realtime_monitor.py tests/unit/modules/fund_flow tests/unit/modules/strategy_pick tests/unit/modules/emotion tests/unit/modules/tdx tests/unit/bootstrap -q
```

Expected: PASS with no imports from `实时监控/`.

- [ ] **Step 3: Run the full Python suite**

Run:

```powershell
uv run pytest --import-mode=importlib -q
```

Expected: 0 failures. If a failure expects a deleted wrapper, remove or update only that wrapper-specific test; do not restore the wrapper.

- [ ] **Step 4: Run frontend tests and build**

Run from `front/`:

```powershell
npm test
npm run build
```

Expected: Both commands exit successfully.

- [ ] **Step 5: Check final scope and commit state**

Run:

```powershell
git diff --check
```

Expected: Only the README/contracts, deleted wrappers, wrapper-only tests, and plan/spec commits appear in this cutover; `task/`, `utils/`, canonical realtime modules, and algorithms remain unchanged.
