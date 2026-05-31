import math

import pandas as pd

from scanner.indicators import ATRIndicator, FastOBVIndicator, MediumOBVIndicator, OBVIndicator, SlowOBVIndicator


def test_obv_starts_flat_and_uses_price_direction_only():
    close = pd.Series([10, 11, 11, 9, 12])
    volume = pd.Series([100, 200, 300, 400, 500])

    obv = OBVIndicator(close, volume).obv()

    assert obv.tolist() == [0, 200, 200, -200, 300]


def test_windowed_obv_uses_raw_signed_volume_without_smoothing():
    close = pd.Series([10, 11, 11, 9, 12])
    volume = pd.Series([100, 200, 300, 400, 500])

    fast_obv = FastOBVIndicator(close, volume, window=2).obv()

    assert fast_obv.tolist() == [0, 200, 0, -400, 500]


def test_independent_obv_windows_produce_distinct_raw_values():
    close = pd.Series([10, 11, 10, 12, 11, 13])
    volume = pd.Series([100, 200, 300, 400, 500, 600])

    fast_obv = FastOBVIndicator(close, volume, window=2).obv()
    medium_obv = MediumOBVIndicator(close, volume, window=3).obv()
    slow_obv = SlowOBVIndicator(close, volume, window=5).obv()

    assert fast_obv.iloc[-1] == 600
    assert medium_obv.iloc[-1] == 100
    assert slow_obv.iloc[-1] == 200


def test_atr_returns_finite_value_with_short_history():
    high = pd.Series([11, 12, 13])
    low = pd.Series([9, 10, 11])
    close = pd.Series([10, 11, 12])

    atr = ATRIndicator(high, low, close, window=14).atr()

    assert math.isfinite(float(atr.iloc[-1]))
    assert float(atr.iloc[-1]) > 0
