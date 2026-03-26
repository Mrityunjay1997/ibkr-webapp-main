"""
Pure indicator functions / small classes.

Classes:
- VolumeWeightedAveragePrice(...).volume_weighted_average_price() -> pd.Series
- SMAIndicator(...).sma_indicator() -> pd.Series
- RSIIndicator(...).rsi() -> pd.Series
- EMAIndicator(...).ema_indicator() -> pd.Series
- OBVIndicator(...).obv() -> pd.Series
- ATRIndicator(...).atr() -> pd.Series

Helpers:
- pivot_points(df) -> pd.DataFrame (PP, R1, S1, R2, S2, R3, S3)
- last_value(series, default=None) -> float | None
"""

import numpy as np
import pandas as pd
from typing import Optional


def last_value(series: pd.Series, default: Optional[float] = None) -> Optional[float]:
    """Return the last non-NaN value of a series or `default` if none."""
    if not isinstance(series, pd.Series) or series.empty:
        return default
    val = series.values[-1]
    try:
        return float(val) if not pd.isna(val) else default
    except Exception:
        return default


class VolumeWeightedAveragePrice:
    """Rolling VWAP over a fixed window."""

    def __init__(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int):
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.window = int(window)

    def volume_weighted_average_price(self) -> pd.Series:
        tp = (self.high + self.low + self.close) / 3.0
        pv = tp * self.volume

        pv_roll = pv.rolling(self.window, min_periods=1).sum()
        vol_roll = self.volume.rolling(self.window, min_periods=1).sum()

        with np.errstate(divide="ignore", invalid="ignore"):
            vwap = pv_roll / vol_roll
        return vwap


class SMAIndicator:
    """Simple moving average wrapper."""

    def __init__(self, close: pd.Series, window: int):
        self.close = close
        self.window = int(window)

    def sma_indicator(self) -> pd.Series:
        return self.close.rolling(self.window, min_periods=1).mean()


class RSIIndicator:
    """RSI using Wilder smoothing (EWM)."""

    def __init__(self, close: pd.Series, window: int):
        self.close = close
        self.window = int(window)

    def rsi(self) -> pd.Series:
        delta = self.close.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        avg_gain = gain.ewm(alpha=1.0 / self.window, adjust=False, min_periods=self.window).mean()
        avg_loss = loss.ewm(alpha=1.0 / self.window, adjust=False, min_periods=self.window).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi


class EMAIndicator:
    """Exponential moving average wrapper."""

    def __init__(self, close: pd.Series, window: int):
        self.close = close
        self.window = int(window)

    def ema_indicator(self) -> pd.Series:
        return self.close.ewm(span=self.window, adjust=False, min_periods=1).mean()

    # aliases for compatibility
    def ema(self) -> pd.Series:
        return self.ema_indicator()


class OBVIndicator:
    """On-Balance Volume."""

    def __init__(self, close: pd.Series, volume: pd.Series):
        self.close = close
        self.volume = volume

    def on_balance_volume(self) -> pd.Series:
        direction = self.close.diff()

        signed_volume = self.volume.copy()
        signed_volume[direction > 0] = self.volume[direction > 0]
        signed_volume[direction < 0] = -self.volume[direction < 0]
        signed_volume[direction == 0] = 0.0

        obv = signed_volume.cumsum()
        return obv

    # aliases for compatibility
    def obv(self) -> pd.Series:
        return self.on_balance_volume()

    def onBalanceVolume(self) -> pd.Series:
        return self.on_balance_volume()


class ATRIndicator:
    """Average True Range."""

    def __init__(self, high: pd.Series, low: pd.Series, close: pd.Series, window: int):
        self.high = high
        self.low = low
        self.close = close
        self.window = int(window)

    def average_true_range(self) -> pd.Series:
        high_low = self.high - self.low
        high_close = (self.high - self.close.shift()).abs()
        low_close = (self.low - self.close.shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / self.window, adjust=False, min_periods=self.window).mean()
        return atr

    # aliases for compatibility
    def atr(self) -> pd.Series:
        return self.average_true_range()

    def averageTrueRange(self) -> pd.Series:
        return self.average_true_range()


def pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """Return PP, R1, S1, R2, S2, R3, S3 as a DataFrame."""
    pp = (df["high"] + df["low"] + df["close"]) / 3.0
    r1 = 2 * pp - df["low"]
    s1 = 2 * pp - df["high"]
    r2 = pp + df["high"] - df["low"]
    s2 = pp - df["high"] + df["low"]
    r3 = df["high"] + 2 * (pp - df["low"])
    s3 = df["low"] - 2 * (df["high"] - pp)

    return pd.DataFrame({"PP": pp, "R1": r1, "S1": s1, "R2": r2, "S2": s2, "R3": r3, "S3": s3})
