from contextlib import asynccontextmanager

from .workers import WorkerManager


def create_lifespan(worker_manager: WorkerManager):
    @asynccontextmanager
    async def lifespan(_app):
        worker_manager.start_all()
        try:
            yield
        finally:
            worker_manager.stop_all()

    return lifespan
