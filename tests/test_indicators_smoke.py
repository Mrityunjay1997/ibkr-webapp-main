import numpy as np
import pandas as pd

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
