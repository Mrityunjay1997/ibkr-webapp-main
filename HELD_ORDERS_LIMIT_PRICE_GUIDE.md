# Held Orders Dynamic Limit Price Guide

## Overview

This guide explains the new dynamic limit price calculation system for hold orders off-market. The system calculates and updates limit prices automatically based on entry/exit criteria as market data changes, allowing your orders to adapt to changing market conditions.

## Features Added

### 1. Candlestick Indicator (CandlestickIndicator class in indicators.py)

The new `CandlestickIndicator` class tracks candlestick patterns and provides:
- **Lookback High/Low**: Gets the highest high and lowest low over a lookback period
- **Lookback Range**: Calculates the range between high and low
- **Recent High/Low**: Returns current candlestick's recent high/low
- **Breakout Detection**: Checks if price is above/below lookback levels with offset

```python
from indicators import CandlestickIndicator

# Example: 5-bar candlestick on 5-minute timeframe
cs = CandlestickIndicator(high_series, low_series, close_series, lookback_bars=5)
recent_data = cs.get_recent_high_low()
# Returns: {'lookback_high': 125.50, 'lookback_low': 124.20, 'current_price': 125.30, 'lookback_range': 1.30}

# Check if price is above recent high (with 0.1% buffer)
is_breakout = cs.is_above_lookback_high(offset_pct=0.1)
```

### 2. New Indicator Fields in Forms

Added to the `Parameters` form in `forms.py`:

#### Additional SMA Fields (3):
- `SMA1` - Additional SMA period field
- `SMA1_tf` - SMA1 timeframe selector
- `ComparisonSMA1` - Comparison operator for SMA1
- `PercentageSMA1` - Percentage threshold for SMA1
- `booleanSMA1` - Enable/disable SMA1
- `filterSMA1` - Filter by SMA1
- `SMA1Bool` - Percentage or value selector

And similarly for `SMA2` and `SMA3` (following the same pattern)

#### Additional EMA Fields (2):
- `EMA1` - Additional EMA period field
- `EMA1_tf` - EMA1 timeframe selector
- `ComparisonEMA1` - Comparison operator for EMA1
- `PercentageEMA1` - Percentage threshold for EMA1
- `booleanEMA1` - Enable/disable EMA1
- `filterEMA1` - Filter by EMA1
- `EMA1Bool` - Percentage or value selector

And similarly for `EMA2` (following the same pattern)

#### Candlestick Indicators (4):
Each candlestick indicator (Candlestick1-4) includes:
- Period/Lookback field (e.g., `Candlestick1` = lookback bars)
- Timeframe selector (e.g., `Candlestick1_tf`)
- Comparison operator (e.g., `ComparisonCandlestick1`)
- Percentage threshold (e.g., `PercentageCandlestick1`)
- Enable/disable boolean (e.g., `booleanCandlestick1`)
- Filter option (e.g., `filterCandlestick1`)
- Percentage/value selector (e.g., `CandlestickBool1`)
- 4 Search Result fields per candlestick (for storing analysis results):
  - `Candlestick1_SearchResult1`, `Candlestick1_SearchResult2`, etc.

### 3. Dynamic Limit Price Calculation (HeldOrderLimitPriceCalculator)

New class in `held_orders_manager.py` with three main methods:

#### calculate_entry_limit_price()
Calculates entry order limit prices based on entry criteria:

```python
from held_orders_manager import HeldOrderLimitPriceCalculator

# Example: Entry based on candlestick breakout
entry_config = {
    'type': 'candlestick_high',  # or 'candlestick_low'
    'lookback_bars': 5,
    'timeframe': '5min',
    'entry_offset_pct': 0.1  # 0.1% buffer above/below level
}

market_data = {
    'candlestick_high_5_5min': 125.50,
    'candlestick_low_5_5min': 124.20,
    'close': 125.45
}

# For long order
limit_price = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
    symbol='AAPL',
    side='long',
    market_data=market_data,
    entry_config=entry_config,
    offset_pct=0  # Additional offset for limit order
)
# Result: ~125.63 (high + 0.1%)
```

**Supported entry types:**
- `candlestick_high` / `candlestick_low` - Breakout from recent high/low
- `sma` - Entry from SMA level
- `ema` - Entry from EMA level
- `atr` - Volatility-adjusted entry

#### calculate_exit_limit_price()
Calculates sell/exit order limit prices based on sell criteria:

```python
exit_config = {
    'type': 'candlestick_high',  # Resistance level to sell at
    'lookback_bars': 5,
    'timeframe': '5min',
    'exit_offset_pct': 0.05  # 0.05% below resistance
}

sell_price = HeldOrderLimitPriceCalculator.calculate_exit_limit_price(
    symbol='AAPL',
    side='long',
    market_data=market_data,
    exit_config=exit_config,
    profit_target_pct=1.0  # 1% profit target
)
# Result: Candlestick high minus offset and profit target
```

**Supported exit types:**
- `candlestick_high` / `candlestick_low` - Resistance/support levels
- `sma` / `ema` - Moving average levels
- `atr` - Volatility-adjusted targets
- `fixed_percent` - Fixed percentage profit target

#### update_held_order_limit_prices()
Updates an order's limit price with new market data:

```python
# Call this method on each new candle to recalculate
success = HeldOrderLimitPriceCalculator.update_held_order_limit_prices(
    held_order=my_order,
    market_data=current_market_data
)

if success:
    print(f"Order limit price updated to {my_order.limit_price}")
```

## How It Works

### Dynamic Calculation Flow

1. **User creates a held order** with entry/exit conditions
   - Entry config: `{'type': 'candlestick_high', 'lookback_bars': 5, 'timeframe': '5min'}`
   - Exit config: `{'type': 'candlestick_high', 'lookback_bars': 3, 'timeframe': '5min'}`

2. **System initializes order** with initial limit price
   ```python
   entry_limit = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
       symbol, side, market_data, entry_config
   )
   order.limit_price = entry_limit
   ```

3. **On each new candle** (5-minute, 15-minute, hourly, etc.):
   - New market data arrives with updated candlestick highs/lows
   - System recalculates limit price using new data
   - Order limit price updates automatically
   - Order adapts to changing market conditions

4. **Example: 5-minute candlestick entry on 10-bar lookback**
   ```
   Time:     12:00  12:05  12:10  12:15  12:20  12:25
   High:     125.0  125.3  125.1  125.8  126.2  125.9
   10-bar high (lookback):
   12:00:    122.5  (uses previous bars)
   12:05:    122.7  (updated with new candle)
   12:10:    122.8  (continuously updates)
   12:15:    123.1
   12:20:    123.5  
   12:25:    123.7
   
   Entry limit price = lookback_high * (1 + 0.1%)
   → Continuously adjusted as new candles form
   ```

## Integration with Your Trading System

### In ibkr_signal_engine.py

Add this code to update held orders periodically:

```python
from held_orders_manager import HeldOrderLimitPriceCalculator, HeldOrdersManager

# When new market data arrives
def on_new_market_data(symbol: str, market_data: dict):
    # Get all held orders for this symbol
    held_orders_mgr = HeldOrdersManager()  # or get from your app state
    active_orders = held_orders_mgr.get_active_orders_for_symbol(symbol)
    
    for order in active_orders:
        # Update limit price with new market data
        updated = HeldOrderLimitPriceCalculator.update_held_order_limit_prices(
            order, market_data
        )
        
        if updated and order.entry_executed:
            # Optionally: update the live order with IBKR
            # update_ibkr_order(order.order_id, order.limit_price)
            pass
```

### Market Data Structure

Provide market data with these keys for the calculator:

```python
market_data = {
    # Candlestick data (required for candlestick-based entries/exits)
    'candlestick_high_5_5min': 125.50,  # Format: candlestick_high_{lookback}_{timeframe}
    'candlestick_low_5_5min': 124.20,
    'candlestick_high_10_5min': 125.80,
    'candlestick_low_10_5min': 123.90,
    
    # Moving average data (required for MA-based entries/exits)
    'sma_20_5min': 124.75,
    'sma_50_5min': 124.50,
    'ema_12_5min': 124.80,
    'ema_26_5min': 124.60,
    
    # Volatility data (for ATR-based entries/exits)
    'atr_14_5min': 0.85,
    'atr_14_1hour': 1.25,
    
    # Price data
    'close': 125.45,
    'entry_price': 125.00,  # For fixed percent calculations
}
```

## Configuration Examples

### Example 1: Long Entry on 5-bar Candlestick Breakout

```python
entry_config = {
    'type': 'candlestick_high',
    'lookback_bars': 5,
    'timeframe': '5min',
    'entry_offset_pct': 0.1  # 0.1% buffer
}

exit_config = {
    'type': 'candlestick_high',
    'lookback_bars': 3,
    'timeframe': '5min',
    'exit_offset_pct': 0.05,  # 0.05% below resistance
    'atr_multiplier': 2.0
}

# Entry limit = recent 5-bar high + 0.1%
# Exit limit = recent 3-bar high - 0.05%
```

### Example 2: Moving Average Crossover with Volatility-Adjusted Exit

```python
entry_config = {
    'type': 'sma',
    'period': 20,
    'timeframe': '15min',
    'entry_offset_pct': 0.2  # 0.2% above SMA
}

exit_config = {
    'type': 'atr',
    'period': 14,
    'timeframe': '15min',
    'atr_multiplier': 1.5  # Take profit at: current_close + (ATR * 1.5)
}

# Entry limit = 20-SMA + 0.2%
# Exit limit = current_close + (ATR * 1.5)
```

### Example 3: Multi-Timeframe Analysis

```python
# Enter on 5-minute candlestick
entry_config = {
    'type': 'candlestick_high',
    'lookback_bars': 5,
    'timeframe': '5min',
    'entry_offset_pct': 0.15
}

# Exit on 15-minute resistance (more stability)
exit_config = {
    'type': 'candlestick_high',
    'lookback_bars': 5,
    'timeframe': '15min',  # Different timeframe
    'exit_offset_pct': 0.10
}

# Order enters when 5-min high breaks
# Exits when 15-min high is reached (larger move, better profit)
```

## Best Practices

### 1. Lookback Period Selection
- **Short timeframes (1-5 min)**: Use 5-10 bar lookback
- **Medium timeframes (15-60 min)**: Use 5-20 bar lookback
- **Daily timeframes**: Use 5-10 day lookback
- Generally: smaller lookback = more sensitive, larger lookback = more stable

### 2. Offset Percentages
- **Entry offset**: Usually 0.05% - 0.3% (thin buffer above/below breakout level)
- **Exit offset**: Usually 0.05% - 0.2% (slightly below/above resistance)
- Lower values = more aggressive, Higher values = more conservative

### 3. Combining Indicators
```python
# Strategy: 5-min entry, 15-min exit confirmation
entry_config = {
    'type': 'candlestick_high',
    'lookback_bars': 5,
    'timeframe': '5min'
}

exit_config = {
    'type': 'sma',  # Use different indicator for exit
    'period': 50,
    'timeframe': '15min'
}
```

### 4. Risk Management
```python
# Always pair with stop loss (not shown here, but essential)
order.entry_conditions = [
    HeldOrderCondition(
        condition_type='candle_breakout',
        phase='entry',
        config={...}
    )
]

order.exit_conditions = [
    HeldOrderCondition(condition_type='candle_breakout', ...),  # Profit target
    HeldOrderCondition(condition_type='stop_loss', ...)  # Stop loss (separate logic)
]
```

## Performance Considerations

- **Update frequency**: Call `update_held_order_limit_prices()` on each new candle
- **Market data frequency**: More frequent data = more responsive but higher CPU usage
- **Lookback period**: Larger lookback periods require more historical data storage
- **Typical usage**: Update once per candle (5-min, 15-min, or 1-hour depending on strategy)

## Troubleshooting

### Limit Price Not Updating
- Check that market_data contains required keys for your config type
- Verify timeframe matches your data timeframe strings (e.g., '5min' vs '5m')
- Ensure candlestick data is being calculated with correct lookback periods

### Limit Price Not Reaching Expected Level
- Check offset_pct values - they may be pushing price further than expected
- Verify entry/exit config has correct type (e.g., 'candlestick_high' vs 'candlestick_low')
- For long entries, use candlestick_high; for shorts, use candlestick_low

### Order Not Triggering
- Verify entry_conditions config matches the market_data available
- Check that price is actually reaching the calculated limit price
- Ensure held order status is 'active' (not 'cancelled' or 'executed')

## Summary

The new system provides:
1. ✅ **Candlestick patterns** with dynamic lookback high/low tracking
2. ✅ **Multiple timeframe support** for each indicator
3. ✅ **Automatic limit price updates** as market data changes
4. ✅ **Flexible configuration** for entry and exit criteria
5. ✅ **Integration-ready** methods to plug into your signal engine

Use this to create orders that adapt to changing market conditions throughout the trading day!
