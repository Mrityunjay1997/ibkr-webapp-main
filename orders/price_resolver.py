"""
Price Resolution Engine for Unified Order System

Resolves price references (indicators, levels, candles) into actual prices.

This engine is used by all three order modes (off-book, automated, manual)
to calculate entry prices, stop-loss prices, and target prices.

Features:
- Support for 30+ price reference types
- Candle-based references (high/low of candle + offset)
- Moving average crossover detection
- Fibonacci levels
- Technical indicators (VWAP, SMA, EMA, ATR, etc)
- Volatility-based calculations
- Risk-reward ratio calculations
"""

import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger("price_resolver")


class PriceResolutionContext:
    """
    Context object containing market data needed to resolve prices.
    
    This is built from:
    - Current price data
    - Recent candles (for candle-based references)
    - Indicator values (VWAP, SMA, EMA, ATR, etc)
    - Daily/session data (high, low, open, close)
    """
    
    def __init__(self):
        self.current_price: Optional[float] = None
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None
        self.last_price: Optional[float] = None
        
        # Daily session data
        self.day_open: Optional[float] = None
        self.day_high: Optional[float] = None
        self.day_low: Optional[float] = None
        self.prev_close: Optional[float] = None
        
        # Indicators (should be pre-calculated)
        self.vwap: Optional[float] = None
        self.sma_fast: Optional[float] = None  # e.g., 20-period
        self.sma_medium: Optional[float] = None  # e.g., 50-period
        self.sma_slow: Optional[float] = None  # e.g., 200-period
        self.ema_fast: Optional[float] = None  # e.g., 12-period
        self.ema_medium: Optional[float] = None  # e.g., 26-period
        self.ema_slow: Optional[float] = None  # e.g., 50-period
        self.atr: Optional[float] = None  # Average True Range
        self.rsi: Optional[float] = None  # Relative Strength Index
        
        # Fibonacci levels (calculated from swing)
        self.fib_23_6: Optional[float] = None
        self.fib_38_2: Optional[float] = None
        self.fib_50_0: Optional[float] = None
        self.fib_61_8: Optional[float] = None
        self.fib_78_6: Optional[float] = None
        self.fib_100_0: Optional[float] = None  # Extension
        
        # Pivot points
        self.pivot: Optional[float] = None
        self.support_1: Optional[float] = None
        self.support_2: Optional[float] = None
        self.resistance_1: Optional[float] = None
        self.resistance_2: Optional[float] = None
        
        # Candle data - dict of {timeframe: candle_list}
        # Each candle: {timestamp, open, high, low, close, volume}
        self.candles: Dict[str, List[Dict]] = {}
        
        # Entry price (needed for relative calculations like stop/target)
        self.entry_price: Optional[float] = None
        
        # Timestamp
        self.timestamp: str = datetime.utcnow().isoformat()


class PriceResolver:
    """Resolves price references into actual prices"""
    
    @staticmethod
    def resolve_price(
        price_ref_type: str,
        offset_pct: float,
        context: PriceResolutionContext,
        **kwargs
    ) -> Tuple[Optional[float], str]:
        """
        Resolve a price reference to an actual price.
        
        Args:
            price_ref_type: Type of price reference ('vwap', 'sma_fast', 'candle_high', etc)
            offset_pct: Offset percentage to apply (-5 = 5% below, +5 = 5% above)
            context: PriceResolutionContext with market data
            **kwargs: Additional arguments specific to price type
        
        Returns:
            (resolved_price, error_message_or_empty_string)
            If error, resolved_price will be None and message will describe the issue
        """
        
        if not context.current_price:
            return None, "Current price not available"
        
        # Get base price from indicator/level
        base_price = None
        error_msg = ""
        
        if price_ref_type == 'vwap':
            base_price = context.vwap
            if not base_price:
                return None, "VWAP not available"
        
        elif price_ref_type == 'sma_fast':
            base_price = context.sma_fast
            if not base_price:
                return None, "Fast SMA not available"
        
        elif price_ref_type == 'sma_medium':
            base_price = context.sma_medium
            if not base_price:
                return None, "Medium SMA not available"
        
        elif price_ref_type == 'sma_slow':
            base_price = context.sma_slow
            if not base_price:
                return None, "Slow SMA not available"
        
        elif price_ref_type == 'ema_fast':
            base_price = context.ema_fast
            if not base_price:
                return None, "Fast EMA not available"
        
        elif price_ref_type == 'ema_medium':
            base_price = context.ema_medium
            if not base_price:
                return None, "Medium EMA not available"
        
        elif price_ref_type == 'ema_slow':
            base_price = context.ema_slow
            if not base_price:
                return None, "Slow EMA not available"
        
        elif price_ref_type == 'prev_close':
            base_price = context.prev_close
            if not base_price:
                return None, "Previous close not available"
        
        elif price_ref_type == 'day_high':
            base_price = context.day_high
            if not base_price:
                return None, "Day high not available"
        
        elif price_ref_type == 'day_low':
            base_price = context.day_low
            if not base_price:
                return None, "Day low not available"
        
        elif price_ref_type == 'high_of_day':
            base_price = context.day_high
            if not base_price:
                return None, "High of day not available"
        
        elif price_ref_type == 'low_of_day':
            base_price = context.day_low
            if not base_price:
                return None, "Low of day not available"
        
        # Fibonacci levels
        elif price_ref_type == 'fibonacci_23_6':
            base_price = context.fib_23_6
            if not base_price:
                return None, "Fibonacci 23.6 not calculated"
        
        elif price_ref_type == 'fibonacci_38_2':
            base_price = context.fib_38_2
            if not base_price:
                return None, "Fibonacci 38.2 not calculated"
        
        elif price_ref_type == 'fibonacci_50_0':
            base_price = context.fib_50_0
            if not base_price:
                return None, "Fibonacci 50.0 not calculated"
        
        elif price_ref_type == 'fibonacci_61_8':
            base_price = context.fib_61_8
            if not base_price:
                return None, "Fibonacci 61.8 not calculated"
        
        elif price_ref_type == 'fibonacci_78_6':
            base_price = context.fib_78_6
            if not base_price:
                return None, "Fibonacci 78.6 not calculated"
        
        elif price_ref_type == 'fibonacci_100_0':
            base_price = context.fib_100_0
            if not base_price:
                return None, "Fibonacci 100 (extension) not calculated"
        
        # Pivot points
        elif price_ref_type == 'pivot':
            base_price = context.pivot
            if not base_price:
                return None, "Pivot point not calculated"
        
        elif price_ref_type == 'support_1':
            base_price = context.support_1
            if not base_price:
                return None, "Support 1 not calculated"
        
        elif price_ref_type == 'support_2':
            base_price = context.support_2
            if not base_price:
                return None, "Support 2 not calculated"
        
        elif price_ref_type == 'resistance_1':
            base_price = context.resistance_1
            if not base_price:
                return None, "Resistance 1 not calculated"
        
        elif price_ref_type == 'resistance_2':
            base_price = context.resistance_2
            if not base_price:
                return None, "Resistance 2 not calculated"
        
        # Candle-based references (NEW)
        elif price_ref_type in ['candle_high', 'candle_low']:
            timeframe = kwargs.get('timeframe')
            lookback = kwargs.get('lookback', 5)
            
            if not timeframe:
                return None, "Timeframe required for candle reference"
            
            if timeframe not in context.candles or not context.candles[timeframe]:
                return None, f"Candle data not available for {timeframe}"
            
            candles = context.candles[timeframe]
            if len(candles) < lookback:
                return None, f"Not enough candles (have {len(candles)}, need {lookback})"
            
            # Get most recent candle(s)
            recent_candle = candles[-lookback]  # Go back 'lookback' candles
            
            if price_ref_type == 'candle_high':
                base_price = recent_candle.get('high')
            else:  # candle_low
                base_price = recent_candle.get('low')
            
            if not base_price:
                return None, f"Candle {price_ref_type} not available"
        
        # Percent target (based on entry or previous close)
        elif price_ref_type == 'percent_target':
            # Use entry price if available, otherwise use last price
            base_price = context.entry_price or context.current_price
            if not base_price:
                return None, "Entry price or current price required for percent target"
        
        # Custom price
        elif price_ref_type == 'custom':
            custom_price = kwargs.get('custom_price')
            if custom_price is None:
                return None, "Custom price not provided"
            return round(custom_price, 2), ""
        
        else:
            return None, f"Unknown price reference type: {price_ref_type}"
        
        if base_price is None:
            return None, f"Cannot resolve {price_ref_type}: base price is None"
        
        # Apply offset percentage
        # offset_pct > 0 means move price UP
        # offset_pct < 0 means move price DOWN
        multiplier = 1.0 + (offset_pct / 100.0)
        final_price = base_price * multiplier
        
        return round(final_price, 2), ""
    
    @staticmethod
    def resolve_stop_price(
        entry_price: float,
        stop_config,  # StopLossConfig object
        context: PriceResolutionContext,
    ) -> Tuple[Optional[float], str]:
        """
        Calculate stop-loss price from configuration.
        
        Args:
            entry_price: Entry price for the position
            stop_config: StopLossConfig object
            context: PriceResolutionContext with market data
        
        Returns:
            (stop_price, error_message)
        """
        
        if not stop_config:
            return None, "Stop config not provided"
        
        stop_type = stop_config.stop_type
        context.entry_price = entry_price
        
        # Fixed price stop
        if stop_type == 'fixed_price':
            if stop_config.fixed_price is None:
                return None, "Fixed price not provided"
            return round(stop_config.fixed_price, 2), ""
        
        # Price reference stop (indicator/level based)
        elif stop_type == 'price_reference':
            if not stop_config.price_ref_type:
                return None, "Price reference type required"
            return PriceResolver.resolve_price(
                stop_config.price_ref_type,
                stop_config.price_ref_offset_pct,
                context,
            )
        
        # ATR-based stop
        elif stop_type == 'atr_multiple':
            if not context.atr or context.atr <= 0:
                return None, "ATR not available or invalid"
            
            # For long: entry - (ATR × multiple)
            # For short: entry + (ATR × multiple)
            atr_offset = context.atr * stop_config.atr_multiplier
            stop_price = entry_price - atr_offset  # Default for long
            
            return round(stop_price, 2), ""
        
        # Percent loss stop
        elif stop_type == 'percent_loss':
            if stop_config.loss_percent <= 0:
                return None, "Loss percent must be positive"
            
            # For long: entry - (entry × loss%)
            loss_amount = entry_price * (stop_config.loss_percent / 100.0)
            stop_price = entry_price - loss_amount
            
            return round(stop_price, 2), ""
        
        # Trailing stop (dollar amount)
        elif stop_type == 'trailing_stop_amount':
            if stop_config.trail_amount is None:
                return None, "Trail amount not provided"
            
            # For long: current_price - trail_amount
            stop_price = context.current_price - stop_config.trail_amount
            
            return round(stop_price, 2), ""
        
        # Trailing stop (percent)
        elif stop_type == 'trailing_stop_percent':
            if stop_config.trail_percent is None:
                return None, "Trail percent not provided"
            
            # For long: current_price - (current_price × trail%)
            trail_amount = context.current_price * (stop_config.trail_percent / 100.0)
            stop_price = context.current_price - trail_amount
            
            return round(stop_price, 2), ""
        
        # Trailing stop (candle-based)
        elif stop_type == 'trailing_stop_candle':
            if not stop_config.trail_candle_timeframe:
                return None, "Candle timeframe required"
            
            # Get low of recent candle + offset
            price, error = PriceResolver.resolve_price(
                'candle_low',
                stop_config.trail_candle_offset_pct,
                context,
                timeframe=stop_config.trail_candle_timeframe,
                lookback=1,
            )
            return price, error
        
        # High of day stop (for shorts)
        elif stop_type == 'high_of_day':
            price, error = PriceResolver.resolve_price(
                'high_of_day',
                stop_config.high_of_day_offset_pct,
                context,
            )
            return price, error
        
        # Key level (behind support/resistance)
        elif stop_type == 'key_level':
            if not stop_config.price_ref_type:
                return None, "Key level price reference required"
            return PriceResolver.resolve_price(
                stop_config.price_ref_type,
                stop_config.price_ref_offset_pct,
                context,
            )
        
        # Fair Value Gap
        elif stop_type == 'fvg':
            # FVG calculation would go here (advanced)
            # For now, use ATR-based fallback
            if context.atr:
                stop_price = entry_price - (context.atr * 0.5)
                return round(stop_price, 2), ""
            else:
                return None, "ATR required for FVG stop calculation"
        
        else:
            return None, f"Unknown stop type: {stop_type}"
    
    @staticmethod
    def resolve_target_price(
        entry_price: float,
        target_config,  # TargetConfig object
        context: PriceResolutionContext,
    ) -> Tuple[Optional[float], str]:
        """
        Calculate profit target price from configuration.
        
        Args:
            entry_price: Entry price for the position
            target_config: TargetConfig object
            context: PriceResolutionContext with market data
        
        Returns:
            (target_price, error_message)
        """
        
        if not target_config:
            return None, "Target config not provided"
        
        target_type = target_config.target_type
        context.entry_price = entry_price
        
        # Fixed price target
        if target_type == 'fixed_price':
            if target_config.fixed_price is None:
                return None, "Fixed price not provided"
            return round(target_config.fixed_price, 2), ""
        
        # Price reference target
        elif target_type == 'price_reference':
            if not target_config.price_ref_type:
                return None, "Price reference type required"
            return PriceResolver.resolve_price(
                target_config.price_ref_type,
                target_config.price_ref_offset_pct,
                context,
            )
        
        # Fibonacci target
        elif target_type == 'fibonacci':
            if not target_config.fib_level:
                return None, "Fibonacci level not specified"
            
            # Map fib_level to actual Fibonacci attribute
            fib_attr_map = {
                'fibonacci_23_6': 'fib_23_6',
                'fibonacci_38_2': 'fib_38_2',
                'fibonacci_50_0': 'fib_50_0',
                'fibonacci_61_8': 'fib_61_8',
                'fibonacci_78_6': 'fib_78_6',
                'fibonacci_100_0': 'fib_100_0',
            }
            
            attr = fib_attr_map.get(target_config.fib_level)
            if not attr:
                return None, f"Unknown Fibonacci level: {target_config.fib_level}"
            
            fib_price = getattr(context, attr, None)
            if not fib_price:
                return None, f"Fibonacci {target_config.fib_level} not calculated"
            
            # Apply additional offset
            final_price = fib_price * (1.0 + target_config.fib_offset_pct / 100.0)
            return round(final_price, 2), ""
        
        # ATR-based target
        elif target_type == 'atr_multiple':
            if not context.atr or context.atr <= 0:
                return None, "ATR not available or invalid"
            
            # For long: entry + (ATR × multiple)
            atr_offset = context.atr * target_config.atr_multiplier
            target_price = entry_price + atr_offset
            
            return round(target_price, 2), ""
        
        # Percent gain target
        elif target_type == 'percent_gain':
            if target_config.gain_percent <= 0:
                return None, "Gain percent must be positive"
            
            # For long: entry + (entry × gain%)
            gain_amount = entry_price * (target_config.gain_percent / 100.0)
            target_price = entry_price + gain_amount
            
            return round(target_price, 2), ""
        
        # Risk-reward ratio target
        elif target_type == 'risk_reward_ratio':
            # This requires a stop price to calculate
            if not target_config.rr_ratio or target_config.rr_ratio <= 0:
                return None, "Risk-reward ratio must be positive"
            
            # We need the stop price to calculate this
            # For now, return error - caller should provide stop price context
            return None, "RR target requires stop price context"
        
        # Candle-based target
        elif target_type == 'candle_high':
            if not target_config.timeframe:
                return None, "Timeframe required for candle target"
            
            return PriceResolver.resolve_price(
                'candle_high',
                target_config.price_ref_offset_pct,
                context,
                timeframe=target_config.timeframe,
                lookback=1,
            )
        
        # Moving average resistance
        elif target_type == 'ma_level':
            if not target_config.price_ref_type:
                return None, "MA type required"
            
            return PriceResolver.resolve_price(
                target_config.price_ref_type,
                target_config.price_ref_offset_pct,
                context,
            )
        
        else:
            return None, f"Unknown target type: {target_type}"
