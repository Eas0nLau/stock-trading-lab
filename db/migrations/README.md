# Database migrations

Run these scripts manually in numeric order against a stopped application:

1. Back up the complete MySQL database with routines and triggers.
2. Run `001_create_english_schema.sql`.
3. Run `002_migrate_legacy_data.sql` and review every validation result.
4. Migrate application repositories, APIs, and frontend modules.
5. Run `003_drop_legacy_schema.sql` only after all cutovers are complete.

The third script is destructive and is intentionally not referenced by project initialization. Before it runs, compare row counts, distinct primary keys, minimum and maximum trade dates, and amount/volume aggregates for every source-target pair.

`ths_boards`, `ths_board_constituents`, and `ths_stock_relations` are archived,
import-only reference tables. `002_migrate_legacy_data.sql` is their only writer;
the application has no runtime THS collector or consumer and exposes them through
the injected, read-only `stock_lab.modules.ths` repository. Review all three THS
row-count results and sample their mapped fields. After parity is confirmed, the
three legacy THS tables may be dropped by `003_drop_legacy_schema.sql`; no ongoing
dual-write or collector cutover is required.

Rollback before cutover by dropping the new English tables. Rollback after cutover by stopping the application and restoring the full backup. Do not use the legacy-drop script as a rollback mechanism.
