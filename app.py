"""Legacy application entry point."""

import os
from threading import Timer

import uvicorn

import front_run
from stock_lab.bootstrap import create_app
from stock_lab.bootstrap.workers import WorkerManager
from stock_lab.infrastructure.database.migration_state import assert_no_incomplete_migration
from stock_lab.jobs.realtime_monitor import create_default_worker_manager


_demo_mode = os.getenv("STOCK_LAB_DISABLE_WORKERS") == "1"
worker_manager = WorkerManager() if _demo_mode else create_default_worker_manager()
app = create_app(
    worker_manager=worker_manager,
    migration_validator=(
        None
        if os.getenv("STOCK_LAB_SKIP_MIGRATION_CHECK") == "1"
        else assert_no_incomplete_migration
    ),
)


if __name__ == "__main__":
    Timer(0, front_run.run).start()
    uvicorn.run(app, host="0.0.0.0", port=8527, reload=False)
