# Implementation Summary: Dynamic Limit Price for Held Orders

## Changes Made

### 1. **indicators.py** - Added CandlestickIndicator Class
**Location**: End of file (after pivot_points function)

**What it does:**
- Tracks candlestick highs/lows over a configurable lookback period
- Provides methods to get recent high/low, range, and detect breakouts
- Updates automatically as new candlestick data arrives

**Key methods:**
```python
CandlestickIndicator.get_lookback_high()     # Rolling max high
CandlestickIndicator.get_lookback_low()      # Rolling min low
CandlestickIndicator.get_recent_high_low()   # Dict with latest values
CandlestickIndicator.is_above_lookback_high(offset_pct=0)
CandlestickIndicator.is_below_lookback_low(offset_pct=0)
```

### 2. **forms.py** - Added New Indicator Fields
**Location**: Multiple sections of the Parameters form class

**Added fields:**

#### Indicator Period Fields:
- `SMA1`, `SMA2`, `SMA3` - Additional SMA periods
- `EMA1`, `EMA2` - Additional EMA periods  
- `Candlestick1-4` - Candlestick lookback periods

#### Timeframe Selectors:
- `SMA1_tf`, `SMA2_tf`, `SMA3_tf` - SMA timeframes
- `EMA1_tf`, `EMA2_tf` - EMA timeframes
- `Candlestick1_tf` through `Candlestick4_tf` - Candlestick timeframes

#### Comparison Operators:
- `ComparisonSMA1-3`, `ComparisonEMA1-2`, `ComparisonCandlestick1-4`

#### Percentage/Amount Fields:
- `PercentageSMA1-3`, `PercentageEMA1-2`, `PercentageCandlestick1-4`

#### Boolean Enable/Disable:
- `booleanSMA1-3`, `booleanEMA1-2`, `booleanCandlestick1-4`

#### Percentage/Value Selectors (RadioField):
- `SMA1Bool-3Bool`, `EMA1Bool-2Bool`, `CandlestickBool1-4`

#### Filter Checkboxes:
- `filterSMA1-3`, `filterEMA1-2`, `filterCandlestick1-4`

#### Candlestick Search Result Fields:
- `Candlestick1_SearchResult1` through `Candlestick4_SearchResult4` (16 total)
  - Used to store analysis results from candlestick pattern searches

### 3. **morfeo.html** - Added UI Rows
**Location**: Two table sections in the indicators display

**First table (after SlowEMA row):**
- Additional EMA 1 row
- Additional EMA 2 row

**Second table (after ATR row):**
- Additional SMA 1 row
- Additional SMA 2 row
- Additional SMA 3 row
- Candlestick 1 row
- Candlestick 2 row
- Candlestick 3 row
- Candlestick 4 row

Each row includes:
- Indicator name
- Timeframe dropdown
- Period/Lookback number field
- Comparison operator dropdown
- Percentage threshold field
- Percentage/Value radio buttons
- Filter checkbox

### 4. **held_orders_manager.py** - Added HeldOrderLimitPriceCalculator Class
**Location**: End of file (new class)

**What it does:**
- Calculates entry limit prices from entry criteria (candlesticks, MAs, ATR)
- Calculates exit limit prices from sell criteria
- Updates held order limit prices dynamically with new market data

**Key methods:**
```python
HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
    symbol, side, market_data, entry_config, offset_pct
)
# Returns: Limit price for entry order based on config

HeldOrderLimitPriceCalculator.calculate_exit_limit_price(
    symbol, side, market_data, exit_config, profit_target_pct
)
# Returns: Limit price for exit order based on config

HeldOrderLimitPriceCalculator.update_held_order_limit_prices(
    held_order, market_data
)
# Returns: True if price was updated, False otherwise
```

## Integration Steps

### Step 1: Import Required Classes
```python
from indicators import CandlestickIndicator
from held_orders_manager import (
    HeldOrderLimitPriceCalculator,
    HeldOrdersManager,
    HeldOrder
)
```

### Step 2: Initialize Market Data Calculation
In your `ibkr_signal_engine.py` or signal generation code:

```python
def calculate_market_indicators(symbol, ohlc_df, timeframe):
    """Calculate all indicators including candlesticks"""
    market_data = {}
    
    # Existing indicators...
    market_data['close'] = ohlc_df['close'].iloc[-1]
    market_data['sma_20_5min'] = ...  # Your existing SMA code
    
    # NEW: Add candlestick indicators
    for lookback in [5, 10, 15, 20]:
        cs = CandlestickIndicator(
            ohlc_df['high'],
            ohlc_df['low'],
            ohlc_df['close'],
            lookback_bars=lookback
        )
        recent = cs.get_recent_high_low()
        market_data[f'candlestick_high_{lookback}_{timeframe}'] = recent['lookback_high']
        market_data[f'candlestick_low_{lookback}_{timeframe}'] = recent['lookback_low']
    
    return market_data
```

### Step 3: Update Held Order Limit Prices
Add this to your main trading loop (called on each new candle):

```python
def update_all_held_orders(symbol, market_data):
    """Update limit prices for all active held orders"""
    held_orders_mgr = HeldOrdersManager()  # Your instance
    active_orders = held_orders_mgr.get_active_orders_for_symbol(symbol)
    
    for order in active_orders:
        updated = HeldOrderLimitPriceCalculator.update_held_order_limit_prices(
            order, market_data
        )
        
        if updated and not order.entry_executed:
            logger.info(
                f"Updated {symbol} {order.side} order {order.order_id} "
                f"limit price to {order.limit_price}"
            )
            # Optionally: update the order in IBKR if already placed
```

### Step 4: Create Held Orders with Entry/Exit Criteria

```python
from held_orders_manager import (
    HeldOrder,
    HeldOrderCondition,
    CandleBreakoutCondition
)

# Example: Create order with candlestick entry criteria
order = HeldOrder(
    order_id=str(uuid.uuid4()),
    symbol='AAPL',
    side='long',
    quantity=100,
    order_type='limit',
    limit_price=None  # Will be calculated
)

# Add entry condition with candlestick config
entry_condition = HeldOrderCondition(
    condition_type='candle_breakout',
    phase='entry',
    config={
        'type': 'candlestick_high',
        'lookback_bars': 5,
        'timeframe': '5min',
        'entry_offset_pct': 0.1
    }
)
order.entry_conditions.append(entry_condition)

# Add exit condition
exit_condition = HeldOrderCondition(
    condition_type='candle_breakout',
    phase='exit',
    config={
        'type': 'candlestick_high',
        'lookback_bars': 3,
        'timeframe': '5min',
        'exit_offset_pct': 0.05
    }
)
order.exit_conditions.append(exit_condition)

# Calculate initial limit price
market_data = calculate_market_indicators('AAPL', df, '5min')
order.limit_price = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
    'AAPL', 'long', market_data, entry_condition.config
)
```

## UI Usage

### In morfeo.html (Web Interface)

The new fields appear in the indicators section:

1. **Candlestick 1-4**: Set lookback period (e.g., 5, 10, 15, 20 bars)
2. **SMA 1-3**: Set SMA periods (e.g., 30, 50, 100)
3. **EMA 1-2**: Set EMA periods (e.g., 12, 26)
4. **Time Frame**: Select timeframe for each indicator (1min, 5min, 15min, 1hour, 1day)
5. **Search Results**: 4 fields per candlestick for storing pattern analysis results

## API Reference

### CandlestickIndicator

```python
class CandlestickIndicator:
    def __init__(self, high: pd.Series, low: pd.Series, close: pd.Series, lookback_bars: int = 5)
    def get_lookback_high(self) -> pd.Series
    def get_lookback_low(self) -> pd.Series
    def get_lookback_range(self) -> pd.Series
    def get_recent_high_low(self) -> dict
    def is_above_lookback_high(self, offset_pct: float = 0.0) -> bool
    def is_below_lookback_low(self, offset_pct: float = 0.0) -> bool
```

### HeldOrderLimitPriceCalculator

```python
class HeldOrderLimitPriceCalculator:
    @staticmethod
    def calculate_entry_limit_price(
        symbol: str,
        side: str,  # 'long' or 'short'
        market_data: Dict,
        entry_config: Dict,
        offset_pct: float = 0
    ) -> Optional[float]
    
    @staticmethod
    def calculate_exit_limit_price(
        symbol: str,
        side: str,
        market_data: Dict,
        exit_config: Dict,
        profit_target_pct: float = 0
    ) -> Optional[float]
    
    @staticmethod
    def update_held_order_limit_prices(
        held_order: HeldOrder,
        market_data: Dict
    ) -> bool
```

## Market Data Format

Ensure market_data dict contains:

```python
{
    # Candlestick data
    'candlestick_high_5_5min': 125.50,    # Format: candlestick_{direction}_{lookback}_{timeframe}
    'candlestick_low_5_5min': 124.20,
    'candlestick_high_10_5min': 125.80,
    'candlestick_low_10_5min': 123.90,
    
    # Moving averages
    'sma_20_5min': 124.75,
    'sma_50_5min': 124.50,
    'ema_12_5min': 124.80,
    'ema_26_5min': 124.60,
    
    # Volatility
    'atr_14_5min': 0.85,
    'atr_14_1hour': 1.25,
    
    # Current price
    'close': 125.45,
    'entry_price': 125.00,
}
```

## Testing

### Unit Test Example
```python
from held_orders_manager import HeldOrderLimitPriceCalculator

def test_candlestick_entry_calculation():
    market_data = {
        'candlestick_high_5_5min': 125.50,
        'candlestick_low_5_5min': 124.20,
        'close': 125.45
    }
    
    config = {
        'type': 'candlestick_high',
        'lookback_bars': 5,
        'timeframe': '5min',
        'entry_offset_pct': 0.1
    }
    
    limit_price = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
        'AAPL', 'long', market_data, config
    )
    
    assert limit_price is not None
    assert limit_price > 125.50  # Should be above candlestick high
    print(f"Entry limit price: {limit_price}")
```

## Files Modified

| File | Changes |
|------|---------|
| `indicators.py` | Added CandlestickIndicator class (~115 lines) |
| `forms.py` | Added 17 new form fields + 4 search result fields per candlestick |
| `morfeo.html` | Added 9 new indicator rows (2 EMA + 3 SMA + 4 Candlestick) |
| `held_orders_manager.py` | Added HeldOrderLimitPriceCalculator class (~250 lines) |

## Backward Compatibility

✅ All changes are additive - no existing fields or methods were modified
✅ Existing held orders functionality is unchanged
✅ New features are optional - can be used alongside existing order methods

## Next Steps

1. **Test the implementation**: Run unit tests for limit price calculations
2. **Integrate into signal engine**: Update `ibkr_signal_engine.py` to use new calculator
3. **Monitor updates**: Track order limit price changes in logs
4. **Fine-tune parameters**: Adjust lookback periods and offsets based on backtests
5. **Implement stop losses**: Add complementary stop loss logic for risk management

## Documentation

See `HELD_ORDERS_LIMIT_PRICE_GUIDE.md` for:
- Detailed feature descriptions
- Configuration examples
- Integration examples
- Best practices
- Troubleshooting guide
