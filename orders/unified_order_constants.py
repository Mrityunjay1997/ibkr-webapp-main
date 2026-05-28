"""
Unified Order System - Consolidated Constants and Options

This module consolidates all price reference options, stop strategies, target strategies,
and other configuration options from off-book orders, automated orders, and manual orders
into a single canonical source.

This eliminates duplication and ensures consistency across all order modes.
"""

# =============================================================================
# PRICE REFERENCE TYPES
# =============================================================================
# These define WHERE an order can be placed (entry/stop/target)

PRICE_REFERENCE_TYPES = {
    # Indicator-based references
    'vwap': {
        'label': 'VWAP',
        'category': 'indicator',
        'requires_offset': True,
        'description': 'Volume Weighted Average Price',
    },
    'sma_fast': {
        'label': 'Fast SMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 20,
    },
    'sma_medium': {
        'label': 'Medium SMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 50,
    },
    'sma_slow': {
        'label': 'Slow SMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 200,
    },
    'ema_fast': {
        'label': 'Fast EMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 12,
    },
    'ema_medium': {
        'label': 'Medium EMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 26,
    },
    'ema_slow': {
        'label': 'Slow EMA',
        'category': 'indicator',
        'requires_offset': True,
        'requires_period': True,
        'default_period': 50,
    },
    
    # Fibonacci levels
    'fibonacci_23_6': {
        'label': 'Fibonacci 23.6%',
        'category': 'fibonacci',
        'requires_offset': True,
        'description': 'First Fibonacci retracement level',
    },
    'fibonacci_38_2': {
        'label': 'Fibonacci 38.2%',
        'category': 'fibonacci',
        'requires_offset': True,
    },
    'fibonacci_50_0': {
        'label': 'Fibonacci 50.0%',
        'category': 'fibonacci',
        'requires_offset': True,
    },
    'fibonacci_61_8': {
        'label': 'Fibonacci 61.8%',
        'category': 'fibonacci',
        'requires_offset': True,
        'description': 'Golden ratio - most important Fibonacci level',
    },
    'fibonacci_78_6': {
        'label': 'Fibonacci 78.6%',
        'category': 'fibonacci',
        'requires_offset': True,
    },
    'fibonacci_100_0': {
        'label': 'Fibonacci 100% (Extension)',
        'category': 'fibonacci',
        'requires_offset': True,
        'description': 'Full range - used for extended targets',
    },
    
    # Pivot points
    'pivot': {
        'label': 'Pivot Point',
        'category': 'pivot',
        'requires_offset': True,
    },
    'support_1': {
        'label': 'Support 1',
        'category': 'pivot',
        'requires_offset': True,
    },
    'support_2': {
        'label': 'Support 2',
        'category': 'pivot',
        'requires_offset': True,
    },
    'resistance_1': {
        'label': 'Resistance 1',
        'category': 'pivot',
        'requires_offset': True,
    },
    'resistance_2': {
        'label': 'Resistance 2',
        'category': 'pivot',
        'requires_offset': True,
    },
    
    # Price levels and candles
    'prev_close': {
        'label': 'Previous Close',
        'category': 'price_level',
        'requires_offset': True,
    },
    'day_high': {
        'label': 'Today High',
        'category': 'price_level',
        'requires_offset': True,
    },
    'day_low': {
        'label': 'Today Low',
        'category': 'price_level',
        'requires_offset': True,
    },
    'high_of_day': {
        'label': 'High of Day (for shorts)',
        'category': 'price_level',
        'requires_offset': True,
        'description': 'Used for short stops - typically above entry',
    },
    'low_of_day': {
        'label': 'Low of Day (for longs)',
        'category': 'price_level',
        'requires_offset': True,
        'description': 'Used for long stops - typically below entry',
    },
    
    # Candle-based (NEW - from off-book orders)
    'candle_high': {
        'label': 'Candle High',
        'category': 'candle',
        'requires_offset': True,
        'requires_timeframe': True,
        'requires_lookback': True,
        'description': 'High of recent candle + offset',
    },
    'candle_low': {
        'label': 'Candle Low',
        'category': 'candle',
        'requires_offset': True,
        'requires_timeframe': True,
        'requires_lookback': True,
        'description': 'Low of recent candle + offset',
    },
    
    # Percent-based
    'percent_target': {
        'label': 'Percent Target',
        'category': 'percent',
        'requires_offset': True,
        'description': '% above/below a reference price',
    },
    
    # Custom
    'custom': {
        'label': 'Custom Price',
        'category': 'custom',
        'requires_custom_price': True,
        'description': 'Manually entered price',
    },
}


# =============================================================================
# ENTRY CONDITION TYPES
# =============================================================================
# These define HOW an order gets triggered (off-book conditions)

ENTRY_CONDITION_TYPES = {
    'immediate': {
        'label': 'Immediate (Market/Limit)',
        'description': 'Place order immediately',
    },
    'candle_breakout': {
        'label': 'Candle Breakout',
        'description': 'Trigger when price breaks above/below recent candle high/low',
        'requires': ['timeframe', 'lookback', 'break_direction', 'offset_pct'],
    },
    'ma_crossover': {
        'label': 'Moving Average Crossover',
        'description': 'Trigger when price crosses above/below moving average',
        'requires': ['timeframe', 'ma_type', 'ma_period', 'cross_direction', 'offset_pct'],
    },
    'price_level_break': {
        'label': 'Price Level Break',
        'description': 'Trigger when price breaks a specific level',
        'requires': ['price_level', 'offset_pct'],
    },
}


# =============================================================================
# STOP LOSS TYPES
# =============================================================================
# These define DIFFERENT WAYS to calculate where stop-loss should go

STOP_LOSS_TYPES = {
    'fixed_price': {
        'label': 'Fixed Price',
        'category': 'fixed',
        'description': 'Stop at exact price',
        'requires_value': 'price',
    },
    'price_reference': {
        'label': 'Price Reference',
        'category': 'reference',
        'description': 'Stop at indicator/level + offset',
        'requires_value': 'reference_type',
        'requires': ['price_ref_type', 'offset_pct'],
    },
    'atr_multiple': {
        'label': 'ATR Multiple',
        'category': 'volatility',
        'description': 'Stop at entry - (ATR × multiple)',
        'requires_value': 'multiplier',
        'requires': ['atr_multiplier'],
    },
    'percent_loss': {
        'label': 'Percent Loss',
        'category': 'percent',
        'description': 'Stop at entry - X% loss',
        'requires_value': 'percent',
        'requires': ['loss_percent'],
    },
    'trailing_stop_amount': {
        'label': 'Trailing Stop ($)',
        'category': 'trailing',
        'description': 'Follow price up by fixed dollar amount',
        'requires_value': 'amount',
        'requires': ['trail_amount'],
    },
    'trailing_stop_percent': {
        'label': 'Trailing Stop (%)',
        'category': 'trailing',
        'description': 'Follow price up by percent',
        'requires_value': 'percent',
        'requires': ['trail_percent'],
    },
    'trailing_stop_candle': {
        'label': 'Trailing Stop (Candle)',
        'category': 'trailing',
        'description': 'Stop at low of recent candle + offset',
        'requires_value': 'candle',
        'requires': ['timeframe', 'offset_pct'],
    },
    'key_level': {
        'label': 'Behind Key Level',
        'category': 'technical',
        'description': 'Stop behind support/resistance',
        'requires_value': 'reference_type',
        'requires': ['price_ref_type', 'offset_pct'],
    },
    'fvg': {
        'label': 'Fair Value Gap',
        'category': 'technical',
        'description': 'Stop at edge of recent FVG',
        'requires_value': 'offset_pct',
        'requires': ['offset_pct'],
    },
}


# =============================================================================
# TARGET/EXIT TYPES
# =============================================================================
# These define DIFFERENT WAYS to calculate profit targets

TARGET_TYPES = {
    'fixed_price': {
        'label': 'Fixed Price',
        'category': 'fixed',
        'description': 'Target at exact price',
        'requires_value': 'price',
    },
    'price_reference': {
        'label': 'Price Reference',
        'category': 'reference',
        'description': 'Target at indicator/level + offset',
        'requires_value': 'reference_type',
        'requires': ['price_ref_type', 'offset_pct'],
    },
    'fibonacci': {
        'label': 'Fibonacci Level',
        'category': 'fibonacci',
        'description': 'Target at Fibonacci extension/retracement',
        'requires_value': 'fib_level',
        'requires': ['fib_level', 'offset_pct'],
    },
    'atr_multiple': {
        'label': 'ATR Multiple',
        'category': 'volatility',
        'description': 'Target at entry + (ATR × multiple)',
        'requires_value': 'multiplier',
        'requires': ['atr_multiplier'],
    },
    'percent_gain': {
        'label': 'Percent Gain',
        'category': 'percent',
        'description': 'Target at entry + X% gain',
        'requires_value': 'percent',
        'requires': ['gain_percent'],
    },
    'risk_reward_ratio': {
        'label': 'Risk:Reward Ratio',
        'category': 'ratio',
        'description': 'Target based on risk/reward multiple',
        'requires_value': 'ratio',
        'requires': ['rr_ratio'],
        'description_detail': 'E.g., 1:2 means target is 2× the risk amount',
    },
    'candle_high': {
        'label': 'Candle High + Offset',
        'category': 'candle',
        'description': 'Target at high of recent candle + offset',
        'requires_value': 'candle',
        'requires': ['timeframe', 'offset_pct'],
    },
    'ma_level': {
        'label': 'MA Resistance',
        'category': 'moving_average',
        'description': 'Target at moving average level',
        'requires_value': 'reference_type',
        'requires': ['ma_type', 'ma_period', 'offset_pct'],
    },
}


# =============================================================================
# SESSION TYPES (PRE-MARKET / AFTER-HOURS)
# =============================================================================

SESSION_TYPES = {
    'regular': {
        'label': 'Regular Hours Only',
        'description': '9:30 AM - 4:00 PM ET',
        'outsideRth': False,
        'tif_options': ['DAY', 'GTC'],
    },
    'premarket': {
        'label': 'Pre-Market Only',
        'description': '4:00 AM - 9:30 AM ET',
        'outsideRth': True,
        'tif_options': ['GTC'],
        'notes': 'Bracket orders not supported',
    },
    'afterhours': {
        'label': 'After-Hours Only',
        'description': '4:00 PM - 8:00 PM ET',
        'outsideRth': True,
        'tif_options': ['GTC'],
        'notes': 'Bracket orders not supported',
    },
    'extended': {
        'label': 'Extended Hours (PM + AH)',
        'description': '4:00 AM - 8:00 PM ET',
        'outsideRth': True,
        'tif_options': ['GTC'],
        'notes': 'Use PM for pre-market, AH for after-hours bracket orders',
    },
    'all_hours': {
        'label': 'All Hours',
        'description': '4:00 AM - 8:00 PM ET (splits into PM + AH bracket orders)',
        'outsideRth': True,
        'tif_options': ['GTC'],
    },
}


# =============================================================================
# ORDER TYPE OPTIONS
# =============================================================================

ORDER_TYPES = {
    'market': {
        'label': 'Market Order',
        'description': 'Execute immediately at best available price',
        'requires_limit_price': False,
        'supported_in': ['all'],
    },
    'limit': {
        'label': 'Limit Order',
        'description': 'Execute at specified price or better',
        'requires_limit_price': True,
        'supported_in': ['all'],
    },
    'stop': {
        'label': 'Stop Order',
        'description': 'Becomes market order when price touches trigger',
        'requires_limit_price': False,
        'supported_in': ['automated', 'manual'],
    },
    'stop_limit': {
        'label': 'Stop-Limit Order',
        'description': 'Becomes limit order when price touches trigger',
        'requires_limit_price': True,
        'supported_in': ['automated', 'manual'],
    },
    'bracket': {
        'label': 'Bracket Order',
        'description': 'Parent + profit target + stop loss (one fills, others cancel)',
        'requires_profit_target': True,
        'requires_stop_price': True,
        'supported_in': ['automated', 'manual'],
        'restrictions': 'Not supported in extended hours (PM/AH)',
    },
    'trailing': {
        'label': 'Trailing Stop',
        'description': 'Stop that follows price, using $ or % offset',
        'supported_in': ['manual'],
        'requires': ['trail_type', 'trail_value'],
    },
}


# =============================================================================
# TIME IN FORCE OPTIONS
# =============================================================================

TIME_IN_FORCE = {
    'DAY': {
        'label': 'DAY',
        'description': 'Order expires at end of trading day',
        'supported_in': ['regular', 'premarket', 'afterhours'],
    },
    'GTC': {
        'label': 'GTC (Good Till Cancelled)',
        'description': 'Order remains until filled or manually cancelled',
        'supported_in': ['all'],
        'note': 'Required for pre-market and after-hours trading',
    },
}


# =============================================================================
# TIMEFRAME OPTIONS
# =============================================================================

TIMEFRAMES = {
    '1min': '1 min',
    '2min': '2 min',
    '5min': '5 min',
    '15min': '15 min',
    '30min': '30 min',
    '1h': '1 hour',
    '4h': '4 hours',
    '1d': '1 day',
    'weekly': 'Weekly',
}


# =============================================================================
# MOVING AVERAGE TYPES
# =============================================================================

MA_TYPES = {
    'sma': {'label': 'SMA (Simple)', 'description': 'Simple Moving Average'},
    'ema': {'label': 'EMA (Exponential)', 'description': 'Exponential Moving Average'},
}


# =============================================================================
# BREAKOUT DIRECTION
# =============================================================================

BREAK_DIRECTIONS = {
    'above_high': {'label': 'Break Above High', 'description': 'Trigger when price breaks above candle high'},
    'below_low': {'label': 'Break Below Low', 'description': 'Trigger when price breaks below candle low'},
}


# =============================================================================
# CROSSOVER DIRECTION
# =============================================================================

CROSS_DIRECTIONS = {
    'above': {'label': 'Cross Above', 'description': 'Trigger when price crosses above MA'},
    'below': {'label': 'Cross Below', 'description': 'Trigger when price crosses below MA'},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_price_ref_options_for_category(category):
    """Get all price reference options in a category"""
    return {
        ref_type: info 
        for ref_type, info in PRICE_REFERENCE_TYPES.items() 
        if info.get('category') == category
    }


def get_all_price_ref_options():
    """Get all available price reference types"""
    return list(PRICE_REFERENCE_TYPES.keys())


def validate_stop_loss_config(stop_type, config):
    """Validate stop-loss configuration"""
    if stop_type not in STOP_LOSS_TYPES:
        return False, f"Unknown stop loss type: {stop_type}"
    
    required_fields = STOP_LOSS_TYPES[stop_type].get('requires', [])
    for field in required_fields:
        if field not in config or config[field] is None:
            return False, f"Missing required field for {stop_type}: {field}"
    
    return True, "Valid"


def validate_target_config(target_type, config):
    """Validate target configuration"""
    if target_type not in TARGET_TYPES:
        return False, f"Unknown target type: {target_type}"
    
    required_fields = TARGET_TYPES[target_type].get('requires', [])
    for field in required_fields:
        if field not in config or config[field] is None:
            return False, f"Missing required field for {target_type}: {field}"
    
    return True, "Valid"
