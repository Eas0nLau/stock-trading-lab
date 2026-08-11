import threading
import time


class RequestRateLimiter:
    def __init__(
        self,
        min_interval_seconds,
        *,
        monotonic=time.monotonic,
        sleep=time.sleep,
    ):
        self.min_interval_seconds = max(float(min_interval_seconds), 0.0)
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_request_at = None
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = self._monotonic()
            if self._last_request_at is not None:
                remaining = self.min_interval_seconds - (
                    now - self._last_request_at
                )
                if remaining > 0:
                    self._sleep(remaining)
            self._last_request_at = self._monotonic()
