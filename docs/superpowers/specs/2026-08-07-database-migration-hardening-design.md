# Database Migration Hardening Design

## Scope

Harden the three MySQL 8 migration scripts so they are restartable, convergent,
and fail closed. Replace the delegated clean-install script with a self-contained
English schema initializer, retire the historical initializer, align optional
Docker initialization, and enforce the contracts with static tests. No test or
command may connect to a user database.

## Migration State

`schema_migrations` records completed migration versions idempotently.
`migration_validations` records validation version, status, timestamp, and
details. Migration `002` clears any prior success marker before work and writes
its success marker only after every executable parity gate passes.

Migration scripts use temporary stored procedures and MySQL `SIGNAL SQLSTATE
'45000'` to abort from the standard MySQL client. Procedures are dropped after
use so reruns do not leave helper objects behind.

## 001 Schema Creation

Every canonical table is created with `CREATE TABLE IF NOT EXISTS`, allowing a
stopped or interrupted run to resume. This does not imply compatibility:
post-creation checks query `information_schema` for the expected tables,
columns, data types, nullability, primary keys, and unique keys. Any incompatible
pre-existing object aborts before version `001` is recorded. Version recording
uses an idempotent insert and occurs only after schema validation succeeds.

## 002 Copy And Validation

Before copying, JSON source columns are checked with `JSON_VALID`. Invalid values
abort with source table, source column, and source key diagnostics. Null values
remain null; valid JSON is cast to MySQL JSON. Free-form broker statistics are
normalized with guarded regular expressions and unit-aware numeric conversion;
unrecognized non-empty values abort instead of silently coercing to zero.

All 16 explicit source-target copies use `INSERT ... ON DUPLICATE KEY UPDATE` and
refresh every copied non-key column. After copying, executable gates compare row
counts and distinct mapped keys for every mapping. Date-bearing mappings also
compare date ranges, numeric fact mappings compare selected amount/count/volume
aggregates, and JSON mappings verify target JSON validity. A mismatch raises an
error. Only then does `002` write a successful validation row and migration
version.

## 003 Destructive Guard

Before the first drop, `003` verifies successful `001` and `002` migration
versions and the expected successful validation version/status. Failure aborts
without dropping a table. The final migration version is recorded idempotently
after all legacy drops.

## Initialization And Documentation

`init/stock_trading_lab_v2.sql` contains `CREATE DATABASE`, `USE`, and the full
canonical English DDL. It contains no `SOURCE`, legacy copy, or drop statements.
The historical SQL dump is renamed with a clear legacy-only name and warning.
Docker Compose declares the same database and an optional init-file mount.
Project setup and migration documentation distinguish clean initialization from
legacy migration.

## Testing

Static parser tests inspect statements and balanced procedure bodies rather than
connecting to MySQL. They enforce all 16 mappings, complete duplicate-key update
sets, preflight normalization, validation coverage and ordering, destructive
guards, initializer self-containment, schema parity, and rerun semantics. Full
Python tests, bytecode compilation, frontend tests/build, and a final diff check
complete verification.
