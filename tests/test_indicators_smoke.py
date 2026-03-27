import numpy as np
import pandas as pd
import pytest

from indicators import (
    VolumeWeightedAveragePrice,
    SMAIndicator,
    RSIIndicator,
    # EMAIndicator,
    # OBVIndicator,
    # ATRIndicator,
    pivot_points,
    last_value,
)


def _sample_df(n=300):
    rng = np.random.default_rng(42)

    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + rng.random(n)
    low = close - rng.random(n)
    volume = pd.Series(rng.integers(100, 10000, n))

    return pd.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_vwap_smoke():
    df = _sample_df()
    vwap = VolumeWeightedAveragePrice(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        volume=df["volume"],
        window=20,
    ).volume_weighted_average_price()

    assert len(vwap) == len(df)
    assert last_value(vwap) is not None


def test_sma_smoke():
    df = _sample_df()
    sma = SMAIndicator(df["close"], 20).sma_indicator()

    assert len(sma) == len(df)
    assert last_value(sma) is not None


def test_rsi_smoke():
    df = _sample_df()
    rsi = RSIIndicator(df["close"], 14).rsi()

    assert len(rsi) == len(df)
    assert last_value(rsi) is not None


# def test_ema_smoke():
#     df = _sample_df()
#     ema = EMAIndicator(df["close"], 20).ema_indicator()
#
#     assert len(ema) == len(df)
#     assert last_value(ema) is not None


# def test_obv_smoke():
#     df = _sample_df()
#     obv = OBVIndicator(df["close"], df["volume"]).obv()
#
#     assert len(obv) == len(df)
#     assert last_value(obv) is not None


# def test_atr_smoke():
#     df = _sample_df()
#     atr = ATRIndicator(
#         df["high"],
#         df["low"],
#         df["close"],
#         14,
#     ).atr()
#
#     assert len(atr) == len(df)
#     assert last_value(atr) is not None


def test_pivot_points_smoke():
    df = _sample_df()
    piv = pivot_points(df)

    assert set(piv.columns) == {"PP", "R1", "S1", "R2", "S2", "R3", "S3"}
    assert len(piv) == len(df)


def test_percent_change_normalizer_ohlc():
    from resilience import PercentChangeNormalizer

    df = pd.DataFrame(
        {
            "date": [1, 2],
            "open": [100.0, 110.0],
            "high": [105.0, 115.0],
            "low": [95.0, 108.0],
            "close": [102.0, 112.0],
            "volume": [1000, 1200],
        }
    )

    pct = PercentChangeNormalizer.calculate_from_ohlc(df)
    assert pct == pytest.approx((112.0 - 102.0) / 102.0 * 100.0)


def test_pullback_calculation_roundtrip_getIndicators():
    from ibkr_signal_engine import IBapi

    ib = IBapi()
    df = [
        [1, 100.0, 105.0, 95.0, 100.0, 1000],
        [2, 110.0, 120.0, 108.0, 90.0, 1200],
    ]
    result = ib.getIndicators(
        data=df,
        cusip="X",
        contract=None,
        form={
            "ComparisonFastSMA": "Not used",
            "ComparisonPivotPoint": "Not used",
            "ComparisonRelativeVolume": "Not used",
        },
        net_position=0,
        symbol="X",
        market_data=None,
    )

    assert result["pullback"] == pytest.approx((120.0 - 90.0) / (120.0 - 100.0))


def test_unified_evaluate_and_percent_condition():
    from ibkr_signal_engine import evaluate, absolute_cond, percent_cond

    assert evaluate(105, "greater", 100)
    assert evaluate(100, "between", 90, 110)
    assert not evaluate(120, "between", 90, 110)

    assert absolute_cond(50, "lowerEqual", 50)
    assert not absolute_cond(60, "lowerEqual", 50)

    # percentage from base
    assert percent_cond(110, "greater", 100, 5)  # 100 * 1.05 = 105
    assert not percent_cond(104, "greater", 100, 5)
    assert percent_cond(108, "between", 100, 5, 10)  # 105..110
