from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_lab.api import register_routes
from stock_lab.config import get_settings
from stock_lab.infrastructure.database.migration_state import assert_no_incomplete_migration
from stock_lab.jobs.realtime_monitor import create_default_worker_manager

from .lifecycle import create_lifespan
from .workers import WorkerManager


def create_app(
    settings=None,
    worker_manager: WorkerManager | None = None,
    route_registrar: Callable[[FastAPI], None] = register_routes,
    worker_factory=create_default_worker_manager,
    migration_validator=assert_no_incomplete_migration,
) -> FastAPI:
    settings = get_settings() if settings is None else settings
    manager = worker_manager or worker_factory(settings=settings)
    app = FastAPI(
        title="stock_trading_lab_api",
        lifespan=create_lifespan(
            manager,
            migration_validator=migration_validator,
            settings=settings,
            job_managers=lambda current_app: tuple(
                manager for manager in (getattr(current_app.state, "dragon_tiger_job_manager", None),) if manager
            ),
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    route_registrar(app, settings=settings)
    app.state.worker_manager = manager
    app.state.settings = settings
    return app
