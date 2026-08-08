# Safe Legacy Code Retirement Design

## Goal

Delete pre-refactor files only when repository-wide evidence shows they have no active caller, runtime contract, documented command, migration role, or external compatibility requirement.

## Immediate Deletions

### Python dead code

- `utils/api.py`: unused eager BaoStock login; replaced by `stock_lab.infrastructure.market_data.baostock`.
- `utils/model_util.py`: unused DeepSeek helper with no repository caller.
- `utils/tdx_util.py`: unused TDX implementation; replaced by `stock_lab.infrastructure.tdx`.
- `utils/driver_chrome.py`: unused browser implementation; replaced by `stock_lab.infrastructure.browser`.
- `tests/test_driver_chrome.py`: tests only the deleted compatibility implementation.

### Frontend template residue

- `front/src/assets/hero.png`
- `front/src/assets/vite.svg`
- `front/src/assets/vue.svg`
- `front/public/icons.svg`
- `front/README.md`

Remove the unused `@tailwindcss/postcss` dependency and lockfile entries through `npm uninstall`. Remove unreferenced `.card`, `.card:hover`, and `.tab-active` selectors. Remove the unread `active` prop from `StrategyPickMonitor.vue`.

### Generated tracked output

Delete all tracked descendants of `output/`. Keep `output/.gitignore` with:

```gitignore
*
!.gitignore
```

Runtime code may continue writing generated reports to `output/`; those files must no longer appear in Git status.

### Database cutover cleanup

Merge `migration/final-legacy-cutover`, which already deletes the retired `jiuyan_reconciliation` job and its dedicated tests after the database cutover completed successfully.

## Explicit Retention

Retain these compatibility surfaces because they still have direct callers, documented commands, or tests:

- `app.py`, `front_run.py`, `config.py`, and `启动项目.ps1`.
- `task/`, `实时监控/`, and `游资溢价分析/`.
- `utils/common.py`, `utils/account.py`, `utils/db.py`, `utils/ini_util.py`, `utils/mysql_base.py`, `utils/redis_base.py`, and `utils/热门板块情绪算法.py`.
- All 57 files under `strategy/`.

Retain database provenance and operator artifacts:

- `init/LEGACY_stock_trading_lab_chinese_schema.sql`.
- `init/stock_trading_lab_v2.sql`.
- `db/migrations/`, `db/schema_mapping.json`, and migration documentation.
- `docs/superpowers/specs/` and active plans.

## Guardrails

- A repository search for each deleted Python/frontend path must show no active reference before deletion.
- Static contracts must assert deleted files remain absent.
- Do not delete compatibility wrappers merely because they are thin.
- Do not remove generated runtime directories such as `data/chrome_profile`.
- Do not combine environment-variable refactoring with the deletion commit.

## Verification

- Focused deletion contracts fail before deletion and pass afterward.
- `npm test` passes.
- `npm run build` passes.
- `uv run pytest --import-mode=importlib -q` passes after the cutover merge.
- `git diff --check` passes.
- `git status --short` contains no generated `output/` files.
