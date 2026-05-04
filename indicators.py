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
    
    # Check for NaN first
    try:
        if pd.isna(val):
            return default
    except (ValueError, TypeError):
        pass
    
    try:
        # Handle numpy scalar types with .item() method
        if hasattr(val, 'item'):
            return float(val.item())
        else:
            return float(val)
    except (ValueError, TypeError, AttributeError):
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


class FastOBVIndicator:
    """Fast OBV - OBV with 5-bar moving average smoothing."""

    def __init__(self, close: pd.Series, volume: pd.Series, window: int = 5):
        self.close = close
        self.volume = volume
        self.window = int(window)

    def fast_obv(self) -> pd.Series:
        """Calculate OBV and apply fast MA smoothing."""
        direction = self.close.diff()
        
        signed_volume = self.volume.copy()
        signed_volume[direction > 0] = self.volume[direction > 0]
        signed_volume[direction < 0] = -self.volume[direction < 0]
        signed_volume[direction == 0] = 0.0
        
        obv = signed_volume.cumsum()
        # Apply fast moving average
        fast_obv = obv.rolling(self.window, min_periods=1).mean()
        return fast_obv

    # aliases for compatibility
    def obv(self) -> pd.Series:
        return self.fast_obv()


class MediumOBVIndicator:
    """Medium OBV - OBV with 10-bar moving average smoothing."""

    def __init__(self, close: pd.Series, volume: pd.Series, window: int = 10):
        self.close = close
        self.volume = volume
        self.window = int(window)

    def medium_obv(self) -> pd.Series:
        """Calculate OBV and apply medium MA smoothing."""
        direction = self.close.diff()
        
        signed_volume = self.volume.copy()
        signed_volume[direction > 0] = self.volume[direction > 0]
        signed_volume[direction < 0] = -self.volume[direction < 0]
        signed_volume[direction == 0] = 0.0
        
        obv = signed_volume.cumsum()
        # Apply medium moving average
        medium_obv = obv.rolling(self.window, min_periods=1).mean()
        return medium_obv

    # aliases for compatibility
    def obv(self) -> pd.Series:
        return self.medium_obv()


class SlowOBVIndicator:
    """Slow OBV - OBV with 20-bar moving average smoothing."""

    def __init__(self, close: pd.Series, volume: pd.Series, window: int = 20):
        self.close = close
        self.volume = volume
        self.window = int(window)

    def slow_obv(self) -> pd.Series:
        """Calculate OBV and apply slow MA smoothing."""
        direction = self.close.diff()
        
        signed_volume = self.volume.copy()
        signed_volume[direction > 0] = self.volume[direction > 0]
        signed_volume[direction < 0] = -self.volume[direction < 0]
        signed_volume[direction == 0] = 0.0
        
        obv = signed_volume.cumsum()
        # Apply slow moving average
        slow_obv = obv.rolling(self.window, min_periods=1).mean()
        return slow_obv

    # aliases for compatibility
    def obv(self) -> pd.Series:
        return self.slow_obv()


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
    
    Supports standard Fibonacci levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
    
    Usage:
        fib = FibonacciCalculator(prev_close=100, high_of_day=115)
        levels = fib.calculate_levels()
        # Returns dict with .236, .382, .5, .618, .786, 1.0 levels
        # Each level contains: entry, move, pullback, and context
    """
    
    # Standard Fibonacci retracement levels (now includes 100%)
    DEFAULT_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    
    def __init__(self, prev_close: float, high_of_day: float, levels: Optional[list] = None):
        """
        Initialize Fibonacci calculator.
        
        Args:
            prev_close: Previous close price (support level for gap up, resistance for gap down)
            high_of_day: High of day price (resistance level for gap up)
            levels: List of Fibonacci ratios to calculate (default includes 100%)
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
                    'percent_from_support': 57.3,  # How far from prev_close as %
                },
                ...
            }
        """
        result = {}
        
        for level in self.levels:
            pullback = self.move * level
            entry = self.high_of_day - pullback
            
            # Calculate percentage distance from previous close
            percent_from_support = ((entry - self.prev_close) / abs(self.move)) * 100 if self.move != 0 else 0
            
            result[f'{level:.3f}'] = {
                'level': level,
                'level_percent': round(level * 100, 1),  # For display: 38.2, 50.0, etc.
                'move': round(self.move, 4),
                'pullback': round(pullback, 4),
                'entry': round(entry, 4),
                'high_of_day': round(self.high_of_day, 4),
                'prev_close': round(self.prev_close, 4),
                'percent_from_support': round(percent_from_support, 2),
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
                'risk_reward_ratio': reward/risk ratio,
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
            'level_percent': round(level * 100, 1),
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


class RiskRewardEvaluator:
    """
    Evaluates Fibonacci levels based on risk/reward characteristics.
    
    Scores each Fibonacci level considering:
    - Risk/reward ratio quality (prefer 2:1 or better)
    - Distance from entry point (avoid entry too close to support/resistance)
    - Proximity to psychological price levels
    - Recent technical context (peaks, valleys, moving averages)
    """
    
    def __init__(self):
        """Initialize the risk/reward evaluator."""
        self.min_reward_risk_ratio = 1.5  # Minimum acceptable R:R ratio
        self.ideal_reward_risk_ratio = 2.0  # Ideal R:R ratio
        self.risk_tolerance_pct = 2.0  # Acceptable risk per trade as % of move
    
    def score_level(self, fib_level: dict, current_price: float, 
                   recent_high: Optional[float] = None, recent_low: Optional[float] = None) -> dict:
        """
        Score a Fibonacci level for quality.
        
        Args:
            fib_level: Dictionary from calculate_levels() with level info
            current_price: Current market price
            recent_high: Recent high (e.g., 5-day or 20-day high)
            recent_low: Recent low
        
        Returns:
            Dict with scoring details and overall score (0-100)
        """
        score = 50  # Base score
        scores_breakdown = {}
        
        level = fib_level['level']
        entry = fib_level['entry']
        move = fib_level['move']
        
        # 1. Distance from current price (0-20 points)
        # Closer to current price = more actionable
        distance_pct = abs(entry - current_price) / current_price * 100
        if distance_pct < 1:
            scores_breakdown['price_proximity'] = 20
        elif distance_pct < 2:
            scores_breakdown['price_proximity'] = 18
        elif distance_pct < 3:
            scores_breakdown['price_proximity'] = 15
        elif distance_pct < 5:
            scores_breakdown['price_proximity'] = 12
        else:
            scores_breakdown['price_proximity'] = max(5, 20 - distance_pct)
        
        # 2. Level quality (0-20 points)
        # Prefer mid-range levels (38.2%, 50%, 61.8%)
        if 0.38 <= level <= 0.68:
            scores_breakdown['level_quality'] = 20
        elif level in [0.236, 0.786]:
            scores_breakdown['level_quality'] = 15
        elif level == 1.0:
            scores_breakdown['level_quality'] = 10  # 100% is last resort
        else:
            scores_breakdown['level_quality'] = 12
        
        # 3. Recent context (0-20 points)
        # Check if entry is near recent technical levels
        context_score = 10
        if recent_high and entry < recent_high:
            context_score += 5
        if recent_low and entry > recent_low:
            context_score += 5
        scores_breakdown['technical_context'] = min(20, context_score)
        
        # 4. Position in support/resistance zone (0-20 points)
        # Prefer levels away from extremes
        percent_from_support = fib_level.get('percent_from_support', 50)
        if 30 <= percent_from_support <= 70:
            scores_breakdown['zone_quality'] = 20
        elif 20 <= percent_from_support <= 80:
            scores_breakdown['zone_quality'] = 15
        else:
            scores_breakdown['zone_quality'] = 10
        
        # 5. Distance from extreme (0-20 points)
        # Don't want to enter right at the high or low
        if 10 <= percent_from_support <= 90:
            scores_breakdown['entry_safety'] = 20
        elif 5 <= percent_from_support <= 95:
            scores_breakdown['entry_safety'] = 15
        else:
            scores_breakdown['entry_safety'] = 8
        
        # Calculate total
        total_score = sum(scores_breakdown.values())
        
        return {
            'level': level,
            'level_percent': fib_level.get('level_percent', level * 100),
            'entry': entry,
            'current_price': current_price,
            'distance_pct': round(distance_pct, 2),
            'total_score': round(total_score, 1),
            'scores': scores_breakdown,
            'recommendation': self._get_recommendation(total_score),
        }
    
    def rank_levels(self, fib_levels: dict, current_price: float,
                   recent_high: Optional[float] = None, 
                   recent_low: Optional[float] = None) -> list:
        """
        Rank all Fibonacci levels by quality score.
        
        Args:
            fib_levels: Dictionary from calculate_levels()
            current_price: Current market price
            recent_high: Recent high price
            recent_low: Recent low price
        
        Returns:
            List of scored levels sorted by quality (best first)
        """
        scored_levels = []
        
        for level_key, level_data in fib_levels.items():
            scored = self.score_level(level_data, current_price, recent_high, recent_low)
            scored_levels.append(scored)
        
        # Sort by total_score descending (best first)
        scored_levels.sort(key=lambda x: x['total_score'], reverse=True)
        
        return scored_levels
    
    @staticmethod
    def _get_recommendation(score: float) -> str:
        """Get recommendation based on score."""
        if score >= 85:
            return "Excellent - High confidence entry"
        elif score >= 70:
            return "Good - Viable entry point"
        elif score >= 55:
            return "Fair - Consider alternatives first"
        elif score >= 40:
            return "Weak - Better levels may exist"
        else:
            return "Poor - Avoid this level"


class FibonacciGapPullbackAnalyzer:
    """
    Comprehensive Fibonacci gap pullback analyzer with recent peak/valley context.
    
    Analyzes gap pullback moves with intelligent level selection:
    - For LONG trades: Uses recent daily peak from X-period lookback
    - For SHORT trades: Uses recent daily low from X-period lookback
    - Scores Fibonacci levels by risk/reward
    - Returns actionable trading setups
    """
    
    def __init__(self, lookback_days: int = 20):
        """
        Initialize gap pullback analyzer.
        
        Args:
            lookback_days: Number of days to look back for recent peaks/valleys
        """
        self.lookback_days = lookback_days
        self.evaluator = RiskRewardEvaluator()
    
    def analyze_gap_pullback(self, prev_close: float, today_high: float, today_low: float,
                           current_price: float, recent_daily_data: list, 
                           trade_direction: str = 'long') -> dict:
        """
        Analyze gap pullback setup for longs or shorts.
        
        Args:
            prev_close: Previous day's close
            today_high: Today's high of day
            today_low: Today's low of day
            current_price: Current intraday price
            recent_daily_data: List of dicts with recent daily OHLC data
                             Expected keys: 'date', 'open', 'high', 'low', 'close'
            trade_direction: 'long' or 'short'
        
        Returns:
            Dict with:
            - gap_analysis: Basic gap info
            - recent_context: Recent peak/valley data
            - fib_levels: All calculated levels
            - ranked_levels: Levels ranked by quality
            - recommended_setup: Best level to trade
        """
        
        gap_analysis = self._analyze_gap(prev_close, today_high, today_low, trade_direction)
        
        if gap_analysis['gap_size'] == 0:
            return {
                'error': 'No significant gap detected',
                'gap_analysis': gap_analysis,
            }
        
        # Get recent peak/valley context
        recent_context = self._get_recent_context(recent_daily_data, trade_direction)
        
        # Calculate Fibonacci levels
        if trade_direction == 'long':
            # For longs: high is the resistance, prev_close is support
            fib_calc = FibonacciCalculator(prev_close, today_high)
        else:
            # For shorts: low is the resistance (downside), prev_close is support (upside)
            fib_calc = FibonacciCalculator(today_low, prev_close)
        
        fib_levels = fib_calc.calculate_levels()
        
        # Score and rank levels
        ranked_levels = self.evaluator.rank_levels(
            fib_levels, 
            current_price, 
            recent_context['recent_high'],
            recent_context['recent_low']
        )
        
        # Determine recommended setup
        recommended_setup = self._select_best_setup(ranked_levels, gap_analysis, recent_context)
        
        return {
            'trade_direction': trade_direction,
            'gap_analysis': gap_analysis,
            'recent_context': recent_context,
            'fib_levels': fib_levels,
            'ranked_levels': ranked_levels,
            'recommended_setup': recommended_setup,
            'analysis_timestamp': pd.Timestamp.now().isoformat(),
        }
    
    @staticmethod
    def _analyze_gap(prev_close: float, today_high: float, today_low: float, 
                     direction: str) -> dict:
        """Analyze gap characteristics."""
        if direction == 'long':
            gap_size = today_high - prev_close
            gap_pct = (gap_size / prev_close) * 100 if prev_close != 0 else 0
            gap_type = 'up' if gap_size > 0 else 'down'
        else:
            gap_size = prev_close - today_low
            gap_pct = (gap_size / prev_close) * 100 if prev_close != 0 else 0
            gap_type = 'down' if gap_size > 0 else 'up'
        
        return {
            'prev_close': round(prev_close, 2),
            'today_high': round(today_high, 2),
            'today_low': round(today_low, 2),
            'gap_size': round(abs(gap_size), 2),
            'gap_pct': round(gap_pct, 2),
            'gap_type': gap_type,
            'is_valid_gap': abs(gap_pct) >= 1.0,  # Minimum 1% gap
        }
    
    def _get_recent_context(self, daily_data: list, direction: str) -> dict:
        """Get recent peak/valley context."""
        if not daily_data:
            return {
                'recent_high': None,
                'recent_low': None,
                'recent_peak_date': None,
                'recent_valley_date': None,
                'lookback_days': self.lookback_days,
            }
        
        # Sort and limit to lookback period
        sorted_data = sorted(daily_data, key=lambda x: x.get('date', ''))
        if len(sorted_data) > self.lookback_days:
            sorted_data = sorted_data[-self.lookback_days:]
        
        # Find recent high and low
        recent_high = None
        recent_low = None
        recent_peak_date = None
        recent_valley_date = None
        
        for candle in sorted_data:
            high = float(candle.get('high', 0))
            low = float(candle.get('low', 0))
            date = candle.get('date', '')
            
            if recent_high is None or high > recent_high:
                recent_high = high
                recent_peak_date = date
            
            if recent_low is None or low < recent_low:
                recent_low = low
                recent_valley_date = date
        
        return {
            'recent_high': recent_high,
            'recent_low': recent_low,
            'recent_peak_date': recent_peak_date,
            'recent_valley_date': recent_valley_date,
            'lookback_days': self.lookback_days,
        }
    
    @staticmethod
    def _select_best_setup(ranked_levels: list, gap_analysis: dict, 
                          recent_context: dict) -> dict:
        """Select the best trading setup from ranked levels."""
        if not ranked_levels:
            return {'error': 'No valid levels to rank'}
        
        best_level = ranked_levels[0]
        
        return {
            'recommended_level': best_level['level_percent'],
            'entry_price': best_level['entry'],
            'confidence_score': best_level['total_score'],
            'recommendation': best_level['recommendation'],
            'gap_size': gap_analysis['gap_size'],
            'gap_pct': gap_analysis['gap_pct'],
            'distance_from_current': best_level['distance_pct'],
            'alternative_levels': ranked_levels[1:4] if len(ranked_levels) > 1 else [],
            'recent_peak_context': recent_context['recent_high'],
            'recent_valley_context': recent_context['recent_low'],
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


class CandlestickIndicator:
    """
    Candlestick pattern indicator that tracks high/low lookback data.
    
    Useful for:
    - Finding recent highs and lows over a lookback period
    - Detecting breakouts above/below candle ranges
    - Setting limit prices based on candlestick patterns
    - Hold order entry/exit conditions
    """
    
    def __init__(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                 lookback_bars: int = 5):
        """
        Initialize candlestick indicator.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            lookback_bars: Number of bars to look back for high/low
        """
        self.high = high
        self.low = low
        self.close = close
        self.lookback_bars = int(lookback_bars)
    
    def get_lookback_high(self) -> pd.Series:
        """Get the rolling highest high over lookback period."""
        return self.high.rolling(window=self.lookback_bars, min_periods=1).max()
    
    def get_lookback_low(self) -> pd.Series:
        """Get the rolling lowest low over lookback period."""
        return self.low.rolling(window=self.lookback_bars, min_periods=1).min()
    
    def get_lookback_range(self) -> pd.Series:
        """Get the rolling range (high - low) over lookback period."""
        return self.get_lookback_high() - self.get_lookback_low()
    
    def get_recent_high_low(self) -> dict:
        """
        Get the most recent lookback high and low.
        
        Returns:
            Dict with keys 'lookback_high' and 'lookback_low'
        """
        if len(self.high) < 1:
            return {'lookback_high': None, 'lookback_low': None}
        
        lookback_high = self.get_lookback_high().iloc[-1]
        lookback_low = self.get_lookback_low().iloc[-1]
        
        # Handle NaN values
        if pd.isna(lookback_high):
            lookback_high = None
        if pd.isna(lookback_low):
            lookback_low = None
        
        return {
            'lookback_high': lookback_high,
            'lookback_low': lookback_low,
            'current_price': self.close.iloc[-1] if len(self.close) > 0 else None,
            'lookback_range': lookback_high - lookback_low if (lookback_high is not None and lookback_low is not None) else None,
        }
    
    def is_above_lookback_high(self, offset_pct: float = 0.0) -> bool:
        """
        Check if current price is above recent lookback high (with optional offset).
        
        Args:
            offset_pct: Percentage offset above high (positive = above, negative = below)
        
        Returns:
            True if price is above (high + offset)
        """
        if len(self.close) < 1 or len(self.high) < 1:
            return False
        
        current_price = self.close.iloc[-1]
        lookback_high = self.get_lookback_high().iloc[-1]
        
        if pd.isna(lookback_high) or pd.isna(current_price):
            return False
        
        threshold = lookback_high * (1 + offset_pct / 100.0)
        return current_price > threshold
    
    def is_below_lookback_low(self, offset_pct: float = 0.0) -> bool:
        """
        Check if current price is below recent lookback low (with optional offset).
        
        Args:
            offset_pct: Percentage offset below low (negative = below, positive = above)
        
        Returns:
            True if price is below (low - offset)
        """
        if len(self.close) < 1 or len(self.low) < 1:
            return False
        
        current_price = self.close.iloc[-1]
        lookback_low = self.get_lookback_low().iloc[-1]
        
        if pd.isna(lookback_low) or pd.isna(current_price):
            return False
        
        threshold = lookback_low * (1 - offset_pct / 100.0)
        return current_price < threshold
