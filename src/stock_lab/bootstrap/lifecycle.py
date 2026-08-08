from contextlib import asynccontextmanager

from .workers import WorkerManager


def create_lifespan(worker_manager: WorkerManager, *, migration_validator=None, settings=None, job_managers=()):
    @asynccontextmanager
    async def lifespan(_app):
        if migration_validator is not None:
            migration_validator(settings=settings)
        worker_manager.start_all()
        try:
            yield
        finally:
            managers = job_managers(_app) if callable(job_managers) else job_managers
            for job_manager in managers:
                job_manager.shutdown()
            worker_manager.stop_all()

    return lifespan
