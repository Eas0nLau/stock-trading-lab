import pandas as pd
import pytest

from stock_lab.modules.market_data.indicators import calculate_ths_kdj
from stock_lab.shared.errors import DataValidationError


def frame(rows=10, *, low=0, high=10, close=5):
    return pd.DataFrame([
        {
            "trade_date": 20260801 + index,
            "low": low,
            "high": high,
            "close": close,
        }
        for index in range(rows)
    ])


def test_ths_kdj_reproduces_upstream_warmup_and_first_row():
    result = calculate_ths_kdj(frame(), n=9, m1=3, m2=3)

    assert list(result.columns) == ["trade_date", "k", "d", "j"]
    assert result.loc[0, ["k", "d", "j"]].tolist() == [50.0, 50.0, 50.0]
    assert result.loc[1, "k"] == pytest.approx(33.3333333333)
    assert result.loc[1, "d"] == pytest.approx(44.4444444444)
    assert result.loc[1, "j"] == pytest.approx(11.1111111111)
    assert result.loc[7, "k"] < 3
    assert result.loc[8, "k"] > result.loc[7, "k"]


def test_ths_kdj_flat_window_uses_zero_rsv():
    result = calculate_ths_kdj(frame(low=10, high=10, close=10))

    assert result.loc[8, "k"] < result.loc[7, "k"]
    assert result.loc[9, "k"] < result.loc[8, "k"]


def test_ths_kdj_supports_non_default_smoothing_parameters():
    source = frame(rows=3)
    source.loc[2, "close"] = 8

    result = calculate_ths_kdj(source, n=3, m1=2, m2=4)

    assert result.loc[1, "k"] == pytest.approx(25)
    assert result.loc[1, "d"] == pytest.approx(43.75)
    assert result.loc[2, "k"] == pytest.approx(52.5)
    assert result.loc[2, "d"] == pytest.approx(45.9375)


@pytest.mark.parametrize(("n", "m1", "m2"), [
    (0, 3, 3),
    (9, 0, 3),
    (9, 3, 0),
])
def test_ths_kdj_rejects_non_positive_parameters(n, m1, m2):
    with pytest.raises(DataValidationError, match="must be positive"):
        calculate_ths_kdj(frame(), n=n, m1=m1, m2=m2)


def test_ths_kdj_rejects_missing_columns():
    with pytest.raises(DataValidationError, match="missing columns"):
        calculate_ths_kdj(pd.DataFrame([{"trade_date": 20260801}]))
