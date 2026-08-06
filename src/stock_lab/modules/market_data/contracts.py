from collections.abc import Iterable, Mapping
from typing import Protocol


class IntradayBarSource(Protocol):
    def fetch_5m_bars(
        self, start_date: int | str, end_date: int | str, ts_code: str
    ) -> Iterable[Mapping[str, object]]: ...
