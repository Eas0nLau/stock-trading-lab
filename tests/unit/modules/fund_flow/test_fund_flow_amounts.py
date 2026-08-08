from decimal import Decimal

import pytest

from stock_lab.modules.fund_flow.contracts import normalize_net_inflow_100m
from stock_lab.shared.errors import DataValidationError


def test_normalizes_wan_to_yi_with_six_decimal_places():
    assert normalize_net_inflow_100m("41113.02", "wan") == Decimal("4.111302")


def test_canonical_yi_value_is_not_divided_twice():
    assert normalize_net_inflow_100m("4.111302", "100m") == Decimal("4.111302")


@pytest.mark.parametrize("value", [None, "", "not-a-number", object()])
def test_rejects_malformed_amounts(value):
    with pytest.raises(DataValidationError):
        normalize_net_inflow_100m(value)
