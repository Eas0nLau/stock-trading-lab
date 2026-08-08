import threading
from dataclasses import dataclass
from typing import Callable

from loguru import logger


@dataclass
class WorkerRegistration:
    name: str
    target: Callable[[], None]
    stop: Callable[[], None] | None = None
    thread: threading.Thread | None = None


class WorkerManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._workers: dict[str, WorkerRegistration] = {}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._workers)

    def register(
        self,
        name: str,
        target: Callable[[], None],
        *,
        stop: Callable[[], None] | None = None,
    ) -> None:
        if name in self._workers:
            raise ValueError(f"Worker already registered: {name}")
        self._workers[name] = WorkerRegistration(name=name, target=target, stop=stop)

    def start_all(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                if worker.thread is not None and worker.thread.is_alive():
                    continue
                worker.thread = threading.Thread(
                    target=self._run_worker,
                    args=(worker,),
                    daemon=True,
                    name=worker.name,
                )
                worker.thread.start()

    def stop_all(self, join_timeout: float = 1.0) -> None:
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            if worker.stop is not None:
                worker.stop()
        for worker in workers:
            if worker.thread is not None and worker.thread.is_alive():
                worker.thread.join(timeout=join_timeout)

    @staticmethod
    def _run_worker(worker: WorkerRegistration) -> None:
        try:
            worker.target()
        except Exception:
            logger.exception("Worker failed: {}", worker.name)
