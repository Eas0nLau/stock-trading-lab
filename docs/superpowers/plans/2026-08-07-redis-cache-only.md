# Redis Cache-Only Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move strategy-pick facts and all remaining historical Redis data to MySQL, leaving Redis only as a rebuildable cache, lock, and event layer.

**Architecture:** Strategy definitions, snapshots, stocks, and events use relational MySQL tables with JSON extension fields. Strategy and fund-flow APIs query MySQL authoritatively and repopulate Redis caches. A guarded migration copies old and V1 Redis data, validates parity, then removes historical keys.

**Tech Stack:** Python 3.12, MySQL 8, redis-py, FastAPI, pytest.

## Global Constraints

- MySQL owns all business facts, history, configuration, and auditable state.
- Redis stores only rebuildable caches, TTL-bound locks/completion markers, and live events.
- Preserve both legacy and V1 data by deduplicating instead of overwriting newer values.
- Back up MySQL and Redis before migration and do not execute `003_drop_legacy_schema.sql`.

### Task 1: Strategy-Pick MySQL Schema And Repository

**Files:** `db/migrations/001_create_english_schema.sql`, `init/stock_trading_lab_v2.sql`, `src/stock_lab/modules/strategy_pick/mysql_repository.py`, repository tests.

- [ ] Add four English tables and unique indexes for definitions, snapshots, stocks, and events.
- [ ] Add transactional CRUD/read repository methods and JSON field validation.
- [ ] Test unique-key upserts, dates/latest/history/events, and rollback behavior.
- [ ] Run focused tests and commit.

### Task 2: MySQL-Authoritative Strategy API And Collector

**Files:** strategy service, API, collector, repository and tests.

- [ ] Make definitions, latest, history, dates, and events read MySQL first.
- [ ] Make collection commit MySQL before updating Redis or publishing SSE.
- [ ] Add Redis cache-miss backfill and TTL policy for same-day keys.
- [ ] Test MySQL failures never publish Redis success and cache loss remains recoverable.
- [ ] Run focused/full tests and commit.

### Task 3: Redis Data Migration And Cleanup

**Files:** `src/stock_lab/jobs/redis_fact_migration.py`, migration tests and docs.

- [ ] Merge all `策略选股:*` and `strategy_pick:v1:*` data into MySQL with deterministic deduplication.
- [ ] Verify strategy counts, dates, snapshot times, stock rows and event IDs.
- [ ] Verify fund-flow MySQL parity, then remove legacy historical fund-flow and strategy keys.
- [ ] Retain only current-day V1 caches plus TTL-bound job markers and locks.
- [ ] Back up configured MySQL/Redis, execute migration, report before/after key inventory, restart services and verify APIs.
