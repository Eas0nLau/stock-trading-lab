from collections.abc import Callable
from uuid import uuid4


_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class RedisJobLock:
    def __init__(
        self,
        client,
        key: str,
        ttl_seconds: int,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("Lock expiry must be positive")
        self.client = client
        self.key = key
        self.ttl_seconds = ttl_seconds
        self._token_factory = token_factory or (lambda: uuid4().hex)
        self._token: str | None = None

    def acquire(self) -> bool:
        if self._token is not None:
            return True
        token = self._token_factory()
        acquired = bool(
            self.client.set(
                self.key,
                token,
                nx=True,
                ex=self.ttl_seconds,
            )
        )
        if acquired:
            self._token = token
        return acquired

    def release(self) -> bool:
        if self._token is None:
            return False
        token = self._token
        self._token = None
        return bool(self.client.eval(_RELEASE_SCRIPT, 1, self.key, token))

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Job already running: {self.key}")
        return self

    def __exit__(self, _exception_type, _exception, _traceback) -> None:
        self.release()
