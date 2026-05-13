# IBKR Order Architecture - Quick Reference Guide

## 1️⃣ Off-Book Order Flow (Conditional Entry)

```
USER ACTION
    ↓
┌───────────────────────────────────────┐
│ Create Held Order (Off-Book)          │
│ • Symbol, Side, Qty, Limit Price      │
│ • Entry Condition (Candle/MA)         │
│ • TIF, Extended Hours                 │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ Store in HeldOrdersManager            │
│ • In-memory dictionary                │
│ • Status: 'active'                    │
│ • Order NOT sent to IBKR yet          │
└───────────────────────────────────────┘
    ↓
    ↓ MONITORING LOOP (Every 5 seconds)
    ↓
┌───────────────────────────────────────┐
│ ConditionChecker.evaluate_conditions()│
│ • Get market data for symbol          │
│ • Check candle breakout OR MA cross   │
│ • All conditions must be TRUE         │
└───────────────────────────────────────┘
    ↓
    ├─ Condition NOT met → Stay active
    │
    └─ ALL conditions MET → Trigger
            ↓
    ┌──────────────────────────┐
    │ Mark as 'triggered'      │
    │ Send to /sendorders      │
    └──────────────────────────┘
            ↓
    ┌──────────────────────────┐
    │ Submit to IBKR           │
    │ • Create bracket/simple  │
    │ • Place order at entry   │
    │ • Activate profit/stop   │
    └──────────────────────────┘
            ↓
    ┌──────────────────────────┐
    │ Position Live on Exchange│
    │ • Status: 'executed'     │
    │ • Awaiting fill          │
    └──────────────────────────┘
```

**Use Case**: Short DGXX at high + 0.5% offset when price breaks below recent low
- Stored locally, not sent to IBKR
- Waits for breakout confirmation
- Submits limit order at specified price once triggered

---

## 2️⃣ Multi-Level Order Flow (Strategy Execution)

```
USER ACTION
    ↓
┌───────────────────────────────────────┐
│ Define Multi-Level Strategy           │
│ • Level 1: Entry @ VWAP -2%          │
│           3 exits: Fib, %, Support   │
│           Stop @ Pivot -0.5%          │
│ • Level 2: Entry @ Fib 50% -1%       │
│           2 exits: Fib, % gain       │
│           Stop @ Support             │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ Send to /sendorders                   │
│ • multiLevelConfig: JSON strategy     │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ sendorders() processing               │
│ 1. Connect to IBKR                    │
│ 2. Resolve symbol → Contract          │
│ 3. Get market data indicators         │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ PriceReferenceResolver                │
│ For each level:                       │
│   • Resolve entry price               │
│   • Resolve each exit target price    │
│   • Resolve stop-loss price           │
│   Using: VWAP, SMA, ATR, Fib, etc.   │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ multiLevelOrderAdvanced()             │
│ Create order group:                   │
│   Parent Entry (transmit=False)       │
│   └─ Exit 1: 50% qty (transmit=False) │
│   └─ Exit 2: 30% qty (transmit=False) │
│   └─ Exit 3: 20% qty (transmit=True)  │
│   └─ Stop: 100% qty (attached)        │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ placeOrder() for each order           │
│ • Submit to IBKR via API              │
│ • Parent becomes active               │
│ • Exits & stops waiting for fill      │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ IBKR Processing                       │
│ Entry fills → Exits activate          │
│ When exit fills → Other exits cancel  │
│ If stop hits → All exits cancel       │
└───────────────────────────────────────┘
```

---

## 3️⃣ Price Reference Resolution (How Orders Get Prices)

```
INPUT: PriceReference Object
  type: "fibonacci_61.8"
  offset_pct: 1.0
  order_type: "limit"

    ↓

RESOLVER: Get indicator value
  ├─ Look up swing range
  │  └─ day_high: 155.00, day_low: 150.00
  │  └─ range: 5.00
  │
  └─ Calculate Fibonacci level
     └─ day_low + (range × 0.618)
     └─ 150.00 + (5.00 × 0.618)
     └─ 150.00 + 3.09 = 153.09

    ↓

APPLY OFFSET:
  base_price: 153.09
  offset_pct: 1.0
  multiplier: 1.0 + (1.0 / 100) = 1.01
  final_price: 153.09 × 1.01 = 154.62

    ↓

OUTPUT: 154.62 (actual limit price)
```

**Supported Reference Types**:
- **Indicators**: VWAP, SMA fast/medium/slow, EMA, RSI, ATR
- **Fibonacci**: 23.6%, 38.2%, 50%, 61.8%, 78.6%
- **Support/Resistance**: Day high/low, Pivot points, S1/S2, R1/R2
- **Price Levels**: Previous close, Current price, Day high/low
- **Percentage Targets**: % above/below previous close
- **Custom**: Manual price entry

---

## 4️⃣ Order Types Cheat Sheet

| Type | Entry | Execution | Fill Risk | Slippage |
|------|-------|-----------|-----------|----------|
| **Market (MKT)** | Immediate | Now | None | High |
| **Limit (LMT)** | At price or better | Uncertain | May not fill | None |
| **Stop (STP)** | On trigger | Market order | High slippage | High |
| **Trailing (TRAIL)** | On trigger | On level hit | Medium | Medium |
| **Bracket** | Parent fills | Auto fill one leg | Low (managed) | None/Med |
| **Multi-Level** | Multiple entries | Multiple exits | Low (managed) | None/Med |

---

## 5️⃣ Bracket Order Mechanics

```
SCENARIO: Buy 100 @ 150.25 with profit @ 152.50 & stop @ 149.00

ORDER GROUP (transmit chain):
  ┌─ Parent Entry (orderId=1001)
  │  └─ action: BUY, quantity: 100, limit: 150.25
  │  └─ transmit: False ← Don't submit yet
  │
  ├─ Take-Profit Leg (orderId=1002)
  │  └─ action: SELL, quantity: 100, limit: 152.50
  │  └─ parentId: 1001, transmit: False ← Don't submit yet
  │
  └─ Stop-Loss Leg (orderId=1003)
     └─ action: SELL, quantity: 100, auxPrice: 149.00
     └─ parentId: 1001, transmit: True ← THIS TRIGGERS GROUP

IBKR BEHAVIOR:
  1. transmit=True on stop leg triggers entire group
  2. All three orders transmitted to exchange
  3. Parent order becomes active
  4. Profit & stop orders waiting (dormant)
  5. When parent fills @ 150.25:
     ├─ Profit order activates @ 152.50
     ├─ Stop order activates @ 149.00
     └─ First one to hit fills & cancels other

OUTCOMES:
  • Price rises to 152.50 → Profit fills, Stop auto-cancels
  • Price drops to 149.00 → Stop fills, Profit auto-cancels
  • Never both fill (mutually exclusive)
```

---

## 6️⃣ Multi-Level Order Mechanics

```
STRATEGY: Scale in (2 levels) with scale out (multiple exits)

LEVEL 1: Early Entry
  ├─ Parent: BUY 100 @ 150.25 (limit)
  ├─ Exit 1: SELL 50 @ 151.50 (limit) ← 50% of position
  ├─ Exit 2: SELL 30 @ 152.00 (limit) ← 30% of position
  ├─ Exit 3: SELL 20 @ 153.00 (limit) ← 20% of position
  └─ Stop: SELL 100 @ 149.00 (stop)

LEVEL 2: Pyramid Addition
  ├─ Parent: BUY 50 @ 149.50 (limit)
  ├─ Exit 1: SELL 40 @ 151.00 (limit) ← 80% of level 2
  ├─ Exit 2: SELL 10 @ 152.50 (limit) ← 20% of level 2
  └─ Stop: SELL 50 @ 148.50 (stop)

TOTAL POSITION: 150 shares
  ├─ 100 from Level 1
  └─ 50 from Level 2

EXIT ALLOCATION:
  Level 1: 50 + 30 + 20 = 100 (fully scaled)
  Level 2: 40 + 10 = 50 (fully scaled)
  Total exits: 150 (matches position)

ORDER ID SEQUENCE:
  1001: Level 1 Parent Entry
  1002: Level 1 Exit 1
  1003: Level 1 Exit 2
  1004: Level 1 Exit 3
  1005: Level 1 Stop
  1006: Level 2 Parent Entry
  1007: Level 2 Exit 1
  1008: Level 2 Exit 2
  1009: Level 2 Stop
```

---

## 7️⃣ Held Order Condition Types

### Candle Breakout Condition

```
Config:
  timeframe: "5min"
  candles_to_check: 5
  break_direction: "above_high"
  entry_offset_pct: 0.5
  lookback_bars: 5

Evaluation:
  1. Get last 5 candles on 5-min chart
  2. Find highest high: 155.25
  3. Calculate breakout level: 155.25 × (1 + 0.5/100) = 156.03
  4. Check current close: 156.10
  5. Is 156.10 > 156.03? YES → Condition triggered

Use: "Break above recent highs with confirmation buffer"
```

### Moving Average Crossover Condition

```
Config:
  timeframe: "1h"
  ma_type: "sma"
  ma_period: 20
  cross_direction: "above"
  cross_offset_pct: 0.25

Evaluation:
  1. Calculate 20-period SMA: 150.50
  2. Apply offset: 150.50 × (1 + 0.25/100) = 150.88
  3. Previous close: 150.70 (below MA)
  4. Current close: 151.00 (above MA + offset)
  5. Crossover detected? YES → Condition triggered

Use: "Buy when price crosses above 20-SMA on hourly"
```

---

## 8️⃣ Share Calculation Examples

### Multi-Level Exit Allocation

```
Total Position: 100 shares
Targets: [
  {price: 151.50, percent: 50.0},
  {price: 152.00, percent: 30.0},
  {price: 153.00, percent: 20.0}
]

Calculation:
  Exit 1 qty: 100 × (50.0 / 100.0) = 50 shares
  Exit 2 qty: 100 × (30.0 / 100.0) = 30 shares
  Exit 3 qty: 100 × (20.0 / 100.0) = 20 shares
  
Validation:
  50 + 30 + 20 = 100 ✓ (all shares accounted for)
```

### Level Quantity Normalization

```
If percentages don't add to 100%:
  Received: [50%, 25%, 15%] = 90% total
  
Normalize:
  New 1: 50 / 0.90 × 100 = 55.56% → 56 shares
  New 2: 25 / 0.90 × 100 = 27.78% → 27 shares  
  New 3: 15 / 0.90 × 100 = 16.67% → 17 shares
  
Check: 56 + 27 + 17 = 100 ✓
```

---

## 9️⃣ Extended Hours & TIF

```
REGULAR TRADING (RTH)
  Time: 9:30 AM - 4:00 PM ET
  TIF Setting: DAY or GTC (both work)
  outsideRth: False (orders won't fill outside these hours)

EXTENDED HOURS
  Pre-market: 4:00 AM - 9:30 AM ET
  After-hours: 4:00 PM - 8:00 PM ET
  TIF Setting: GTC (must use; DAY expires at 4 PM)
  outsideRth: True (allows execution in extended hours)

EXAMPLE ORDERS:
  
  Order A (Regular Hours Only)
    TIF: DAY
    outsideRth: False
    └─ 4:00 AM: Inactive
       9:30 AM: Active
       4:00 PM: Expires
  
  Order B (Extended Hours)
    TIF: GTC
    outsideRth: True
    └─ 4:00 AM: Active (pre-market)
       9:30 AM: Active (regular)
       4:00 PM: Active (after-hours)
       8:00 PM: Still active
       Next day: Still active
       Until cancelled or 90 days
```

---

## 🔟 API Quick Reference

### Create Held Order
```
POST /held-orders/create
{
  "symbol": "DGXX",
  "side": "short",
  "quantity": 100,
  "order_type": "limit",
  "limit_price": 155.50,
  "tif": "DAY",
  "entry_conditions": [{
    "condition_type": "candle_breakout",
    "config": {
      "timeframe": "5min",
      "break_direction": "below_low",
      "entry_offset_pct": 0.5,
      "lookback_bars": 5
    }
  }],
  "notes": "Short at high"
}
```

### Submit Order to IBKR
```
POST /sendorders
{
  "tickerOrder": "AAPL",
  "longshort": "long",
  "quantity": "100",
  "limitPrice": "150.25",
  "bracketlimit": "bracket",
  "highBraket": "152.50",
  "lowBraket": "149.00",
  "tif": "DAY",
  "outsideRth": "regular",
  "entryType": "limit"
}
```

### List Held Orders
```
GET /held-orders/list?symbol=DGXX

Response:
{
  "status": "ok",
  "orders": [...],
  "count": 5
}
```

### Save Order Preset
```
POST /order-presets/save
{
  "name": "VWAP Bounce Fib Scale",
  "symbol": "AAPL",
  "strategy_notes": "Short-term bounce strategy",
  "levels": [...]
}
```

---

## File Locations Reference

| Feature | Files | Location |
|---------|-------|----------|
| **Order Definition** | order_manager.py | Root |
| **Held Orders** | held_orders_manager.py<br/>held_orders_api.py | Root |
| **Order Submission** | __init__.py (sendorders) | Root |
| **IBKR Integration** | ibkr_signal_engine.py | Root |
| **Forms/UI** | forms.py | Root |
| **Templates** | multi_level_order_modal.html<br/>morfeo.html | /templates |
| **Order Presets** | Stored as JSON | /order_presets |
| **Screening Setups** | Stored as JSON | /setups |
| **Documentation** | HELD_ORDERS_COMPLETE_GUIDE.md | Root |

---

## Key Takeaways

✅ **Off-Book Orders**: Local storage, condition-based triggering, auto-submit to IBKR  
✅ **Multi-Level**: Multiple entries, flexible exits, automatic risk management  
✅ **Price Types**: 12+ reference types (indicators, Fibonacci, support/resistance)  
✅ **Bracket Orders**: Parent + profit + stop (one fills, other auto-cancels)  
✅ **Extended Hours**: TIF=GTC + outsideRth=True for pre/after-market trading  
✅ **Scaling**: Percentage-based exit allocation for position scaling  

