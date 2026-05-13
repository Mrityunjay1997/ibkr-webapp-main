# Multi-Level Order Strategy Builder Guide

## Overview

The enhanced Multi-Level Order Builder now includes powerful strategy selection and customization features. You can now:

- **Select pre-built entry strategies** from a dropdown
- **Select pre-built exit strategies** from a dropdown  
- **Apply combined strategies** (entry + exit packages)
- **Create custom "off-book" strategies** for specialized trading approaches

---

## 📥 Entry Strategies

Choose from these predefined entry points to automatically configure how your buy orders are placed:

### Entry Strategy Options

| Strategy | Price Reference | Offset | Best For |
|----------|-----------------|--------|----------|
| **VWAP Conservative** | VWAP | -2% | Risk-averse entries |
| **VWAP Aggressive** | VWAP | -1% | Active traders |
| **VWAP at Support** | VWAP | -3% | Support bounces |
| **SMA Fast Crossover** | SMA Fast | -0.5% | Momentum trading |
| **SMA Medium Crossover** | SMA Medium | 0% | Trend following |
| **EMA Fast Bounce** | EMA Fast | +1% | Pullback entries |
| **Previous Close Support** | Previous Close | -1% | Day trading |
| **Day High Breakout** | Day High | +2% | Breakout trading |
| **Fibonacci 23.6% Entry** | Fib 23.6% | 0% | Retracement levels |
| **Market Order** | Custom | 0% | Immediate execution |

**How to use:**
1. Open the Multi-Level Order Builder modal
2. Select an entry strategy from the "📥 Entry Strategy" dropdown
3. The entry price configuration will be applied to ALL current levels
4. You can still customize individual levels if needed

---

## 📤 Exit/Stop Strategies

Choose how you want to scale out of positions or set stop losses:

### Exit Strategy Options

| Strategy | Levels | Distribution | Best For |
|----------|--------|---------------|----------|
| **Fibonacci Scale Out** | 3 targets | 30-40-30 | Fib traders |
| **ATR-Based Exits** | 3 targets | 1x, 2x, 3x ATR | Volatility adapters |
| **Fixed Profit Targets** | 3 targets | +2%, +5%, +10% | Quick scalps |
| **Trailing Stop** | 3 targets | 2% trailing + 3/6/10% | Trend protection |
| **Pivot Scale Out** | 3 targets | S1, Pivot, R1 | Pivot traders |
| **EMA Fast Exit** | 3 targets | Step targets | EMA followers |
| **Quick Profit Scalp** | 3 targets | +1%, +3%, +5% | Ultra-quick exits |
| **Aggressive Scale** | 3 targets | 30-40-30 mixed | Aggressive traders |

**How to use:**
1. Select an exit strategy from the "📤 Exit/Stop Strategy" dropdown
2. Stop loss and all take-profit targets are automatically configured
3. Adjust individual targets if needed for fine-tuning

---

## 🔗 Combined Strategies (Pre-Built Packages)

Apply complete entry + exit combinations with one click:

### Combined Strategy Options

| Strategy | Entry | Stop Loss | Targets | Risk Profile |
|----------|-------|-----------|---------|--------------|
| **Conservative** | VWAP -2% | PC -2.5% | +2%, +4%, +6% | Low risk |
| **Moderate** | VWAP -1.5% | Pivot -1% | Fib levels | Medium risk |
| **Aggressive** | VWAP -0.5% | PC -1.5% | 1-3x ATR | Higher risk |
| **Breakout Strategy** | Day High +2% | PC -2% | +3%, +6%, +10% | Breakout plays |
| **Scalp Strategy** | VWAP -1% | PC -0.75% | +1%, +2% | Quick flips |
| **Swing Trade** | SMA Medium -1% | S1 | Fib + R2 | Multi-day holds |
| **Gap Play** | PC -1% | -1x ATR | +2%, +5%, +8% | Gap traders |

**How to use:**
1. Select a combined strategy from the "🔗 Combined Strategy" dropdown
2. BOTH entry and exit strategies are applied in one action
3. Perfect for complete trade setups

---

## 🔧 Off-Book Strategy Builder (Custom Strategies)

Create completely custom entry/exit combinations for your specific trading style:

### Step-by-Step Custom Strategy Creation

**1. Open the Builder:**
- Click the **"🔗 Off-Book Strategy Builder"** button to expand the custom strategy panel

**2. Configure Entry:**
- Select a **Price Reference** (VWAP, SMA, Fibonacci, etc.)
- Enter an **Offset %** (positive/negative adjustment)
- Entry type defaults to Limit Order

**3. Configure Stop Loss:**
- Select a **Price Reference** for your stop
- Enter an **Offset %** adjustment
- Stop type defaults to Stop Order

**4. Add Exit Targets:**
- Click **"+ Add Exit Target"** to add multiple profit targets
- For each target, set:
  - **Price Reference** (where to exit)
  - **Offset %** (adjustment from that level)
  - **Order Type** (Limit, Market, Stop)
  - **% of Position** (what % to sell at this level)
- Example: 40% at first target, 35% at second, 25% at third

**5. Optional: Name Your Strategy**
- Enter a name (e.g., "My Gap Play Setup")
- This appears in the status bar after applying

**6. Apply Strategy:**
- Click **"✓ Apply Custom Strategy"** button
- The custom setup is applied to ALL current levels
- The builder collapses and shows active strategy status

---

## 📝 Practical Examples

### Example 1: Conservative Gap Play (Combined)
1. Select "Gap Play Strategy" from Combined Strategies dropdown
2. All levels get: Entry at Previous Close -1%, Stop at -1x ATR, Targets +2%/+5%/+8%

### Example 2: Custom VWAP + EMA Combo (Off-Book)
1. Click "Off-Book Strategy Builder"
2. Entry: Select VWAP, offset -1.5%
3. Stop: Select EMA Fast, offset -2%
4. Add 3 targets:
   - Fibonacci 38.2% (40% of position)
   - Day High +1% (35% of position)
   - +10% target (25% of position)
5. Name it "VWAP-EMA Swing"
6. Click "Apply Custom Strategy"

### Example 3: Aggressive 3-Level Scalp (Off-Book)
1. Click "Off-Book Strategy Builder"
2. Entry: VWAP, offset -0.5%
3. Stop: Previous Close, offset -1%
4. Add 2 quick targets:
   - +1% (50% of position)
   - +2% (50% of position)
5. Apply to all levels

---

## ⚙️ Advanced Tips

### Combining Strategies
- Apply a **Combined Strategy** first for quick setup
- Then switch to **Off-Book Builder** to fine-tune specific targets
- Each application overwrites previous settings

### Multi-Level Optimization
- Each level maintains the same strategy
- Modify individual levels after applying strategy for nuanced approaches
- Add more levels by clicking "Add Level" button

### Position Sizing with Target %
- Targets must add up to 100% (or less if you hold through)
- Example: 30% + 40% + 30% = 100% full exit
- Example: 50% + 50% = 100% (only 2 targets)
- Example: 40% + 40% = 80% (hold 20%)

### Order Type Selection
- **Limit**: Most popular for targets (specify exact price)
- **Market**: Immediate execution (slippage risk)
- **Stop**: Triggers on price hit (use for exits)
- **Trail**: Follows price up/down by % amount

---

## 💾 Saving Custom Strategies

### Method 1: Save as Preset
1. Create your custom strategy
2. Enter a **Preset Name** (e.g., "My Custom Setup")
3. Click **"Save"** button
4. Later, select preset from "Load Preset" dropdown
5. Click **"Load"** to reuse

### Method 2: Copy Settings
- Take screenshots of Off-Book Builder settings
- Document your custom offset %s and targets
- Re-enter later as needed

---

## 🎯 When to Use Each Strategy Type

| Situation | Recommendation |
|-----------|-----------------|
| Quick entry, don't know stops | Use **Combined Strategy** first |
| Following a technical level | Use **Entry Strategy** dropdown |
| Focus on scale-out approach | Use **Exit Strategy** dropdown |
| Custom ratio or niche setup | Use **Off-Book Builder** |
| Reusing same setup repeatedly | **Save as Preset** |

---

## 📊 Strategy Status Display

After applying a strategy, you'll see a status bar showing:
- **Active Strategy: [Entry] ✕ [Exit]** for separate strategies
- **Active Strategy: [Combined Name]** for combined strategies
- **Active Strategy: Custom: [Name] (X targets)** for off-book strategies

This confirms your configuration before placing orders.

---

## ⚡ Quick Reference

### Keyboard-Free Workflow
1. Click "Multi-Level Order Builder"
2. Enter Symbol & Action (BUY/SELL)
3. Select **Combined Strategy** from dropdown
4. Adjust quantity if needed
5. Click "Place Multi-Level Orders"

### Power User Workflow
1. Click "Multi-Level Order Builder"  
2. Use **Entry Strategy** + **Exit Strategy** dropdowns
3. Click "Off-Book Builder" for fine-tuning
4. Add additional levels
5. Save as Preset for future use
6. Submit orders

---

## ❓ FAQ

**Q: Can I mix strategies?**
A: Yes! Apply one, then open Off-Book Builder to customize further.

**Q: Do targets need to add to 100%?**
A: No, you can hold portion (e.g., 50% + 50% = full exit, or 40% + 40% = hold 20%).

**Q: Can I modify strategies after applying?**
A: Yes, click individual fields within each level to adjust.

**Q: What if I want different strategies per level?**
A: Apply strategy to all, then manually edit each level separately.

**Q: How do I add a new entry strategy?**
A: Contact development team to add to MloEntryStrategies object in modal HTML.

---

## 🚀 Next Steps

1. **Try a Combined Strategy** - Fastest way to learn
2. **Build a Custom Strategy** - Practice with Off-Book Builder
3. **Save Your Setups** - Use Presets to reuse favorite strategies
4. **Optimize** - Adjust % allocations and targets based on backtests

Enjoy flexible, template-based multi-level trading!
