# Emotion Module Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate index and hot-board emotion to English Python modules, English database tables, versioned English API responses, and English frontend model fields.

**Architecture:** `stock_lab.modules.emotion` owns contract translation, repositories, services, and `/api/v1` routes. Legacy algorithms remain callable through adapters during this phase, but all new database access and public payload keys are English. The Vue views consume a dedicated emotion API client and English normalizers while keeping Chinese visible labels and state values.

**Tech Stack:** Python 3.12, FastAPI, MySQL 8, pytest, Vue 3, ECharts, Vite.

## Global Constraints

- New code identifiers and wire keys are English.
- Chinese is allowed only for visible labels, domain display values, raw third-party fields, and legacy adapters.
- New repositories query only `index_daily`, `daily_quotes`, `index_market_breadth`, `index_emotion_daily`, `hot_board_emotion_daily`, and `jiuyan_actions`.
- `/api/v1` never returns Chinese object keys, including nested persisted JSON.
- Old routes remain available until both Vue pages use `/api/v1`.
- Missing data returns `status=empty`; infrastructure errors are not disguised as empty data.
- Existing algorithms keep their scoring behavior in this phase.

---

### Task 1: English emotion contract and versioned routes

**Files:**
- Create: `src/stock_lab/modules/__init__.py`
- Create: `src/stock_lab/modules/emotion/__init__.py`
- Create: `src/stock_lab/modules/emotion/contracts.py`
- Create: `src/stock_lab/modules/emotion/api.py`
- Modify: `src/stock_lab/api/routes.py`
- Create: `tests/unit/modules/emotion/test_contracts.py`
- Create: `tests/api/test_emotion_v1.py`

**Interfaces:**
- `translate_legacy_payload(value) -> object` recursively converts all known Chinese keys and preserves Chinese display values.
- `register_emotion_routes(app)` exposes `/api/v1/emotion/current` and `/api/v1/emotion/hot-boards`.

- [ ] Write contract and route tests that fail before implementation.
- [ ] Implement a complete explicit key map, duplicate-key aliases, and recursive list/dict translation.
- [ ] Add versioned routes that initially adapt legacy service results.
- [ ] Verify nested payload identifiers are ASCII and run API tests.
- [ ] Commit with `迁移情绪模块英文 API 契约`.

### Task 2: English repositories and task writes

**Files:**
- Create: `src/stock_lab/modules/emotion/repository.py`
- Create: `src/stock_lab/modules/emotion/service.py`
- Create: `src/stock_lab/modules/emotion/jobs.py`
- Modify: `task/emotion_analysis.py`
- Create: `tests/unit/modules/emotion/test_repository.py`
- Create: `tests/unit/modules/emotion/test_jobs.py`

**Interfaces:**
- `EmotionRepository.latest_index_emotion()`, `recent_hot_board_dates(days)`, `hot_board_rows(dates)`, and transactional upserts use only English tables and fields.
- Compatibility functions in `task/emotion_analysis.py` delegate to English jobs and preserve current callable names.

- [ ] Write failing SQL contract tests with a fake database executor.
- [ ] Implement English read repositories without broad exception suppression.
- [ ] Implement explicit legacy-result-to-English-row adapters for index and hot-board writes.
- [ ] Switch task writes to English tables in one transaction per emotion job.
- [ ] Verify old tests plus new repository/job tests.
- [ ] Commit with `迁移情绪数据读写`.

### Task 3: Frontend English emotion models

**Files:**
- Create: `front/src/modules/emotion/api.js`
- Create: `front/src/modules/emotion/normalizers.js`
- Modify: `front/src/views/IndexCycle.vue`
- Modify: `front/src/views/HotBoardEmotion.vue`
- Modify: `front/package.json`
- Create: `front/src/modules/emotion/normalizers.test.js`

**Interfaces:**
- `fetchIndexEmotion()` and `fetchHotBoardEmotion(days)` call `/api/v1`.
- Vue views use English model properties; Chinese remains only in visible labels and state presentation maps.

- [ ] Add failing normalizer tests for index aliases, sparse trends, nulls, and hot-board fields.
- [ ] Implement API client and normalizers.
- [ ] Convert both views to English property access without changing visual text.
- [ ] Run frontend tests and production build.
- [ ] Commit with `迁移情绪前端模块`.

### Task 4: Phase verification and migration documentation

**Files:**
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`
- Modify: `README.md`

- [ ] Verify no new emotion module contains Chinese identifiers.
- [ ] Run `uv run pytest -q` and `npm --prefix front run build`.
- [ ] Document that the five emotion-related English tables can replace their legacy equivalents only after data-copy validation.
- [ ] Keep `003_drop_legacy_schema.sql` blocked because other modules still use legacy tables.
- [ ] Commit with `完成情绪模块迁移`.
