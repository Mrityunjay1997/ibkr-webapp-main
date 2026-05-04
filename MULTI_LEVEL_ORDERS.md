# Advanced Multi-Level Order System

## Overview

The Advanced Multi-Level Order System allows you to create sophisticated trading strategies with:
- **Multiple entry levels** with different quantities
- **Multiple exit targets per level** with position scaling (e.g., 50% at first target, 30% at second, 20% at third)
- **Flexible price reference system** for entries, stops, and targets
- **100% customizable** using technical indicators, Fibonacci levels, pivot points, or custom prices
- **Full order automation** ready for autonomous trading

This system is designed as a bridge toward fully automated trading while maintaining complete control over your strategy parameters.

---

## Quick Start Example

### Scenario: Safe Long Entry Strategy
You want to buy 300 shares total, but scale into 3 levels:
- **Level 1:** 100 shares @ VWAP
- **Level 2:** 100 shares @ VWAP - 2%
- **Level 3:** 100 shares @ VWAP - 4%

For each level, you want multiple exits:
- **Level 1 Exits:**
  - Sell 50% at High of Day + 5%
  - Sell 30% at Fibonacci 61.8%
  - Sell 20% at +15% profit target

---

## Available Price References

### 1. Technical Indicators
Use any of these calculated indicators as reference points:
- **VWAP** - Volume Weighted Average Price
- **SMA Fast** - Short-term Simple Moving Average
- **SMA Medium** - Medium-term Simple Moving Average
- **SMA Slow** - Long-term Simple Moving Average (often 200-day)
- **EMA Fast** - Short-term Exponential Moving Average
- **EMA Slow** - Long-term Exponential Moving Average
- **RSI** - Relative Strength Index
- **ATR** - Average True Range

**With Offset:** All indicators support ±% offsets
- `-2%` means 2% below the indicator value
- `+3%` means 3% above the indicator value

### 2. Fibonacci Levels
Standard Fibonacci retracement levels for scalp trades:
- **23.6%** - Shallow pullback
- **38.2%** - Light pullback
- **50.0%** - Medium pullback
- **61.8%** - Deep pullback
- **78.6%** - Very deep pullback

**With Offset:** Each can have ±% offset applied
- "fibonacci_61.8" with offset +1% = 61.8% level pushed up 1%

### 3. Pivot Points
Classical pivot point system:
- **Pivot** - (High + Low + Close) / 3
- **Support 1** - (Pivot × 2) - High
- **Support 2** - Pivot - (High - Low)
- **Resistance 1** - (Pivot × 2) - Low
- **Resistance 2** - Pivot + (High - Low)

### 4. Price Levels
Daily price reference points:
- **Day High** - Highest price of the day
- **Day Low** - Lowest price of the day
- **Previous Close** - Yesterday's closing price
- **Gap Close** - Previous close (marks yesterday's gap)

### 5. 100% Price Targets ⭐ NEW
Direct percentage gains from the previous close:
- **+5%** = 5% above yesterday's close
- **-2%** = 2% below yesterday's close
- **+10%** = 10% above yesterday's close

Perfect for:
- Setting specific profit targets
- Day trading fixed risk/reward ratios
- Momentum exits

### 6. Custom Prices
Enter any fixed price you want for entries, stops, or targets.

---

## Order Types

### Entry Order Types
- **Limit Order** - Execute at or better than specified price
- **Market Order** - Execute immediately at best available price

### Exit/Stop Order Types
- **Limit Order** - Sell at or better than specified price
- **Market Order** - Sell immediately at market price
- **Stop Order** - Trigger market sell when price drops to stop price
- **Trailing Stop** - Dynamic stop that trails behind price movement
  - $ Amount: stops trail at fixed dollar distance
  - % Amount: stops trail at fixed percentage distance

---

## Building Your Strategy

### Step 1: Configure Entry Levels

For each entry level:
1. **Quantity** - How many shares to buy at this level
2. **Price Reference** - Where to enter (VWAP, SMA, custom price, etc.)
3. **Offset %** - Adjust above/below the reference
4. **Order Type** - Limit or Market

**Example:**
```
Level 1: 100 shares @ VWAP - 1%
Level 2: 100 shares @ VWAP - 3%
Level 3: 50 shares @ Previous Close (no offset)
```

### Step 2: Configure Stop Loss

For each level, set ONE stop loss price reference:

**Example:**
```
Level 1 Stop: Previous Close - 5%
Level 2 Stop: Fibonacci 38.2%
Level 3 Stop: Custom price $120
```

**Tips:**
- If no stop is set, none will be created
- All shares from a level are exited by its stop
- You can use wider stops on first levels, tighter on later levels

### Step 3: Configure Sell Targets (Multiple Per Level!)

This is the powerful part. For each entry level, create MULTIPLE exit targets:

**Level 1 Example (100 shares entered):**
- Target 1: 50% of position at High of Day + 5%
- Target 2: 30% of position at Fib 61.8%
- Target 3: 20% of position at +15% profit target

**System will create:**
- 1 parent Buy order: 100 shares @ VWAP - 1%
- 3 exit orders (children of the parent):
  - Sell 50 shares @ High of Day + 5%
  - Sell 30 shares @ Fib 61.8%
  - Sell 20 shares @ +15% price target
- 1 stop order: Sell 100 shares @ Previous Close - 5%

### Step 4: Review & Submit

Before submitting:
1. Verify all price references resolve to realistic prices
2. Check position percentages sum close to 100%
3. Review the example strategy in the modal
4. Click "Place Multi-Level Orders"

---

## Advanced Tips for Automation

### For Moving Toward Full Automation

1. **Use Technical Indicators as Base**
   - Entries based on VWAP, SMA crossovers
   - Targets based on Fib levels or ATR multiples
   - Stops based on previous day's range

2. **Create Pre-built Presets**
   - Save your tested strategies as presets
   - Load instantly for recurring setups
   - Example: "Morning_Gap_Long", "Fib_Pullback_Scalp"

3. **Parameter Testing**
   - Test different offsets on paper trading
   - Document what works for your stocks
   - Build a library of proven strategies

4. **Next Phase (Planned)**
   - Automatic order generation based on screener results
   - Conditional order submission (e.g., only if RSI < 30)
   - Real-time position management and scaling
   - Automated profit/loss alerts

---

## Examples

### Example 1: Conservative Entry with Multi-Target Exit

**Goal:** Safe entry with scaled exits

```
LEVEL 1: 50 shares @ VWAP
  Stop: Previous Close - 3%
  Exit 1 (40%): High of Day
  Exit 2 (60%): +8% price target

LEVEL 2: 50 shares @ VWAP - 2%
  Stop: Previous Close - 3%
  Exit 1 (50%): Fib 61.8%
  Exit 2 (50%): +12% price target
```

**Why this works:**
- Conservative first entry near VWAP
- Aggressive entries on pullbacks
- Early exits at natural resistance (HOD)
- Tail profit targets capture big moves

---

### Example 2: Fibonacci Scaling Strategy

**Goal:** Scalp pullbacks with 3-level entry

```
LEVEL 1: 100 shares @ Fib 23.6% + 1%
  Stop: Fib 0% - 2%
  Exit 1 (50%): Fib 61.8% + 2%
  Exit 2 (50%): +5% price target

LEVEL 2: 100 shares @ Fib 38.2%
  Stop: Fib 0% - 2%
  Exit 1 (60%): Fib 78.6%
  Exit 2 (40%): +10% price target

LEVEL 3: 50 shares @ Fib 50%
  Stop: Fib 0% - 2%
  Exit 1 (100%): +8% price target
```

**Why this works:**
- Buys at each Fib level as price pulls back
- Tight stops based on full pullback range
- Exits scale from conservative to aggressive
- Natural support/resistance levels

---

### Example 3: Gap-Based Strategy (Day Trading)

**Goal:** Trade overnight gaps with defined risk

```
LEVEL 1: 200 shares @ Gap Close + 1% (Previous Close + 1%)
  Stop: Gap Close - 2%
  Exit 1 (30%): Day High + 2%
  Exit 2 (40%): +5% price target
  Exit 3 (30%): +10% price target

LEVEL 2: 100 shares @ Gap Close - 1%
  Stop: Gap Close - 2%
  Exit 1 (50%): Day High
  Exit 2 (50%): +7% price target
```

**Why this works:**
- Entries right at previous close (fills the gap)
- Exits use day's high as natural resistance
- Fixed percentage targets = known risk/reward
- Good for pre-market/post-market trading

---

## Troubleshooting

### Issue: "Could not resolve entry price"
- **Cause:** The price reference doesn't have data (e.g., VWAP with no volume)
- **Solution:** Use Previous Close or Day High as fallback

### Issue: Position percentages don't add up
- **Cause:** You set exits to 50% + 30% + 40% instead of 100%
- **Solution:** Adjust percentages to sum to 100%, or system will auto-normalize

### Issue: Stop prices are unrealistic
- **Cause:** Offset too large (e.g., -20% from High of Day)
- **Solution:** Use Previous Close or SMA for stops, smaller offsets

### Issue: Orders aren't filling
- **Cause:** Limit prices too tight, or market conditions changed
- **Solution:** Use market orders for entries, or wider limits

---

## Next Steps: Toward Full Automation

This system is designed as a stepping stone. The planned roadmap:

1. **Phase 2: Conditional Orders**
   - "Only place if RSI < 30"
   - "Only place if gap > 3%"
   - "Only place if volume > 2M"

2. **Phase 3: Auto-Screener Integration**
   - Automatically generate orders for stocks matching criteria
   - Batch order submission

3. **Phase 4: Live Position Management**
   - Monitor fill prices
   - Auto-adjust trailing stops
   - Real-time P&L alerts

4. **Phase 5: Full Automation**
   - Entry signals from technical analysis
   - Exit signals from indicators
   - Position sizing based on volatility
   - No manual intervention needed

---

## Tips for Success

1. **Start with presets** - Use proven strategies first
2. **Paper trade new ideas** - Test before risking real money
3. **Keep stops tight** - Define max loss upfront
4. **Scale into winners** - Use multiple entry levels
5. **Document your wins** - Build your strategy library
6. **Review execution** - Track what worked, what didn't

---

## Support & Questions

For issues or questions, check:
1. The example strategies above
2. The tooltips in the multi-level order modal
3. The order preset library for similar strategies

Good luck building your automated trading system! 🚀
