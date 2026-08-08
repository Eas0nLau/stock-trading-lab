import pytest

from stock_lab.modules.dragon_tiger.parsing import (
    listing_brokers,
    listing_history,
    parse_amount,
    parse_broker_directory_page,
    parse_broker_history_page,
    parse_listing_page,
)


LISTING_HTML = """
<div class="twrap">
  <table class="m-table">
    <tr><th>header</th></tr>
    <tr>
      <td></td><td>000001</td><td><a rid="RID-1">Ping An Bank</a></td>
      <td>10.50</td><td>7.25%</td><td>1.2亿</td><td>3500万</td>
    </tr>
  </table>
</div>
<div rid="RID-1">
  <p>明细：日涨幅偏离值达7%的证券</p>
  <p style="padding: 7px 0;">合计买入：2.5亿元 合计卖出：8000万元</p>
  <table class="m-table m-table-nosort mt10">
    <tr><th>header</th></tr>
    <tr><td><a href="/market/lhbyyb/orgcode/B1/" title="机构专用">机构专用</a></td><td>22000</td><td>50</td><td>21950</td></tr>
    <tr><td><a href="/market/no-code/" title="深股通专用">深股通专用</a></td><td>3000</td><td>1000</td><td>2000</td></tr>
  </table>
  <table class="m-table m-table-nosort mt10">
    <tr><th>header</th></tr>
    <tr><td><a href="/market/lhbyyb/orgcode/B2/" title="Broker Two">Broker Two</a></td><td>100</td><td>6000</td><td>-5900</td></tr>
  </table>
</div>
"""


def test_parse_amount_normalizes_source_units():
    assert parse_amount("1.2亿") == 12000.0
    assert parse_amount("3500万") == 3500.0
    assert parse_amount("7.25%") == 7.25
    assert parse_amount("--") is None


def test_parse_listing_page_emits_canonical_listing_and_seats():
    listings = parse_listing_page(LISTING_HTML, 20260806)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.data_id == "20260806_RID-1"
    assert listing.trade_date == 20260806
    assert listing.date_type == "1日"
    assert listing.stock_code == "000001"
    assert listing.turnover == 12000.0
    assert listing.net_buy_amount == 3500.0
    assert listing.total_buy_amount == 25000.0
    assert listing.total_sell_amount == 8000.0
    assert listing.buy_1_broker_id == "B1"
    assert listing.buy_1_broker_name == "机构专用"
    assert listing.buy_1_buy_amount == 22000.0
    assert listing.buy_2_broker_id is None
    assert listing.sell_1_broker_id == "B2"
    assert listing.sell_1_net_amount == -5900.0
    assert listing.buy_3_broker_name is None


def test_listing_derivatives_deduplicate_brokers_and_history_identity():
    listing = parse_listing_page(LISTING_HTML, 20260806)[0]

    brokers = listing_brokers([listing, listing])
    history = listing_history([listing, listing])

    assert [(row.broker_id, row.broker_name) for row in brokers] == [
        ("B1", "机构专用"),
        ("B2", "Broker Two"),
    ]
    assert [row.data_id for row in history] == [
        "B1_20260806_000001_日涨幅偏离值达7%的证券",
        "B2_20260806_000001_日涨幅偏离值达7%的证券",
    ]
    assert history[0].net_amount == 21950.0


def test_parse_listing_page_skips_unpublished_day_and_rejects_malformed_page():
    assert parse_listing_page("今日龙虎榜暂未公布", 20260806) == []

    with pytest.raises(ValueError, match="listing table"):
        parse_listing_page("<html></html>", 20260806)


def test_parse_listing_page_rejects_malformed_listing_row_with_date_context():
    html = """
    <div class="twrap"><table class="m-table">
      <tr><th>header</th></tr>
      <tr><td>1日</td><td>000001</td><td>broken</td></tr>
    </table></div>
    """

    with pytest.raises(ValueError, match=r"listing row 2 malformed.*20260806"):
        parse_listing_page(html, 20260806)


def test_parse_listing_page_rejects_malformed_seat_row_with_listing_context():
    malformed = LISTING_HTML.replace(
        '<tr><td><a href="/market/lhbyyb/orgcode/B1/" title="机构专用">机构专用</a></td><td>22000</td><td>50</td><td>21950</td></tr>',
        "<tr><td>broken</td></tr>",
    )

    with pytest.raises(ValueError, match=r"buy seat row 1 malformed.*20260806.*RID-1"):
        parse_listing_page(malformed, 20260806)


def test_parse_listing_page_preserves_text_only_broker_seat_without_id():
    text_only = LISTING_HTML.replace(
        '<td><a href="/market/lhbyyb/orgcode/B1/" title="机构专用">机构专用</a></td><td>22000</td><td>50</td><td>21950</td>',
        "<td>机构专用</td><td>22000</td><td>50</td><td>21950</td>",
    )

    listing = parse_listing_page(text_only, 20260806)[0]

    assert listing.buy_1_broker_id is None
    assert listing.buy_1_broker_name == "机构专用"
    assert listing.buy_1_buy_amount == 22000.0
    assert listing.buy_1_sell_amount == 50.0
    assert listing.buy_1_net_amount == 21950.0


def test_parse_broker_directory_page_deduplicates_brokers_from_both_columns():
    html = """
    <table class="m-table">
      <tr><th>header</th></tr>
      <tr><td><a href="/code/NOISE/" title="Not a broker">1</a></td><td><a href="/code/B1/" title="Broker One">One</a></td><td>x</td><td><a href="/code/B2/" title="Broker Two">Two</a></td></tr>
      <tr><td>2</td><td><a href="/code/B1/" title="Broker One">One</a></td></tr>
    </table>
    """

    assert [(row.broker_id, row.broker_name) for row in parse_broker_directory_page(html)] == [
        ("B1", "Broker One"),
        ("B2", "Broker Two"),
    ]


def test_parse_broker_history_page_normalizes_rows_and_page_count():
    html = """
    <span class="page_info">1/3</span>
    <table class="m-table m-table-nosort">
      <tr><th>header</th></tr>
      <tr><td>2026-08-06</td><td><a href="/code/000001/">Ping An</a></td><td>Reason</td><td>7.2%</td><td>3000万</td><td>1000万</td><td>2000万</td><td>Bank</td></tr>
    </table>
    """

    rows, page_count = parse_broker_history_page(html, "B1", "Broker One")

    assert page_count == 3
    assert rows[0].data_id == "B1_20260806_000001_Reason"
    assert rows[0].trade_date == 20260806
    assert rows[0].change_pct == 7.2
    assert rows[0].net_amount == 2000.0
    assert rows[0].board_name == "Bank"


def test_parse_broker_history_page_keeps_legacy_two_page_fallback():
    html = """
    <table class="m-table m-table-nosort">
      <tr><th>header</th></tr>
    </table>
    """

    rows, page_count = parse_broker_history_page(html, "B1", "Broker One")

    assert rows == []
    assert page_count == 2


def test_parse_broker_history_page_rejects_malformed_row_with_broker_context():
    html = """
    <table class="m-table m-table-nosort">
      <tr><th>header</th></tr>
      <tr><td>2026-08-06</td><td>broken</td></tr>
    </table>
    """

    with pytest.raises(ValueError, match=r"broker history row 1 malformed.*B1"):
        parse_broker_history_page(html, "B1", "Broker One")
