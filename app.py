"""Legacy application entry point."""

from threading import Timer

import uvicorn

import front_run
from stock_lab.bootstrap import create_app
from stock_lab.jobs.realtime_monitor import create_default_worker_manager


worker_manager = create_default_worker_manager()
app = create_app(worker_manager=worker_manager)


if __name__ == "__main__":
    Timer(0, front_run.run).start()
    uvicorn.run(app, host="0.0.0.0", port=8051, reload=False)
