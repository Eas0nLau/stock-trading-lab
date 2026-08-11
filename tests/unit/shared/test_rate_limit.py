from concurrent.futures import ThreadPoolExecutor

from stock_lab.shared.rate_limit import RequestRateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limiter_serializes_concurrent_slots():
    clock = Clock()
    limiter = RequestRateLimiter(
        0.5,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _item: limiter.wait(), range(2)))

    assert clock.sleeps == [0.5]
    assert clock.now == 0.5


def test_zero_interval_does_not_sleep():
    clock = Clock()
    limiter = RequestRateLimiter(
        0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.wait()
    limiter.wait()

    assert clock.sleeps == []
