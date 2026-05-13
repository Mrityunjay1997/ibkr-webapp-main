# Unified Order System - Quick Reference Card

**Version 1.0** | **Status**: Phase 1 Complete | **Date**: May 13, 2026

---

## At a Glance

| Feature | Off-Book | Automated | Manual |
|---------|----------|-----------|--------|
| Entry Type | Condition-based | Indicator-based | Direct price |
| Candle Breakout | ✅ | ✅ NEW | ✅ NEW |
| MA Crossover | ✅ | ✅ | ✅ |
| Multiple Targets | ❌ | ✅ | ✅ |
| Share Calc (Amount) | ✅ NEW | ✅ NEW | ✅ NEW |
| Share Calc (Risk %) | ❌ | ✅ NEW | ✅ NEW |
| Trailing Stop | ❌ | ✅ | ✅ |
| Candle-Based Exit | ❌ | ✅ NEW | ✅ NEW |
| Fib 100% Target | ❌ | ✅ NEW | ✅ NEW |
| Session-Aware | ✅ NEW | ✅ NEW | ✅ NEW |

---

## Price Reference Types (30+)

### Indicators
```python
'vwap'          # Volume Weighted Avg Price
'sma_fast'      # 20-period SMA (override with period)
'sma_medium'    # 50-period SMA
'sma_slow'      # 200-period SMA
'ema_fast'      # 12-period EMA
'ema_medium'    # 26-period EMA
'ema_slow'      # 50-period EMA
```

### Fibonacci (All 6 levels)
```python
'fibonacci_23_6'    # First retracement
'fibonacci_38_2'    # Second retracement
'fibonacci_50_0'    # Mid-point
'fibonacci_61_8'    # Golden ratio (most important)
'fibonacci_78_6'    # Deep retracement
'fibonacci_100_0'   # Extension level ◄── NEW
```

### Pivot Points
```python
'pivot'         # Central pivot
'support_1'     # S1
'support_2'     # S2
'resistance_1'  # R1
'resistance_2'  # R2
```

### Price Levels
```python
'prev_close'    # Yesterday's close
'day_high'      # Today's high
'day_low'       # Today's low
'high_of_day'   # For short stops
'low_of_day'    # For long stops
```

### Candles ◄── NEW
```python
'candle_high'   # High of candle (+ timeframe + lookback)
'candle_low'    # Low of candle (+ timeframe + lookback)
```

### Percent-Based
```python
'percent_target'    # X% above/below reference
```

### Custom
```python
'custom'        # User-specified price
```

---

## Stop-Loss Types

```python
'fixed_price'               # Fixed $ price
'price_reference'           # Indicator/level + offset
'atr_multiple'              # ATR × multiplier
'percent_loss'              # Fixed % loss
'trailing_stop_amount'      # Follow price by $X
'trailing_stop_percent'     # Follow price by X%
'trailing_stop_candle'      # Low of candle + offset ◄── NEW
'key_level'                 # Behind support/resistance
'high_of_day'               # For shorts ◄── NEW
'fvg'                       # Fair Value Gap
```

---

## Target Types

```python
'fixed_price'       # Fixed $ price
'price_reference'   # Indicator/level + offset
'fibonacci'         # All 6 Fib levels (including 100% extension) ◄── NEW
'atr_multiple'      # ATR × multiplier
'percent_gain'      # Fixed % profit
'risk_reward_ratio' # Based on stop price
'candle_high'       # High of candle + offset ◄── NEW
'ma_level'          # Moving average
```

---

## Session Types

```python
'regular'       # 9:30 AM - 4:00 PM ET (default)
'premarket'     # 4:00 AM - 9:30 AM ET
'afterhours'    # 4:00 PM - 8:00 PM ET
'extended'      # Both PM and AH (auto-split if bracket)
'all_hours'     # Works across all sessions
```

**Constraints:**
- Bracket orders NOT supported in extended hours
- GTC required for pre-market/after-hours
- `outsideRth=true` automatically set

---

## Python API - Quick Examples

### Create Orders

```python
from unified_order_manager import UnifiedOrderManager
from unified_order_model import (
    EntryConditionConfig, StopLossConfig, TargetConfig
)

manager = UnifiedOrderManager()

# OFF-BOOK: Candle breakout
entry = EntryConditionConfig(
    condition_type='candle_breakout',
    candle_timeframe='15min',
    candle_lookback=5,
    candle_break_direction='above_high',
    candle_offset_pct=0.0,
)
success, order_id = manager.create_offbook_order(
    'AAPL', 'long', 100, entry
)

# AUTOMATED: Multi-level with targets
targets = [
    TargetConfig(
        target_type='fibonacci',
        fib_level='fibonacci_61_8',
        percent_of_position=50.0,
    ),
    TargetConfig(
        target_type='percent_gain',
        gain_percent=10.0,
        percent_of_position=50.0,
    ),
]
success, order_id = manager.create_automated_order(
    'MSFT', 'long', entry, targets
)

# MANUAL: Direct entry
success, order_id = manager.create_manual_order(
    'TSLA', 'long', 100, entry_price=250.00
)
```

### Prepare Orders

```python
from price_resolver import PriceResolutionContext

order = manager.get_order(order_id)

context = PriceResolutionContext()
context.current_price = 150.25
context.vwap = 150.15
context.sma_fast = 150.05
context.atr = 1.50

success, warnings = manager.prepare_for_submission(
    order, price_context=context, current_price=150.25
)

for warning in warnings:
    print(f"⚠️  {warning}")
```

### Submit Orders

```python
success, msg = manager.submit_order(order)
if success:
    print(f"✓ Submitted: {msg}")
else:
    print(f"✗ Failed: {msg}")
```

### Retrieve Orders

```python
# Get one order
order = manager.get_order(order_id)

# Get all orders for a symbol
orders = manager.get_orders_by_symbol('AAPL')

# Get by mode
offbook = manager.get_orders_by_mode('offbook')

# Get pending
pending = manager.get_pending_orders()

# Get active
active = manager.get_active_orders()

# Statistics
stats = manager.get_statistics()
print(stats['by_mode'])      # {'offbook': 5, 'automated': 3, 'manual': 2}
print(stats['by_status'])    # {'pending': 4, 'active': 6, ...}
```

---

## REST API - Quick Reference

### Create Orders

```
POST /api/unified/orders/offbook      # Create off-book
POST /api/unified/orders/automated    # Create automated
POST /api/unified/orders/manual       # Create manual
```

### Get Orders

```
GET /api/unified/orders/<id>                    # Get by ID
GET /api/unified/orders/symbol/<symbol>        # Get by symbol
GET /api/unified/orders/symbol/<symbol>?status=pending
GET /api/unified/orders/mode/<mode>            # Get by mode
GET /api/unified/orders/pending                # Get all pending
GET /api/unified/orders/active                 # Get all active
```

### Manage Orders

```
POST /api/unified/orders/<id>/prepare          # Prepare order
POST /api/unified/orders/<id>/submit           # Submit order
```

### Analytics

```
GET /api/unified/stats                         # Get statistics
```

---

## Share Calculation Methods

### Method 1: Fixed Quantity
```python
config.calculation_method = 'fixed_quantity'
config.fixed_quantity = 100  # Use exactly 100 shares
```

### Method 2: From Dollar Amount
```python
config.calculation_method = 'from_amount'
config.amount_dollars = 1000.0  # Use $1000
# Shares = 1000 / current_price (rounded down)
```

### Method 3: From Risk Percent
```python
config.calculation_method = 'from_percent_risk'
config.account_size = 100000.0      # Total account
config.risk_percent = 1.0           # Risk 1% per trade
# Shares = (account × risk%) / (entry - stop)
```

---

## Common Configurations

### Aggressive Short Entry + Candle Stop
```python
# Entry: MA crossover below SMA
entry = EntryConditionConfig(
    condition_type='immediate',
    indicator_type='sma_fast',
    indicator_offset_pct=-0.5,
)

# Stop: High of day + 0.5% offset
stop = StopLossConfig(
    stop_type='high_of_day',
    high_of_day_offset_pct=0.5,  # Above high
)

# Target: Fib 61.8%
target = TargetConfig(
    target_type='fibonacci',
    fib_level='fibonacci_61_8',
    percent_of_position=100.0,
)
```

### Conservative Long Entry + ATR Stop
```python
entry = EntryConditionConfig(
    condition_type='immediate',
    indicator_type='vwap',
    indicator_offset_pct=-0.25,  # Below VWAP
)

stop = StopLossConfig(
    stop_type='atr_multiple',
    atr_multiplier=1.5,  # 1.5× ATR below entry
)

targets = [
    TargetConfig(
        target_type='percent_gain',
        gain_percent=2.0,
        percent_of_position=50.0,
    ),
    TargetConfig(
        target_type='percent_gain',
        gain_percent=5.0,
        percent_of_position=50.0,
    ),
]
```

### Breakout Trade with Candle Entry/Exit
```python
entry = EntryConditionConfig(
    condition_type='candle_breakout',
    candle_timeframe='1h',
    candle_lookback=3,
    candle_break_direction='above_high',
    candle_offset_pct=0.25,  # Above high
)

targets = [
    TargetConfig(
        target_type='candle_high',
        timeframe='1h',
        price_ref_offset_pct=0.5,
        percent_of_position=30.0,
    ),
    TargetConfig(
        target_type='fibonacci_100_0',  # Extension
        fib_offset_pct=0.0,
        percent_of_position=70.0,
    ),
]

stop = StopLossConfig(
    stop_type='trailing_stop_candle',
    trail_candle_timeframe='5min',
    trail_candle_offset_pct=-0.25,  # Below low of 5min
)
```

---

## Important Notes

### Price Resolution Context
Market data must be provided for price calculations:
- `current_price` - Current bid/ask/last
- `vwap` - Pre-calculated
- `sma_fast`, `sma_medium`, `sma_slow` - Pre-calculated
- `atr` - Pre-calculated
- `day_high`, `day_low`, `prev_close`
- `candles[timeframe]` - For candle-based references

### Order Status Flow
```
pending → active → triggered (offbook) / executed / cancelled
```

### Session Auto-Handling
```
Order with extended hours → system auto-applies:
✓ Sets outsideRth=true
✓ Converts TIF to GTC
✓ Splits bracket into PM + AH components
✓ Avoids unsupported order types
```

### Error Handling
```python
is_valid, error_msg = order.validate()
if not is_valid:
    print(f"Validation error: {error_msg}")
```

---

## Transition from Old System

**Old API** (still works):
```python
held_order_manager.create_order(...)
multiLevelOrderAdvanced(...)
send_orders()
```

**New API** (recommended):
```python
manager.create_offbook_order(...)
manager.create_automated_order(...)
manager.create_manual_order(...)
```

Both work during transition period.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Price not available" | Add to PriceResolutionContext |
| Bracket not submitted | Check session (not supported in PM/AH) |
| Shares = 0 | Verify amount is sufficient for at least 1 share |
| Order rejected | Run `order.validate()` to check config |
| Candle reference fails | Verify timeframe candle data exists |
| Fibonacci level not found | Ensure swing high/low calculated first |

---

## Files in System

```
Core Modules:
├── unified_order_model.py ..................... Data classes
├── unified_order_constants.py ................. Options & types
├── price_resolver.py .......................... Price calculation
├── share_calculator.py ........................ Share quantities
├── session_handler.py ......................... Session constraints
└── unified_order_manager.py ................... Central manager

Documentation:
├── UNIFIED_ORDER_SYSTEM_GUIDE.md .............. Full guide (500+ lines)
├── UNIFIED_ORDER_INTEGRATION_GUIDE.md ........ Flask integration (400+ lines)
└── QUICK_REFERENCE.md ......................... This file

Integration:
├── Flask blueprint with 10+ endpoints
├── Backward compatibility with old APIs
└── Ready for gradual migration

Next Phase:
├── Phase 2: Intelligent order suggestions
├── Phase 3: UI consolidation
└── Phase 4: Backtesting integration
```

---

**For complete documentation, see:**
- `UNIFIED_ORDER_SYSTEM_GUIDE.md` - Full system overview
- `UNIFIED_ORDER_INTEGRATION_GUIDE.md` - Flask integration
- Module docstrings for API details

