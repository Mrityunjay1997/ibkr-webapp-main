# Multi-Level Order System - Quick Start Guide

## What's New?

You now have a complete **Multi-Level Order Builder** that lets you:
- Create orders with 2+ levels, each with different entry prices and exits
- Use powerful price references (VWAP, SMAs, Fibonacci, etc.) with offsets
- Save order templates as presets for quick reuse
- Submit all levels simultaneously to IBKR

## Quick Setup (5 minutes)

### 1. Open the Multi-Level Order Builder
- In the main trading dashboard, look for the **Multi-Level Order Builder** modal button
- Or it appears in the order entry toolbar

### 2. Configure Your First Order

**Basic Settings:**
```
Symbol: AAPL
Action: BUY (or SELL)
TIF: DAY (or GTC for good-till-canceled)
Extended Hours: OFF (toggle if needed)
```

**Add Level 1:**
```
Quantity: 100
Entry: VWAP - 2% (buy on weakness)
Exit: Fibonacci 61.8% + 1% (natural target)
Stop: Support 1 - 0.5% (tight risk)
```

**Add Level 2:**
```
Quantity: 50
Entry: Fibonacci 50% - 1% (scale in)
Exit: Trailing Stop $0.50 (let winners run)
Stop: Support 1 - 0.5% (same risk)
```

**Submit:**
Click "Place Multi-Level Orders"

### 3. Save as Preset (Optional)

Before submitting, enter a name and click "Save":
```
Preset Name: "Fibonacci 2-Level AAPL"
```

Load it anytime by selecting from the preset dropdown and clicking "Load".

## Common Strategies

### Strategy 1: VWAP Bounce
Use when price bounces off VWAP support.

```
Level 1: 100 shares @ VWAP - 1%
  → Exit at SMA Slow + 0.5%
  → Stop at VWAP - 2%

Level 2: 50 shares @ VWAP - 2.5%
  → Exit at Trailing Stop $1.00
  → Stop at VWAP - 3%
```

### Strategy 2: Fibonacci Pullback
Use when price pulls back to Fibonacci levels.

```
Level 1: 150 shares @ Fib 38.2% - 1%
  → Exit at Fib 61.8% + 0.5%
  → Stop at Fib 23.6%

Level 2: 75 shares @ Fib 50% - 0.5%
  → Exit at Trailing Stop $0.75
  → Stop at Fib 23.6%
```

### Strategy 3: SMA Crossover Fade
Use when price crosses SMA on pullback.

```
Level 1: 120 shares @ SMA Medium - 1%
  → Exit at SMA Slow + 0.5%
  → Stop at SMA Fast - 0.5%

Level 2: 60 shares @ SMA Slow - 1%
  → Exit at 2.0% profit
  → Stop at SMA Slow - 1.5%
```

## Price Reference Options at a Glance

### Technical Indicators
| Reference | What It Is | Common Offset |
|-----------|-----------|---------------|
| VWAP | Volume-weighted price | ±2% |
| SMA Fast | 5-period simple average | ±0.5% to ±2% |
| SMA Medium | 10-period average | ±0.5% to ±1% |
| SMA Slow | 20-period average | ±0.5% |
| EMA Fast | 5-period exponential | ±1% |
| EMA Slow | 10-period exponential | ±0.5% |
| Prev Close | Yesterday's close | ±0.5% to ±3% |

### Fibonacci Levels
| Level | When To Use | Common Offset |
|-------|-----------|---------------|
| 23.6% | Shallow pullback entries | ±0.5% |
| 38.2% | Moderate pullback | ±0.5% to ±1% |
| 50.0% | Mid-point pullback | ±0.5% to ±1% |
| 61.8% | Deep pullback (natural support) | ±0.5% to ±2% |
| 78.6% | Very deep pullback | ±1% to ±2% |

### Support/Resistance
| Level | Definition |
|-------|-----------|
| Support 1 | Day's lowest price so far |
| Resistance 1 | Day's highest price so far |
| Day High | Current day high |
| Day Low | Current day low |

## Order Type Meanings

| Type | Meaning | Best For |
|------|---------|----------|
| **Limit** | Buy/sell at specific price or better | Entry, precise exits |
| **Market** | Buy/sell at best available price NOW | Fast execution |
| **Stop** | Trigger when price crosses level | Stop-loss orders |
| **Trailing** | Automatically adjust with profit | Protecting gains |

## Working with Presets

### Save a Preset
1. Configure your order levels
2. Click the "Preset name" field
3. Type a name (e.g., "Fib 2-Level Scalp")
4. Click "Save"
5. Preset saved to disk!

### Load a Preset
1. Click the preset dropdown at top
2. Select your saved strategy
3. Click "Load"
4. All levels populate instantly
5. Modify if needed, then submit

### Delete a Preset
1. Select from dropdown
2. Click "Delete"
3. Confirm when prompted

## Tips & Tricks

### ✓ Do's
- ✓ Test presets on paper trading first
- ✓ Start with 2-3 levels, scale up as comfortable
- ✓ Use similar stop levels across levels (easier risk management)
- ✓ Document strategy in "Strategy Notes" field
- ✓ Use negative offsets for entry (to buy weakness/sell strength)
- ✓ Use positive offsets for exits (to target moves)

### ✗ Don'ts
- ✗ Don't use market orders for entries in volatile stocks
- ✗ Don't forget to set stop-loss levels!
- ✗ Don't use unrealistic offsets (e.g., VWAP + 10%)
- ✗ Don't submit without checking symbol is correct
- ✗ Don't leave "Extended Hours" on unless you trade outside 9:30-16:00

## Troubleshooting

### "Orders submitted but prices look wrong"
- Market data may not be live. Check TWS data subscriptions.
- Prices calculated at submission time, not in real-time.

### "Can't see Multi-Level Order Builder"
- Try scrolling down on the page
- Check browser console for errors (F12)
- Reload the page

### "Presets not showing in dropdown"
- Click "Load Preset" dropdown again
- If symbol changed, dropdown filters by symbol
- Create a new preset if needed

### "Error submitting orders"
- Check IBKR connection (verify in TWS Gateway)
- Verify symbol is valid
- Check that order prices make sense (check bid/ask)

## Next Steps

1. **Practice**: Create a 2-level order as a preset
2. **Test**: Try on paper trading first
3. **Iterate**: Save different variations as presets
4. **Scale**: Add levels as you get comfortable
5. **Automate**: Eventually integrate with Auto-Orders (future feature)

## Example Complete Workflow

```
STEP 1: Market opens, you see AAPL bouncing off VWAP
↓
STEP 2: Open Multi-Level Order Builder
↓
STEP 3: Enter Symbol = AAPL, Action = BUY
↓
STEP 4: Add Level 1 (100 shares @ VWAP - 1%)
↓
STEP 5: Add Level 2 (50 shares @ VWAP - 2%)
↓
STEP 6: Set exits and stops for each
↓
STEP 7: Type preset name "AAPL Bounce v1"
↓
STEP 8: Click "Save" (saved for future use!)
↓
STEP 9: Review strategy notes
↓
STEP 10: Click "Place Multi-Level Orders"
↓
✓ Orders submitted to IBKR!
```

## Support & Documentation

- Full documentation: See `MULTI_LEVEL_ORDER_SYSTEM.md`
- Code reference: See `order_manager.py`
- Questions? Check the strategy notes in your saved presets

---

**You're all set!** Start building smarter multi-level orders today.
