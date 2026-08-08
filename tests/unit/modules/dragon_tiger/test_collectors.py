from stock_lab.modules.dragon_tiger.collectors import (
    collect_broker_directory,
    collect_broker_history,
    collect_listings,
)
from stock_lab.modules.dragon_tiger.models import Broker

from .test_parsing import LISTING_HTML


class RecordingRepository:
    def __init__(self):
        self.writes = []

    def trading_dates(self, start_date):
        return [20260805, 20260806]

    def brokers(self):
        return [Broker("B1", "Broker One")]

    def upsert_listings(self, rows):
        self.writes.append(("listings", list(rows)))
        return len(self.writes[-1][1])

    def upsert_brokers(self, rows):
        self.writes.append(("brokers", list(rows)))
        return len(self.writes[-1][1])

    def upsert_broker_history(self, rows):
        self.writes.append(("history", list(rows)))
        return len(self.writes[-1][1])


def test_collect_listings_fetches_dates_and_writes_all_derived_rows():
    repository = RecordingRepository()
    fetched = []

    def fetch_page(trade_date):
        fetched.append(trade_date)
        return "今日龙虎榜暂未公布" if trade_date == 20260805 else LISTING_HTML

    result = collect_listings(20260805, repository, fetch_page)

    assert fetched == [20260805, 20260806]
    assert result == {"listings": 1, "brokers": 2, "broker_history": 2}
    assert [name for name, _ in repository.writes] == ["listings", "brokers", "history"]


def test_collect_broker_directory_deduplicates_across_injected_pages():
    repository = RecordingRepository()
    pages = [
        '<table class="m-table"><tr><th>x</th></tr><tr><td>x</td><td><a href="/code/B1/" title="One">One</a></td></tr></table>',
        '<table class="m-table"><tr><th>x</th></tr><tr><td>x</td><td><a href="/code/B1/" title="One">One</a></td><td>x</td><td><a href="/code/B2/" title="Two">Two</a></td></tr></table>',
    ]

    assert collect_broker_directory(repository, lambda: iter(pages)) == 2
    assert [row.broker_id for row in repository.writes[0][1]] == ["B1", "B2"]


def test_collect_broker_history_uses_cache_and_stops_at_reported_page_count():
    repository = RecordingRepository()
    fetched = []
    cached = {
        ("B1", 1): """
        <span class="page_info">1/2</span><table class="m-table m-table-nosort">
        <tr><th>x</th></tr><tr><td>2026-08-06</td><td><a href="/code/000001/">Ping An</a></td><td>Reason</td><td>1%</td><td>3</td><td>1</td><td>2</td><td>Bank</td></tr>
        </table>""",
    }

    def fetch_page(broker_id, page):
        fetched.append((broker_id, page))
        return """
        <span class="page_info">2/2</span><table class="m-table m-table-nosort">
        <tr><th>x</th></tr><tr><td>2026-08-05</td><td><a href="/code/600000/">Pudong</a></td><td>Other</td><td>2%</td><td>4</td><td>1</td><td>3</td><td>Bank</td></tr>
        </table>"""

    result = collect_broker_history(repository, fetch_page, cache=cached)

    assert result == 2
    assert fetched == [("B1", 2)]
    assert [row.trade_date for row in repository.writes[0][1]] == [20260806, 20260805]
