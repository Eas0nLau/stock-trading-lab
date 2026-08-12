from __future__ import annotations

import pytest

from stock_lab.modules.ths.contracts import ThsBoardSeed
from stock_lab.modules.ths.parsing import (
    normalize_ths_code,
    parse_blockrank_jsonp,
    parse_board_directory,
    parse_concept_import_code,
    parse_constituent_page,
    parse_page_count,
)
from stock_lab.shared.errors import DataValidationError


@pytest.fixture
def board() -> ThsBoardSeed:
    return ThsBoardSeed(
        board_code="885001",
        board_type="concept",
        board_name="Robotics",
        page_code="301558",
        detail_path="gn",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, "000001"), ("000001", "000001"), ("1.0", "000001")],
)
def test_normalize_ths_code_preserves_six_digit_identity(value, expected) -> None:
    assert normalize_ths_code(value) == expected


@pytest.mark.parametrize("value", [None, "", "abc", "1234567"])
def test_normalize_ths_code_rejects_invalid_values(value) -> None:
    with pytest.raises(DataValidationError, match="THS code"):
        normalize_ths_code(value)


def test_parse_board_directory_normalizes_and_deduplicates_links() -> None:
    html = """
    <div class="cate_inner">
      <a href="/gn/detail/code/301558/">Robotics</a>
      <a href="/gn/detail/code/301558/">Robotics</a>
      <a href="/gn/detail/code/9/">AI</a>
    </div>
    """

    rows = parse_board_directory(html, "concept", "gn")

    assert [(row.board_type, row.board_name, row.page_code) for row in rows] == [
        ("concept", "AI", "000009"),
        ("concept", "Robotics", "301558"),
    ]
    assert all(row.board_code == "" for row in rows)


def test_parse_board_directory_requires_supported_type_and_container() -> None:
    with pytest.raises(DataValidationError, match="board type"):
        parse_board_directory("<div class='cate_inner'></div>", "other", "gn")
    with pytest.raises(DataValidationError, match="board directory"):
        parse_board_directory("<html></html>", "concept", "gn")


def test_parse_concept_import_code_requires_valid_clid() -> None:
    assert parse_concept_import_code('<input id="clid" value="885001">') == "885001"
    with pytest.raises(DataValidationError, match="clid"):
        parse_concept_import_code("<html></html>")


def test_parse_blockrank_jsonp_preserves_declared_count_and_unique_rows(board) -> None:
    payload = (
        'callback({"block":{"subcodeCount":"2"},"items":['
        '{"5":"1","55":"One"},{"5":"000001","55":"One"},'
        '{"5":"600000","55":"Two"}]})'
    )

    result = parse_blockrank_jsonp(payload, board)

    assert result.declared_count == 2
    assert [row.stock_code for row in result.constituents] == ["000001", "600000"]


@pytest.mark.parametrize(
    "payload",
    ["not-jsonp", 'x({"block":{"subcodeCount":"bad"},"items":[]})', "x([])"],
)
def test_parse_blockrank_jsonp_rejects_invalid_payloads(board, payload) -> None:
    with pytest.raises(DataValidationError, match="blockrank"):
        parse_blockrank_jsonp(payload, board)


def test_parse_page_count_defaults_to_one_and_enforces_limit() -> None:
    assert parse_page_count("<html></html>") == 1
    assert parse_page_count('<span class="page_info">1 / 300</span>') == 300
    with pytest.raises(DataValidationError, match="300"):
        parse_page_count('<span class="page_info">1 / 301</span>')


def test_parse_constituent_page_reads_codes_names_and_deduplicates(board) -> None:
    html = """
    <table>
      <thead><tr><th>代码</th><th>名称</th></tr></thead>
      <tbody>
        <tr><td>1</td><td>One</td></tr>
        <tr><td>000001</td><td>One duplicate</td></tr>
        <tr><td>600000</td><td>Two</td></tr>
      </tbody>
    </table>
    """

    result = parse_constituent_page(html, board)

    assert result.explicitly_empty is False
    assert [row.stock_code for row in result.constituents] == ["000001", "600000"]
    assert result.constituents[0].stock_name == "One"


def test_parse_constituent_page_distinguishes_explicit_empty_from_failure(board) -> None:
    empty = parse_constituent_page(
        "<table><tr><td>暂无成份股数据</td></tr></table>", board
    )
    assert empty.explicitly_empty is True
    assert empty.constituents == ()

    with pytest.raises(DataValidationError, match="constituent table"):
        parse_constituent_page("<html></html>", board)
