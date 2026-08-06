# Database migrations

Run these scripts manually in numeric order against a stopped application:

1. Back up the complete MySQL database with routines and triggers.
2. Run `001_create_english_schema.sql`. It creates missing tables, validates every canonical column/index signature, and records `001` idempotently only after compatibility succeeds.
3. Run `002_migrate_legacy_data.sql`. It rejects invalid JSON and unparseable broker statistics before copying, refreshes every copied non-key column, and executes all 16 parity gates.
4. Migrate application repositories, APIs, and frontend modules.
5. Run `003_drop_legacy_schema.sql` only after all cutovers are complete.

The third script is destructive and is intentionally not referenced by project initialization. Before its first drop it requires migration versions `001` and `002` plus `migration_validations.validation_version = '002_parity_v1'` with `status = 'succeeded'`. The database guard is necessary but does not replace backup and application-cutover approval.

The repository application cutover is complete and enforced by
`tests/test_cutover_contracts.py`: active Python has no legacy table/Redis literals,
official modules do not import compatibility implementations, and documented old
paths are thin wrappers. This is readiness evidence only. Migration `003` was not
executed as part of the cutover and still requires a stopped application, a fresh
full backup, successful parity state, sampling, and separate destructive approval.

Each `002` gate compares source/target rows and distinct mapped keys. Date-bearing mappings also compare date ranges; fact mappings compare selected amount, volume, count, or indicator aggregates; JSON mappings verify target validity. A mismatch raises SQLSTATE `45000`. The success validation and `002` version are written only after all gates return, and reruns clear stale success first.

`ths_boards`, `ths_board_constituents`, and `ths_stock_relations` are archived,
import-only reference tables. `002_migrate_legacy_data.sql` is their only writer;
the application has no runtime THS collector or consumer and exposes them through
the injected, read-only `stock_lab.modules.ths` repository. Review all three THS
row/key/date-range results and sample their mapped fields. After parity is confirmed, the
three legacy THS tables may be dropped by `003_drop_legacy_schema.sql`; no ongoing
dual-write or collector cutover is required.

Rollback before cutover by dropping the new English tables. Rollback after cutover by stopping the application and restoring the full backup. Do not use the legacy-drop script as a rollback mechanism.

For a clean empty database, use the self-contained `init/stock_trading_lab_v2.sql` instead of these legacy-data migrations. Never use `init/LEGACY_stock_trading_lab_chinese_schema.sql` for current setup; it is an archival migration reference.
