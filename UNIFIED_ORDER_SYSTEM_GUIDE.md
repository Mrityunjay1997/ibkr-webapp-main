# Unified Order Management System - Complete Guide

**Version**: 1.0  
**Date**: May 13, 2026  
**Status**: Phase 1 Foundation Complete

---

## Overview

The Unified Order Management System consolidates **off-book orders**, **automated orders**, and **manual orders** into a single integrated system. This eliminates configuration duplication and enables feature sharing across all three modes.

### Key Achievements in Phase 1

✅ **Consolidated Data Models** - Single `UnifiedOrderConfig` for all order types  
✅ **Unified Constants** - All price references, stops, targets in one canonical source  
✅ **Price Resolution Engine** - 30+ price reference types across all modes  
✅ **Share Calculator** - Multiple calculation methods (fixed, from amount, from risk %)  
✅ **Session-Aware Handler** - Pre-market/after-hours constraints automatically applied  
✅ **Order Manager** - Central orchestrator with creation, validation, routing  

---

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                   UNIFIED ORDER CONFIG                      │
│  (Entry | StopLoss | Targets | Session | Shares)          │
└────────────┬────────────────────────────────────────────────┘
             │
    ┌────────┴──────────────────────────────────┐
    │                                           │
    ▼                                           ▼
┌──────────────────┐              ┌──────────────────────┐
│  OFF-BOOK MODE   │              │  AUTOMATED MODE      │
│  (Conditional)   │              │  (Multi-Level)       │
└──────────────────┘              └──────────────────────┘
    │                                           │
    │        ┌────────────────┬────────────────┤
    │        │                │                │
    ▼        ▼                ▼                ▼
┌─────────────────────────────────────────────────────┐
│           UNIFIED ORDER MANAGER                     │
│  - Validates  - Calculates Prices/Shares          │
│  - Routes     - Prepares for Submission            │
│  - Tracks     - Persists to Storage                │
└─────────────────────────────────────────────────────┘
    │
    ├──► PRICE RESOLVER (30+ ref types)
    ├──► SHARE CALCULATOR (3 methods)
    ├──► SESSION HANDLER (PM/AH constraints)
    └──► BACKEND ROUTING (IBKR / Monitors)
```

### Data Flow

```
Form Input / Preset / API
    ↓
UnifiedOrderConfig (created)
    ↓
register_order() 
    ↓
prepare_for_submission()
    ├─→ calculate_prices()
    ├─→ calculate_shares()
    ├─→ validate_session_constraints()
    └─→ prepare_session_settings()
    ↓
submit_order()
    ├─→ Set status = ACTIVE
    ├─→ Route to backend (offbook/automated/manual)
    └─→ Persist to storage
```

---

## Core Modules

### 1. `unified_order_model.py` - Data Classes

Defines all configuration classes:

```python
# Main configuration object
UnifiedOrderConfig
├── EntryConditionConfig (how to enter)
├── StopLossConfig (where to stop)
├── TargetConfig (where to exit) - can have multiple
└── SessionConfig (PM/AH settings)

# Enums
├── OrderMode (OFFBOOK, AUTOMATED, MANUAL)
├── OrderSide (LONG, SHORT)
└── OrderStatus (PENDING, ACTIVE, TRIGGERED, EXECUTED, etc)

# Convenience builders
├── create_offbook_order()
├── create_automated_order()
└── create_manual_order()
```

**Key Features:**
- Full serialization to/from JSON
- Validation methods
- Status tracking
- Timestamps and audit trail

### 2. `unified_order_constants.py` - Options & Definitions

Consolidated options that work across all three modes:

```python
# 30+ price reference types
PRICE_REFERENCE_TYPES
├── Indicators (VWAP, SMA, EMA, RSI, ATR, OBV)
├── Fibonacci (23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)
├── Pivot Points (Pivot, Support, Resistance)
├── Price Levels (prev_close, high_of_day, low_of_day)
├── Candles (NEW - candle_high + offset, candle_low + offset)
└── Custom (user-specified price)

# Entry conditions
ENTRY_CONDITION_TYPES
├── immediate (market/limit)
├── candle_breakout (breakout of recent candle)
├── ma_crossover (price crosses moving average)
└── price_level_break (break of specific level)

# Stop-loss types
STOP_LOSS_TYPES
├── fixed_price
├── price_reference (indicator/level based)
├── atr_multiple (ATR-based)
├── percent_loss (fixed % loss)
├── trailing_stop_amount ($ trailing)
├── trailing_stop_percent (% trailing)
├── trailing_stop_candle (candle low + offset) ◄── NEW
├── key_level (behind support/resistance)
└── fvg (fair value gap)

# Target types
TARGET_TYPES
├── fixed_price
├── price_reference
├── fibonacci (with all 6 levels)
├── atr_multiple
├── percent_gain
├── risk_reward_ratio
├── candle_high (+ offset) ◄── NEW
└── ma_level

# Session types (NEW feature)
SESSION_TYPES
├── regular (9:30 AM - 4:00 PM ET)
├── premarket (4:00 AM - 9:30 AM ET)
├── afterhours (4:00 PM - 8:00 PM ET)
├── extended (PM + AH split)
└── all_hours (auto-split)

# Order types, time in force, timeframes, MAs
```

### 3. `price_resolver.py` - Price Resolution Engine

Resolves all price reference types to actual prices:

```python
PriceResolutionContext
├── Current market data (bid, ask, last)
├── Daily data (high, low, open, close, prev_close)
├── Indicators (VWAP, SMA, EMA, ATR, RSI)
├── Fibonacci levels (all 6)
├── Pivot points (5 levels)
├── Candle data (dict of timeframe → candles)
└── Entry price (for relative calculations)

PriceResolver
├── resolve_price() - any price reference → actual price
├── resolve_stop_price() - stop config → stop price
└── resolve_target_price() - target config → target price
```

**Features:**
- Supports 30+ price reference types
- Handles offset percentages (±X%)
- Validates data availability
- Detailed error messages

### 4. `share_calculator.py` - Share Quantity Calculation

Three calculation methods:

```python
ShareCalculator.calculate_from_fixed_quantity(qty)
    ├─ Use quantity directly
    └─ No calculation needed

ShareCalculator.calculate_from_amount(amount, price)
    ├─ Shares = Amount / Price
    ├─ Rounding: down, up, or round
    └─ Example: $1000 / $50.25 = 19 shares (rounded down)

ShareCalculator.calculate_from_percent_risk(account, risk%, entry, stop)
    ├─ Risk$ = Account × Risk%
    ├─ RiskPerShare = |Entry - Stop|
    ├─ Shares = Risk$ / RiskPerShare
    └─ Example: $100k account, 1% risk, $50-$49 = 1000 shares

ShareCalculator.calculate_partial_position_shares(total, %)
    ├─ For multi-level exits
    └─ Example: 100 shares, exit 50% = 50 shares
```

### 5. `session_handler.py` - Session-Aware Order Management

Handles pre-market and after-hours constraints:

```python
SessionHandler
├── get_current_session() → PREMARKET | REGULAR | AFTERHOURS
├── is_extended_hours() → bool
├── validate_order_for_session() → (valid, [warnings])
├── prepare_order_for_submission() → applies session settings
└── split_extended_hours_order() → PM order + AH order

Features:
├── Auto-detects current trading session
├── Applies session constraints (no bracket orders in PM/AH)
├── Sets outsideRth flag correctly
├── Converts TIF to GTC for extended hours
└── Splits orders for PM+AH bracket handling
```

**Session Times (ET):**
- **Pre-market**: 4:00 AM - 9:30 AM
- **Regular**: 9:30 AM - 4:00 PM  
- **After-hours**: 4:00 PM - 8:00 PM

**Constraints:**
- Bracket orders not supported in PM/AH
- GTC required for extended hours
- `outsideRth=true` for orders that cross regular hours

### 6. `unified_order_manager.py` - Central Orchestrator

Master order manager with full lifecycle support:

```python
UnifiedOrderManager
├── Order Creation
│   ├── create_offbook_order()
│   ├── create_automated_order()
│   └── create_manual_order()
│
├── Order Retrieval
│   ├── get_order(id)
│   ├── get_orders_by_symbol(symbol)
│   ├── get_orders_by_mode(mode)
│   ├── get_pending_orders()
│   ├── get_active_orders()
│   └── get_offbook_active()
│
├── Order Preparation
│   ├── calculate_prices(order, context)
│   ├── calculate_shares(order, price, account_size)
│   └── prepare_for_submission(order, context)
│
├── Order Submission
│   ├── register_order(order)
│   └── submit_order(order)
│
├── Persistence
│   ├── _save_order_to_disk(order)
│   ├── _load_order_from_disk(id)
│   └── load_all_from_disk()
│
└── Reporting
    └── get_statistics()
```

---

## Usage Examples

### Example 1: Create Off-Book Order (Condition-Based)

```python
from unified_order_model import (
    UnifiedOrderConfig, EntryConditionConfig, 
    StopLossConfig, TargetConfig
)
from unified_order_manager import UnifiedOrderManager

manager = UnifiedOrderManager()

# Entry: Trigger when price breaks above 5-candle high on 15min chart
entry = EntryConditionConfig(
    condition_type='candle_breakout',
    candle_timeframe='15min',
    candle_lookback=5,
    candle_break_direction='above_high',
    candle_offset_pct=0.0,  # Exact break, no offset
)

# Stop: Fixed price at $155.00
stop = StopLossConfig(
    stop_type='fixed_price',
    fixed_price=155.00,
)

# Create and register
success, result = manager.create_offbook_order(
    symbol='DGXX',
    side='short',
    quantity=100,
    entry_condition=entry,
    stop_loss=stop,
    notes='Off-book: Breakout short trade'
)

if success:
    print(f"Created order: {result}")
```

### Example 2: Create Automated Multi-Level Order

```python
# Entry: At Fast SMA with -0.5% offset (below)
entry = EntryConditionConfig(
    condition_type='immediate',
    indicator_type='sma_fast',
    indicator_offset_pct=-0.5,
)

# Stop: ATR multiple (1.5× ATR below entry)
stop = StopLossConfig(
    stop_type='atr_multiple',
    atr_multiplier=1.5,
)

# Targets: Multiple exit points
targets = [
    TargetConfig(
        target_type='fibonacci',
        fib_level='fibonacci_61_8',
        fib_offset_pct=0.0,
        percent_of_position=50.0,  # Exit 50% at Fib
    ),
    TargetConfig(
        target_type='percent_gain',
        gain_percent=10.0,
        percent_of_position=30.0,  # Exit 30% at +10%
    ),
    TargetConfig(
        target_type='trailing_stop_percent',
        trail_percent=2.0,
        percent_of_position=20.0,  # Exit 20% on trailing stop
    ),
]

# Create multi-level order
success, result = manager.create_automated_order(
    symbol='AAPL',
    side='long',
    entry=entry,
    targets=targets,
    stop_loss=stop,
    quantity=100,
    notes='Automated: Multi-level entry at SMA'
)
```

### Example 3: Create Manual Order with Share Calculation

```python
from share_calculator import ShareCalculator
from price_resolver import PriceResolutionContext, PriceResolver

# Market context
context = PriceResolutionContext()
context.current_price = 50.25
context.atr = 1.50

# Entry: At market (or with limit offset)
entry = EntryConditionConfig(
    condition_type='immediate',
    order_type='market',
)

# Stop: 2% loss
stop = StopLossConfig(
    stop_type='percent_loss',
    loss_percent=2.0,
)

# Calculate stop price
stop_price, _ = PriceResolver.resolve_stop_price(50.25, stop, context)
# Result: 50.25 - (50.25 × 2%) = $49.25

# Target: 5% gain
target = TargetConfig(
    target_type='percent_gain',
    gain_percent=5.0,
    percent_of_position=100.0,
)

# Calculate shares from amount
shares, _ = ShareCalculator.calculate_from_amount(
    amount_dollars=1000.0,
    current_price=50.25,
)
# Result: 1000 / 50.25 = 19 shares (rounded down)

# Create manual order
success, order_id = manager.create_manual_order(
    symbol='MSFT',
    side='long',
    quantity=shares,
    entry_price=50.25,
    profit_target=target,
    stop_loss=stop,
    notes=f'Manual: Risk $19.75 ({2}% of {50.25}), target ${50.25 * 1.05}'
)
```

### Example 4: Prepare and Submit Order

```python
# Get a pending order
orders = manager.get_pending_orders()
order = orders[0]

# Build market context
context = PriceResolutionContext()
context.current_price = 50.25
context.bid = 50.23
context.ask = 50.27
context.prev_close = 50.10
context.vwap = 50.15
context.sma_fast = 50.05
context.atr = 1.50

# Prepare for submission
success, warnings = manager.prepare_for_submission(
    order=order,
    price_context=context,
    current_price=50.25,
    account_size=100000.0,
)

# Check for warnings
if warnings:
    for warning in warnings:
        print(f"⚠️  {warning}")

# Submit
if success:
    success, msg = manager.submit_order(order)
    if success:
        print(f"✓ Order submitted: {msg}")
    else:
        print(f"✗ Submission failed: {msg}")
```

---

## New Features Enabled by Consolidation

### 1. Candle-Based Targets for Automated Orders ✓

```python
# Now automated orders can use candle-based targets
target = TargetConfig(
    target_type='candle_high',
    timeframe='1h',  # High of 1-hour candle
    price_ref_offset_pct=0.5,  # Plus 0.5%
    percent_of_position=30.0,
)
```

### 2. Share Calculation from Amount ✓

```python
# All order modes now support share calculation from amount
config = ShareCalculationConfig(
    calculation_method='from_amount',
    amount_dollars=1000.0,  # Trade $1000
)
order.shares_config = config
```

### 3. Session-Aware Order Handling ✓

```python
# Orders automatically adjust for pre-market and after-hours
# No more manual bracket order conversion needed!
order.session.session_type = 'extended'  # Works PM + AH
# System automatically:
# - Sets outsideRth=true
# - Converts TIF to GTC
# - Splits into PM and AH orders if needed
```

### 4. Trailing Stop with Candle Timeframe ✓

```python
stop = StopLossConfig(
    stop_type='trailing_stop_candle',
    trail_candle_timeframe='15min',  # Low of 15-min candle
    trail_candle_offset_pct=-0.5,  # Minus 0.5%
)
```

### 5. Fibonacci 100% Extension ✓

```python
target = TargetConfig(
    target_type='fibonacci',
    fib_level='fibonacci_100_0',  # Extension target
    fib_offset_pct=0.0,
    percent_of_position=10.0,
)
```

### 6. Interchangeable Entry/Stop/Target Options ✓

```python
# Can now mix-and-match ANY combination:
# - Off-book entry with automated targets
# - Automated entry with manual stop
# - Manual entry with candle-based exits
# All work together seamlessly!
```

---

## Migration Path from Old System

### Off-Book Orders → Unified

**Old:**
```python
held_order = HeldOrder(symbol='AAPL', side='long', quantity=100)
held_order.entry_conditions.append(
    HeldOrderCondition(condition_type='candle_breakout', ...)
)
```

**New:**
```python
order = UnifiedOrderConfig(
    mode='offbook',
    symbol='AAPL',
    side='long',
    quantity=100,
    entry=EntryConditionConfig(condition_type='candle_breakout', ...),
)
manager.register_order(order)
```

### Automated Orders → Unified

**Old:**
```python
level = MultiLevelOrderLevel(...)
multiLevelOrderAdvanced(symbol, levels)
```

**New:**
```python
order = UnifiedOrderConfig(
    mode='automated',
    symbol='AAPL',
    entry=entry_config,
    targets=[target1, target2, target3],
    stop_loss=stop_config,
)
manager.submit_order(order)
```

### Manual Orders → Unified

**Old:**
```python
# Form submission
form = Parameters(...)
# Directly to IBKR
```

**New:**
```python
order = UnifiedOrderConfig(
    mode='manual',
    symbol='AAPL',
    quantity=100,
    entry_price=150.00,
    targets=[target_config],
    stop_loss=stop_config,
)
manager.register_order(order)
manager.prepare_for_submission(order, context)
manager.submit_order(order)
```

---

## Next Phase: Intelligent Order Suggestions

**Phase 2** (coming next) will add:

1. **Intelligent Entry Selection**
   - Analyze price action and key levels
   - Factor in time-of-day biases
   - Detect confluence points
   - Suggest best entry from available options

2. **Intelligent Stop & Target Placement**
   - Calculate based on ATR + risk/reward ratio
   - Place stops behind support/resistance
   - Suggest Fibonacci extensions for targets
   - Adjust for volatility regime

3. **Backtesting Integration**
   - Test candidate strategies against historical data
   - Rank by win rate and profit factor
   - Suggest best-performing strategy
   - Track performance over time

4. **Advanced Timing**
   - Entry selection based on time of day
   - News release timing
   - Keyword significance
   - Technical analysis confluence

---

## API Summary

### UnifiedOrderManager

**Creation:**
- `create_offbook_order(symbol, side, quantity, entry_condition, stop_loss, notes)`
- `create_automated_order(symbol, side, entry, targets, stop_loss, quantity, notes)`
- `create_manual_order(symbol, side, quantity, entry_price, profit_target, stop_loss, notes)`

**Retrieval:**
- `get_order(order_id)`
- `get_orders_by_symbol(symbol, status)`
- `get_orders_by_mode(mode, status)`
- `get_pending_orders()`
- `get_active_orders()`
- `get_offbook_active()`

**Preparation:**
- `calculate_prices(order, context)`
- `calculate_shares(order, current_price, account_size)`
- `prepare_for_submission(order, price_context, current_price, account_size)`

**Submission:**
- `register_order(order)`
- `submit_order(order)`

**Persistence:**
- `load_all_from_disk()`

**Reporting:**
- `get_statistics()`

---

## Configuration Files Needed

The system works with market data from these sources:

1. **Price Resolution Context** - Real-time market data
   - Current price, bid/ask, last
   - Day high/low, previous close
   - Indicator values (VWAP, SMA, EMA, ATR)
   - Fibonacci levels (calculated from swing)
   - Candle data (timeframe → [candles])

2. **Session Information** - Current trading session
   - Automatically detected from timestamp
   - Can be manually specified

3. **Account Information** (for risk-based share calculation)
   - Account size
   - Risk percent per trade

---

## Known Limitations & Future Work

**Current Limitations:**
- Price resolution requires market data context to be built separately
- IBKR/monitor routing not yet implemented (framework ready)
- Backtesting engine not yet integrated
- AI suggestion engine not yet implemented

**Future Enhancements:**
- Real-time price context builder from market data
- Full IBKR API integration
- Strategy performance tracking
- Strategy library / favorites system
- Backtesting comparison engine
- Automated intelligent order suggestions

---

## Support & Troubleshooting

**Price Resolution Issues:**
- Check that market data context has required fields
- Verify indicator calculations are current
- Check candle timeframe data availability

**Share Calculation Issues:**
- Verify current_price > 0
- For risk-based: ensure entry_price and stop_price are different
- For amount-based: ensure amount is sufficient for at least 1 share

**Session Issues:**
- Check current time is within expected trading hours
- Verify outsideRth flag set correctly for extended hours
- Ensure GTC used for PM/AH orders

---

## Files Included

```
Core Modules:
├── unified_order_model.py ........... Data classes and models
├── unified_order_constants.py ....... Consolidated options
├── price_resolver.py ............... Price calculation engine
├── share_calculator.py ............. Share quantity engine
├── session_handler.py .............. Session/hours handling
└── unified_order_manager.py ......... Central orchestrator

This Document:
└── UNIFIED_ORDER_SYSTEM_GUIDE.md .... Complete documentation
```

---

## Questions & Examples

For more detailed examples and advanced usage, see code comments in each module.

**Contact**: See order manager logs for diagnostic information.

