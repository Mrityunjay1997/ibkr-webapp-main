"""
Dynamic Indicator Management Module

Handles parsing, validation, and execution of dynamically configured indicators.
Replaces the hardcoded indicator logic with a flexible configuration-based system.
"""

import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from indicators import (
    SMAIndicator, EMAIndicator, RSIIndicator, OBVIndicator,
    FastOBVIndicator, MediumOBVIndicator, SlowOBVIndicator,
    ATRIndicator, VolumeWeightedAveragePrice, last_value
)

logger = logging.getLogger(__name__)


class DynamicIndicatorConfig:
    """Parses and manages dynamic indicator configuration."""
    
    def __init__(self, config_json: str = "[]"):
        """Initialize from JSON configuration string."""
        self.indicators: List[Dict[str, Any]] = []
        self.load_from_json(config_json)
    
    def load_from_json(self, config_json: str):
        """Load configuration from JSON string."""
        try:
            if not config_json or config_json.strip() in ("", "[]", "null"):
                self.indicators = []
            else:
                data = json.loads(config_json)
                self.indicators = data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Error parsing indicator config: {e}")
            self.indicators = []
    
    def get_enabled_indicators(self) -> List[Dict[str, Any]]:
        """Get all enabled indicators (comparison != 'disabled')."""
        return [
            i for i in self.indicators
            if i.get('enabled', True) and i.get('comparison') != 'disabled'
        ]
    
    def validate(self) -> tuple[bool, str]:
        """Validate configuration. Returns (is_valid, error_message)."""
        if not self.indicators:
            return True, ""  # Empty config is valid
        
        for idx, ind in enumerate(self.indicators):
            # Check required fields
            required = ['type', 'window', 'comparison']
            for field in required:
                if field not in ind:
                    return False, f"Indicator {idx}: missing '{field}'"
            
            # Validate type
            valid_types = [
                'FastSMA', 'MediumSMA', 'SlowSMA', 'SMA1', 'SMA2', 'SMA3',
                'FastEMA', 'SlowEMA', 'EMA1', 'EMA2',
                'RSI', 'VWAP', 'OBV', 'FastOBV', 'MediumOBV', 'SlowOBV',
                'ATR', 'Candlestick1', 'Candlestick2', 'Candlestick3', 'Candlestick4',
                'PrevClose', 'PctChange', 'LowOfDay', 'HighOfDay'
            ]
            if ind['type'] not in valid_types:
                return False, f"Indicator {idx}: invalid type '{ind['type']}'"
            
            # Validate comparison operator
            valid_ops = [
                'greater', 'greaterEqual', 'lower', 'lowerEqual', 'between',
                'withinPercentAbove', 'withinPercentBelow', 'withinPercentEither',
                'disabled'
            ]
            if ind.get('comparison') not in valid_ops:
                return False, f"Indicator {idx}: invalid comparison '{ind.get('comparison')}'"
        
        return True, ""


def calculate_dynamic_indicators(
    data: List[List],
    config_json: str,
    symbol: str,
    cusip: str,
    net_position: Optional[int] = 0,
    market_cap: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate all indicators from dynamic configuration.
    
    Args:
        data: List of OHLCV bars (date, open, high, low, close, volume)
        config_json: JSON string with indicator configuration
        symbol: Stock symbol
        cusip: CUSIP code
        net_position: Current position size
        market_cap: Company market cap
    
    Returns:
        Dictionary with calculated indicator values
    """
    
    # Parse configuration
    config = DynamicIndicatorConfig(config_json)
    is_valid, error_msg = config.validate()
    
    if not is_valid:
        logger.error(f"Invalid indicator config: {error_msg}")
        return {
            "symbol": symbol,
            "cusip": cusip,
            "netPosition": net_position or 0,
            "error": error_msg
        }
    
    # Build dataframe
    if not data:
        return {
            "symbol": symbol,
            "cusip": cusip,
            "netPosition": net_position or 0,
            "error": "No data"
        }
    
    try:
        df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close", "volume"])
    except Exception as e:
        logger.error(f"Error creating dataframe: {e}")
        return {
            "symbol": symbol,
            "cusip": cusip,
            "netPosition": net_position or 0,
            "error": f"Data error: {e}"
        }
    
    # Initialize results
    results = {
        "symbol": symbol,
        "cusip": cusip,
        "netPosition": int(net_position) if net_position is not None else 0,
    }
    
    # Calculate each enabled indicator
    for indicator in config.get_enabled_indicators():
        try:
            indicator_name = indicator['type']
            window = int(indicator.get('window', 0))
            comparison = indicator.get('comparison', 'disabled')
            percentage = float(indicator.get('percentage', 0))
            use_percentage = indicator.get('usePercentage', False)
            
            # Skip if disabled
            if comparison == 'disabled':
                continue
            
            # Calculate indicator value
            value = _calculate_single_indicator(
                indicator_name, window, df
            )
            
            if value is not None:
                # Store with a unique key (type + index if multiple of same type)
                key = f"{indicator_name}_{indicator.get('id', 0)}"
                results[key] = {
                    "value": value,
                    "percentage": percentage,
                    "usePercentage": use_percentage,
                    "comparison": comparison,
                    "window": window
                }
        
        except Exception as e:
            logger.error(f"Error calculating {indicator['type']}: {e}")
    
    return results


def _calculate_single_indicator(indicator_type: str, window: int, df: pd.DataFrame) -> Optional[float]:
    """Calculate a single indicator value."""
    
    if indicator_type.startswith('SMA'):
        try:
            sma = SMAIndicator(close=df['close'], window=window)
            return last_value(sma.sma_indicator())
        except Exception as e:
            logger.debug(f"SMA calculation error: {e}")
            return None
    
    elif indicator_type.startswith('EMA'):
        try:
            ema = EMAIndicator(close=df['close'], window=window)
            return last_value(ema.ema_indicator())
        except Exception as e:
            logger.debug(f"EMA calculation error: {e}")
            return None
    
    elif indicator_type == 'RSI':
        try:
            rsi = RSIIndicator(df['close'], window=window)
            return last_value(rsi.rsi())
        except Exception as e:
            logger.debug(f"RSI calculation error: {e}")
            return None
    
    elif indicator_type == 'VWAP':
        try:
            vwap = VolumeWeightedAveragePrice(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume'],
                window=window
            )
            return last_value(vwap.volume_weighted_average_price())
        except Exception as e:
            logger.debug(f"VWAP calculation error: {e}")
            return None
    
    elif indicator_type == 'OBV':
        try:
            obv = OBVIndicator(df['close'], df['volume'])
            return last_value(obv.obv())
        except Exception as e:
            logger.debug(f"OBV calculation error: {e}")
            return None
    
    elif indicator_type == 'FastOBV':
        try:
            obv = FastOBVIndicator(df['close'], df['volume'], window=window)
            return last_value(obv.obv())
        except Exception as e:
            logger.debug(f"FastOBV calculation error: {e}")
            return None
    
    elif indicator_type == 'MediumOBV':
        try:
            obv = MediumOBVIndicator(df['close'], df['volume'], window=window)
            return last_value(obv.obv())
        except Exception as e:
            logger.debug(f"MediumOBV calculation error: {e}")
            return None
    
    elif indicator_type == 'SlowOBV':
        try:
            obv = SlowOBVIndicator(df['close'], df['volume'], window=window)
            return last_value(obv.obv())
        except Exception as e:
            logger.debug(f"SlowOBV calculation error: {e}")
            return None
    
    elif indicator_type == 'ATR':
        try:
            atr = ATRIndicator(df['high'], df['low'], df['close'], window=window)
            atr_series = atr.atr()
            val = last_value(atr_series)
            # Debug logging: timeframe inference, bars, window, symbol not available here
            try:
                logger.debug("[DYN-ATR] window=%d bars=%d result=%s", int(window), len(df), val)
            except Exception:
                logger.exception("Failed to log dynamic ATR info")
            return val
        except Exception as e:
            logger.debug(f"ATR calculation error: {e}")
            return None
    
    elif indicator_type == 'PrevClose':
        # Previous close (exclude current last incomplete bar)
        try:
            if len(df) >= 2:
                return float(df['close'].iloc[-2])
            else:
                return float(df['close'].iloc[-1])
        except Exception as e:
            logger.debug(f"PrevClose calculation error: {e}")
            return None
    
    elif indicator_type == 'PctChange':
        # Percentage change from previous close
        try:
            if len(df) >= 2:
                prev_close = float(df['close'].iloc[-2])
                current_close = float(df['close'].iloc[-1])
                return ((current_close - prev_close) / prev_close * 100) if prev_close != 0 else 0
            else:
                return 0
        except Exception as e:
            logger.debug(f"PctChange calculation error: {e}")
            return None
    
    elif indicator_type == 'HighOfDay':
        # Highest price in today's session
        try:
            return float(df['high'].iloc[-window:].max()) if window > 0 else float(df['high'].iloc[-1])
        except Exception as e:
            logger.debug(f"HighOfDay calculation error: {e}")
            return None
    
    elif indicator_type == 'LowOfDay':
        # Lowest price in today's session
        try:
            return float(df['low'].iloc[-window:].min()) if window > 0 else float(df['low'].iloc[-1])
        except Exception as e:
            logger.debug(f"LowOfDay calculation error: {e}")
            return None
    
    else:
        logger.warning(f"Unknown indicator type: {indicator_type}")
        return None


def check_indicator_condition(
    value: float,
    comparison: str,
    threshold: float,
    use_percentage: bool = False
) -> bool:
    """
    Check if indicator value meets the condition.
    
    Args:
        value: Indicator value
        comparison: Comparison operator
        threshold: Threshold value
        use_percentage: If True, threshold is percentage; if False, absolute value
    
    Returns:
        True if condition is met, False otherwise
    """
    
    if pd.isna(value) or pd.isna(threshold):
        return False
    
    # Convert percentage to absolute if needed
    if use_percentage and value != 0:
        threshold_abs = value * (threshold / 100)
    else:
        threshold_abs = threshold
    
    if comparison == 'greater':
        return value > threshold_abs
    elif comparison == 'greaterEqual':
        return value >= threshold_abs
    elif comparison == 'lower':
        return value < threshold_abs
    elif comparison == 'lowerEqual':
        return value <= threshold_abs
    elif comparison == 'withinPercentAbove':
        return value >= threshold_abs and value <= threshold_abs * (1 + threshold / 100)
    elif comparison == 'withinPercentBelow':
        return value <= threshold_abs and value >= threshold_abs * (1 - threshold / 100)
    elif comparison == 'withinPercentEither':
        return abs(value - threshold_abs) <= (threshold_abs * threshold / 100)
    elif comparison == 'between':
        # For between, we'd need min and max values (second value)
        return True  # Placeholder
    
    return False
