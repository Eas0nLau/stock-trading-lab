# Realtime Monitor Directory Retirement

## Goal

Retire the legacy `实时监控/` directory after its runtime implementations have
moved into the canonical Python modules. The application must keep the same
official realtime capabilities without exposing the Chinese wrapper directory
as an executable entrypoint.

## Scope

Delete these legacy wrappers:

- `实时监控/资金流向.py`
- `实时监控/策略选股.py`
- `实时监控/情绪周期.py`
- `实时监控/热门板块情绪.py`
- `实时监控/tdx_全局监控.py`
- `实时监控/tdx_竞价监控.py`

Keep the canonical implementations and their public behavior:

- `stock_lab.modules.fund_flow`
- `stock_lab.modules.strategy_pick`
- `stock_lab.modules.emotion`
- `stock_lab.modules.tdx`
- `stock_lab.jobs.realtime_monitor`

This work does not migrate or delete `task/`, `utils/`, or strategy files. It
does not change monitor algorithms, data schemas, worker scheduling, or TDX
adapters.

## Entry Points

The supported runtime entrypoints remain the FastAPI application and the
canonical module/job APIs. README commands that execute files under
`实时监控/` must be removed or replaced with the supported application/module
entrypoint. No replacement Chinese wrapper directory is introduced.

## Tests And Contracts

- Remove compatibility tests whose only purpose is to import or execute the
  deleted wrappers.
- Add a cutover contract asserting that `实时监控/` does not exist.
- Keep tests for the canonical fund-flow, strategy-pick, emotion, TDX, and
  realtime-worker modules.
- Run the full Python suite and frontend tests after the cutover.

## Risks And Handling

- Historical shell commands may still mention the deleted paths. Search README,
  development docs, migration docs, and scripts before deletion.
- TDX wrappers are currently documented public commands. Replace those command
  references before deleting the files.
- The directory may contain generated `__pycache__` files after tests. Remove
  generated caches before evaluating the deletion contract; do not commit them.

## Acceptance Criteria

1. `实时监控/` has no tracked or generated files after cleanup.
2. No active README or runtime script launches a file below `实时监控/`.
3. Canonical realtime modules remain importable and their tests pass.
4. Full Python tests pass without requiring the deleted wrappers.
5. The change does not modify `task/`, `utils/`, or realtime algorithm behavior.
