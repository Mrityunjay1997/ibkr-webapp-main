import math

import pandas as pd

from scanner.indicators import ATRIndicator, FastOBVIndicator, OBVIndicator


def test_obv_starts_flat_and_uses_price_direction_only():
    close = pd.Series([10, 11, 11, 9, 12])
    volume = pd.Series([100, 200, 300, 400, 500])

    obv = OBVIndicator(close, volume).obv()

    assert obv.tolist() == [0, 200, 200, -200, 300]


def test_smoothed_obv_uses_same_base_obv_series():
    close = pd.Series([10, 11, 11, 9, 12])
    volume = pd.Series([100, 200, 300, 400, 500])

    fast_obv = FastOBVIndicator(close, volume, window=2).obv()

    assert fast_obv.tolist() == [0, 100, 200, 0, 50]


def test_atr_returns_finite_value_with_short_history():
    high = pd.Series([11, 12, 13])
    low = pd.Series([9, 10, 11])
    close = pd.Series([10, 11, 12])

    atr = ATRIndicator(high, low, close, window=14).atr()

    assert math.isfinite(float(atr.iloc[-1]))
    assert float(atr.iloc[-1]) > 0
