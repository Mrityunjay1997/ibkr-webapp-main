"""
Pure indicator functions / small classes.

Classes:
- VolumeWeightedAveragePrice(...).volume_weighted_average_price() -> pd.Series
- SMAIndicator(...).sma_indicator() -> pd.Series
- RSIIndicator(...).rsi() -> pd.Series
- EMAIndicator(...).ema_indicator() -> pd.Series
- OBVIndicator(...).obv() -> pd.Series
- ATRIndicator(...).atr() -> pd.Series
- FibonacciCalculator(prev_close, high_of_day).calculate_levels() -> dict
- FibonacciCalculator(...).calculate_order_prices(level, ...) -> dict

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


class FibonacciCalculator:
    """
    Calculates Fibonacci pullback levels from a swing high and previous close.
    
    Usage:
        fib = FibonacciCalculator(prev_close=100, high_of_day=115)
        levels = fib.calculate_levels()
        # Returns dict with .236, .382, .5, .618, .786 levels
        # Each level contains: entry, move, pullback
    """
    
    # Standard Fibonacci retracement levels
    DEFAULT_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
    
    def __init__(self, prev_close: float, high_of_day: float, levels: Optional[list] = None):
        """
        Initialize Fibonacci calculator.
        
        Args:
            prev_close: Previous close price (support level)
            high_of_day: High of day price (resistance level)
            levels: List of Fibonacci ratios to calculate (default: [.236, .382, .5, .618, .786])
        """
        self.prev_close = float(prev_close)
        self.high_of_day = float(high_of_day)
        self.levels = levels if levels else self.DEFAULT_LEVELS
        self.move = self.high_of_day - self.prev_close
    
    def calculate_levels(self) -> dict:
        """
        Calculate Fibonacci pullback levels.
        
        Returns:
            Dictionary with keys for each level (e.g., '0.382'):
            {
                '0.382': {
                    'level': 0.382,
                    'move': 1.5,           # High - PrevClose
                    'pullback': 0.573,     # Move × Level
                    'entry': 1.927,        # High - Pullback
                },
                ...
            }
        """
        result = {}
        
        for level in self.levels:
            pullback = self.move * level
            entry = self.high_of_day - pullback
            
            result[f'{level:.3f}'] = {
                'level': level,
                'move': round(self.move, 4),
                'pullback': round(pullback, 4),
                'entry': round(entry, 4),
                'high_of_day': round(self.high_of_day, 4),
                'prev_close': round(self.prev_close, 4),
            }
        
        return result
    
    def calculate_order_prices(self, level: float, entry_offset_pct: float = 0,
                              stop_loss_pct: float = 2.0, target_profit_pct: float = 2.0) -> dict:
        """
        Calculate entry, stop, and target prices with adjustable offsets.
        
        Args:
            level: Fibonacci level (e.g., 0.382)
            entry_offset_pct: Percentage offset from calculated entry (can be +/-)
            stop_loss_pct: Stop loss as % of the move distance
            target_profit_pct: Take profit as % of the move distance
        
        Returns:
            Dictionary with:
            {
                'entry': entry_price,
                'stop_loss': stop_loss_price,
                'target': target_price,
                'risk_per_share': risk_amount,
                'reward_per_share': reward_amount,
            }
        """
        pullback = self.move * level
        base_entry = self.high_of_day - pullback
        
        # Apply entry offset
        entry = base_entry * (1 + entry_offset_pct / 100.0)
        
        # Stop loss is below entry
        stop_distance = self.move * (stop_loss_pct / 100.0)
        stop_loss = entry - stop_distance
        
        # Target is above entry
        target_distance = self.move * (target_profit_pct / 100.0)
        target = entry + target_distance
        
        risk = entry - stop_loss
        reward = target - entry
        
        return {
            'level': level,
            'entry': round(entry, 4),
            'stop_loss': round(stop_loss, 4),
            'target': round(target, 4),
            'risk_per_share': round(risk, 4),
            'reward_per_share': round(reward, 4),
            'risk_reward_ratio': round(reward / risk, 2) if risk > 0 else 0,
            'prev_close': round(self.prev_close, 4),
            'high_of_day': round(self.high_of_day, 4),
            'move': round(self.move, 4),
        }


class GapAnalyzer:
    """
    Detects and tracks open/unfilled gaps in price history.
    
    A gap occurs when today's open price differs significantly from 
    yesterday's close price. Tracks both upside (positive) and downside (negative) gaps.
    
    Gap is considered "open" if it has not been filled:
    - Upside gap: open until price drops back to previous close level
    - Downside gap: open until price rises back to previous close level
    
    Can filter by:
    - Look-back period (how many days to analyze)
    - Minimum gap size (%) to consider
    - Current proximity to gap closing price (%)
    """
    
    def __init__(self, lookback_days: int = 60, min_gap_percent: float = 2.0):
        """
        Initialize gap analyzer.
        
        Args:
            lookback_days: Number of historical days to analyze
            min_gap_percent: Minimum gap size (%) to track (e.g., 2.0 = 2%)
        """
        self.lookback_days = lookback_days
        self.min_gap_percent = min_gap_percent
    
    def detect_gaps(self, historical_data: list) -> dict:
        """
        Detect all gaps in historical price data.
        
        Args:
            historical_data: List of dicts with keys:
                - 'date': Date of candle
                - 'open': Opening price
                - 'close': Closing price
                - 'high': High of day
                - 'low': Low of day
        
        Returns:
            Dict with:
            - 'all_gaps': List of all detected gaps
            - 'open_gaps': List of currently unfilled gaps
            - 'upside_gaps': List of unfilled upside gaps
            - 'downside_gaps': List of unfilled downside gaps
        """
        if not historical_data or len(historical_data) < 2:
            return {
                'all_gaps': [],
                'open_gaps': [],
                'upside_gaps': [],
                'downside_gaps': [],
            }
        
        # Sort by date (oldest first)
        sorted_data = sorted(historical_data, key=lambda x: x.get('date', ''))
        
        # Limit to lookback period
        if len(sorted_data) > self.lookback_days:
            sorted_data = sorted_data[-self.lookback_days:]
        
        all_gaps = []
        
        # Compare each day's open to previous day's close
        for i in range(1, len(sorted_data)):
            prev_candle = sorted_data[i - 1]
            curr_candle = sorted_data[i]
            
            prev_close = float(prev_candle.get('close', 0))
            curr_open = float(curr_candle.get('open', 0))
            
            if prev_close == 0:
                continue
            
            # Calculate gap
            gap_amount = curr_open - prev_close
            gap_percent = abs(gap_amount / prev_close) * 100
            
            # Only track significant gaps
            if gap_percent < self.min_gap_percent:
                continue
            
            gap_info = {
                'date': curr_candle.get('date', ''),
                'prev_close': prev_close,
                'curr_open': curr_open,
                'gap_amount': round(gap_amount, 2),
                'gap_percent': round(gap_percent, 2),
                'direction': 'up' if gap_amount > 0 else 'down',
                'high_since_gap': float(curr_candle.get('high', curr_open)),
                'low_since_gap': float(curr_candle.get('low', curr_open)),
                'is_open': True,  # Will be updated based on price action
            }
            
            all_gaps.append(gap_info)
        
        return {
            'all_gaps': all_gaps,
            'open_gaps': [],  # Updated below
            'upside_gaps': [],
            'downside_gaps': [],
        }
    
    def identify_open_gaps(self, all_gaps: list, current_price: float) -> dict:
        """
        Identify which gaps are still open (unfilled).
        
        Args:
            all_gaps: List of detected gaps from detect_gaps()
            current_price: Current price
        
        Returns:
            Dict with gaps organized by status
        """
        open_gaps = []
        upside_gaps = []
        downside_gaps = []
        
        for gap in all_gaps:
            is_gap_open = False
            
            if gap['direction'] == 'up':
                # Upside gap is closed when price drops back to prev_close
                if current_price >= gap['prev_close']:
                    is_gap_open = True
            else:  # down
                # Downside gap is closed when price rises back to prev_close
                if current_price <= gap['prev_close']:
                    is_gap_open = True
            
            gap['is_open'] = is_gap_open
            
            if is_gap_open:
                open_gaps.append(gap)
                if gap['direction'] == 'up':
                    upside_gaps.append(gap)
                else:
                    downside_gaps.append(gap)
        
        return {
            'all_gaps': all_gaps,
            'open_gaps': open_gaps,
            'upside_gaps': upside_gaps,
            'downside_gaps': downside_gaps,
        }
    
    def find_approaching_gaps(self, open_gaps: list, current_price: float, 
                              proximity_percent: float = 50.0) -> dict:
        """
        Find gaps that are being filled (price approaching gap closing level).
        
        Args:
            open_gaps: List of open gaps
            current_price: Current price
            proximity_percent: How close to closing price (%) to trigger alert
                              e.g., 50% means within 50% of the gap from entry
        
        Returns:
            Dict with:
            - 'approaching': Gaps within proximity threshold
            - 'closest_gap': The gap closest to being filled
            - 'approaching_downside': Downside gaps being filled
            - 'approaching_upside': Upside gaps being filled
        """
        approaching = []
        approaching_downside = []
        approaching_upside = []
        
        for gap in open_gaps:
            distance_to_close = abs(gap['prev_close'] - current_price)
            gap_size = abs(gap['gap_amount'])
            
            # Calculate how close to closing (0-100%)
            if gap_size == 0:
                percent_to_close = 0
            else:
                percent_to_close = (distance_to_close / gap_size) * 100
            
            # Reverse for downside gaps (higher % means closer to close)
            if gap['direction'] == 'down':
                percent_to_close = 100 - percent_to_close
            
            gap['distance_to_close'] = round(distance_to_close, 2)
            gap['percent_to_close'] = round(percent_to_close, 2)
            gap['within_proximity'] = percent_to_close >= (100 - proximity_percent)
            
            if gap['within_proximity']:
                approaching.append(gap)
                if gap['direction'] == 'down':
                    approaching_downside.append(gap)
                else:
                    approaching_upside.append(gap)
        
        # Find closest gap to being filled
        closest_gap = None
        if approaching:
            closest_gap = max(approaching, key=lambda x: x['percent_to_close'])
        
        return {
            'approaching': approaching,
            'closest_gap': closest_gap,
            'approaching_downside': approaching_downside,
            'approaching_upside': approaching_upside,
        }


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
