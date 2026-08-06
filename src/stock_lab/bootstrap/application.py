from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_lab.api import register_routes
from stock_lab.jobs.realtime_monitor import create_default_worker_manager

from .lifecycle import create_lifespan
from .workers import WorkerManager


def create_app(
    settings=None,
    worker_manager: WorkerManager | None = None,
    route_registrar: Callable[[FastAPI], None] = register_routes,
) -> FastAPI:
    del settings
    manager = worker_manager or create_default_worker_manager()
    app = FastAPI(
        title="stock_trading_lab_api",
        lifespan=create_lifespan(manager),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    route_registrar(app)
    app.state.worker_manager = manager
    return app
