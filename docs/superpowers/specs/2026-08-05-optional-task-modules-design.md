# Optional Task Modules Design

## Goal

Allow the public application to start when the unpublished `task` package is absent, while automatically restoring the existing scheduled-task behavior if the original package is added later.

## Scope

- Change only task loading and the call sites for `每日更新` and `盘前纪要` in `app.py`.
- Preserve all FastAPI routes, frontend startup, MySQL and Redis behavior, and real-time monitoring behavior.
- Do not create placeholder task implementations or infer unpublished task behavior.

## Design

`app.py` will treat the two task modules as one optional capability. It will attempt to import `task.每日更新` and `task.盘前纪要` during startup.

If the `task` package itself is absent, both module references will be unavailable and the application will log one warning explaining that daily updates and pre-market brief collection are disabled. The application will continue loading.

If the package exists, both modules must import successfully. Their existing scheduler calls and Redis run-lock cleanup will remain unchanged. Import failures caused by dependencies or errors inside an existing `task` package must propagate instead of being hidden as an optional-feature absence.

The scraper loop will check module availability before evaluating each task's schedule and Redis locks. The `__main__` startup block will clear a task's Redis run lock only when that task module is available.

## Error Handling

- Missing top-level `task` package: warn once and continue.
- Existing `task` package with a missing nested dependency, syntax error, or runtime import error: fail startup with the original exception.
- One of the two required task modules missing from an existing package: fail startup, because this indicates an incomplete package rather than the supported public-repository state.

## Tests

Tests will isolate imports from external services and verify:

1. With no `task` package, `app` imports successfully and exposes unavailable task references.
2. With simulated `task.每日更新` and `task.盘前纪要` modules, `app` imports successfully and retains both references.
3. An import error raised from inside an existing `task` package is not swallowed.

## Success Criteria

- The current public checkout can import `app` without a `task` directory.
- A clear warning identifies exactly which scheduled features are disabled.
- Adding the original complete `task` directory and restarting automatically enables the original scheduler behavior without another code change.
- Core API imports and MySQL/Redis connectivity remain valid.
