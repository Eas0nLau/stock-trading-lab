from contextlib import asynccontextmanager

from .workers import WorkerManager


def create_lifespan(worker_manager: WorkerManager, *, migration_validator=None, settings=None):
    @asynccontextmanager
    async def lifespan(_app):
        if migration_validator is not None:
            migration_validator(settings=settings)
        worker_manager.start_all()
        try:
            yield
        finally:
            worker_manager.stop_all()

    return lifespan
