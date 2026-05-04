# Quick Reference: Held Orders Dynamic Limit Price

## What Was Implemented

✅ **CandlestickIndicator** - Tracks rolling high/low over lookback period  
✅ **4 Candlestick Indicators** - With timeframe and 4 search result fields each  
✅ **3 Additional SMA Fields** - For multi-timeframe moving average analysis  
✅ **2 Additional EMA Fields** - For multi-timeframe exponential moving averages  
✅ **HeldOrderLimitPriceCalculator** - Automatically calculates and updates limit prices  

## Key Methods

### Calculate Entry Limit Price
```python
HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
    symbol='AAPL',
    side='long',  # or 'short'
    market_data={'candlestick_high_5_5min': 125.50},
    entry_config={'type': 'candlestick_high', 'lookback_bars': 5, 'timeframe': '5min'},
    offset_pct=0  # Additional buffer %
)
# Returns: ~125.63 for long (high + offset), or limit below low for short
```

### Calculate Exit Limit Price
```python
HeldOrderLimitPriceCalculator.calculate_exit_limit_price(
    symbol='AAPL',
    side='long',
    market_data={...},
    exit_config={'type': 'candlestick_high', 'lookback_bars': 3, 'timeframe': '5min'},
    profit_target_pct=1.0
)
# Returns: Sell price at resistance level adjusted for profit target
```

### Update Limit Price Dynamically
```python
# Call on each new candle
success = HeldOrderLimitPriceCalculator.update_held_order_limit_prices(
    held_order=my_order,
    market_data=current_market_data
)
# Returns: True if price updated, False otherwise
```

## Configuration Examples

### Example 1: Candlestick Breakout Entry
```python
entry_config = {
    'type': 'candlestick_high',      # or 'candlestick_low' for shorts
    'lookback_bars': 5,               # 5-bar lookback
    'timeframe': '5min',              # On 5-minute candles
    'entry_offset_pct': 0.1           # 0.1% buffer above/below level
}
```

### Example 2: SMA-Based Entry
```python
entry_config = {
    'type': 'sma',
    'period': 20,
    'timeframe': '15min',
    'entry_offset_pct': 0.2           # Enter 0.2% above SMA
}
```

### Example 3: ATR-Based Entry (Volatility Adjusted)
```python
entry_config = {
    'type': 'atr',
    'period': 14,
    'timeframe': '5min',
    'atr_multiplier': 1.0             # Entry at: close + (ATR * 1.0)
}
```

## Market Data Format

Required keys in market_data dict:

```python
market_data = {
    # Candlestick patterns
    'candlestick_high_5_5min': 125.50,    # Format: candlestick_{direction}_{lookback}_{timeframe}
    'candlestick_low_5_5min': 124.20,
    'candlestick_high_10_5min': 125.80,
    'candlestick_low_10_5min': 123.90,
    
    # Moving averages
    'sma_20_5min': 124.75,
    'ema_12_5min': 124.80,
    
    # Volatility
    'atr_14_5min': 0.85,
    
    # Current price
    'close': 125.45,
    'entry_price': 125.00,
}
```

## Integration Steps

1. **Calculate indicators on new candle**
```python
from indicators import CandlestickIndicator
cs = CandlestickIndicator(high_series, low_series, close_series, lookback_bars=5)
recent = cs.get_recent_high_low()
market_data['candlestick_high_5_5min'] = recent['lookback_high']
market_data['candlestick_low_5_5min'] = recent['lookback_low']
```

2. **Calculate initial entry limit**
```python
from held_orders_manager import HeldOrderLimitPriceCalculator
order.limit_price = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
    'AAPL', 'long', market_data, entry_config
)
```

3. **Update periodically as new candles arrive**
```python
HeldOrderLimitPriceCalculator.update_held_order_limit_prices(order, market_data)
```

## Supported Types

| Type | Entry | Exit | Description |
|------|-------|------|-------------|
| `candlestick_high` | ✓ | ✓ | Recent high with lookback |
| `candlestick_low` | ✓ | ✓ | Recent low with lookback |
| `sma` | ✓ | ✓ | Simple Moving Average |
| `ema` | ✓ | ✓ | Exponential Moving Average |
| `atr` | ✓ | ✓ | ATR volatility-adjusted |
| `fixed_percent` | | ✓ | Fixed % profit target |

## Parameters Explanation

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `type` | string | 'candlestick_high' | Indicator type to use |
| `lookback_bars` | int | 5 | Number of bars for candlestick high/low |
| `period` | int | 20 | Period for MA/EMA/ATR |
| `timeframe` | string | '5min' | Candle timeframe |
| `entry_offset_pct` | float | 0.1 | % above/below level for long entry |
| `exit_offset_pct` | float | 0.05 | % adjustment for exit level |
| `atr_multiplier` | float | 1.5 | How many ATRs from close |
| `target_percent` | float | 2.0 | Profit target percentage |

## Common Patterns

### Pattern 1: Short-Term Breakout (5-min)
```python
entry_config = {'type': 'candlestick_high', 'lookback_bars': 5, 'timeframe': '5min', 'entry_offset_pct': 0.1}
exit_config = {'type': 'candlestick_high', 'lookback_bars': 3, 'timeframe': '5min', 'exit_offset_pct': 0.05}
```

### Pattern 2: Moving Average Crossover
```python
entry_config = {'type': 'sma', 'period': 20, 'timeframe': '15min', 'entry_offset_pct': 0.2}
exit_config = {'type': 'sma', 'period': 50, 'timeframe': '15min', 'exit_offset_pct': 0.1}
```

### Pattern 3: Multi-Timeframe (Conservative)
```python
entry_config = {'type': 'candlestick_high', 'lookback_bars': 5, 'timeframe': '5min'}
exit_config = {'type': 'candlestick_high', 'lookback_bars': 5, 'timeframe': '15min'}  # Larger move
```

### Pattern 4: Volatility-Based (ATR)
```python
entry_config = {'type': 'atr', 'period': 14, 'timeframe': '5min', 'atr_multiplier': 1.0}
exit_config = {'type': 'atr', 'period': 14, 'timeframe': '5min', 'atr_multiplier': 2.0}  # 2x ATR for profit
```

## Files Modified

| File | What Changed |
|------|--------------|
| `indicators.py` | Added CandlestickIndicator class |
| `forms.py` | Added 17 new indicator fields + candlestick search results |
| `morfeo.html` | Added 9 new indicator rows in UI |
| `held_orders_manager.py` | Added HeldOrderLimitPriceCalculator class |

## Documentation Files

📖 [HELD_ORDERS_LIMIT_PRICE_GUIDE.md](HELD_ORDERS_LIMIT_PRICE_GUIDE.md) - Complete guide with examples  
📋 [IMPLEMENTATION_SUMMARY_HELD_ORDERS.md](IMPLEMENTATION_SUMMARY_HELD_ORDERS.md) - Technical details  

## Next Steps

1. **Test it**: Run unit tests for the calculator
2. **Integrate it**: Update ibkr_signal_engine.py to call the new methods
3. **Monitor it**: Watch the logs for limit price updates
4. **Tune it**: Adjust lookback periods and offsets based on results

## Troubleshooting

**Q: Limit price not updating?**  
A: Check that market_data contains required keys and timeframe matches

**Q: Wrong entry direction?**  
A: For longs use `candlestick_high`, for shorts use `candlestick_low`

**Q: Price not reaching target?**  
A: Check offset_pct values - they might be pushing price too far

## Support

Refer to the implementation guide for:
- Configuration examples
- API reference
- Integration code
- Best practices
- Troubleshooting details
