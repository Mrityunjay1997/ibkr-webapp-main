# Multi-OBV Analysis - Quick Reference Card

## One-Page Cheat Sheet

### Enable Feature
```
Form → OBV Analysis Section
☑ Enable Multi-OBV Analysis
Set: Multi-OBV Change Threshold = 5.0%
☑ Enable Multi-OBV Audio Alerts (optional)
☑ Enable Multi-OBV Text-to-Speech (optional)
```

### Signal Types & Meanings

| Signal | Meaning | Action | Confidence |
|--------|---------|--------|------------|
| 🟢 **STRONG BULLISH** | All OBVs ↑ and aligned | BUY or ADD | ⭐⭐⭐⭐⭐ |
| 🟢 **BULLISH** | All OBVs ↑ together | MONITOR for entry | ⭐⭐⭐⭐ |
| 🟡 **NEUTRAL** | Mixed signals | WAIT for clarity | ⭐⭐ |
| 🔴 **BEARISH** | All OBVs ↓ together | EXIT or SHORT | ⭐⭐⭐⭐ |
| 🔴 **STRONG BEARISH** | All OBVs ↓ aligned | SHORT or EXIT | ⭐⭐⭐⭐⭐ |

### The Three OBV Indicators

| Name | Window | Speed | Use |
|------|--------|-------|-----|
| **Fast OBV** | 5 bars | Very fast | Early entry signals |
| **Medium OBV** | 10 bars | Balanced | Confirmation |
| **Slow OBV** | 20 bars | Slow | Trend foundation |

**Rule**: When Fast > Medium > Slow (all positive) = Strong uptrend

### Alignment Types

| Type | Definition | Bullish? |
|------|-----------|----------|
| **Aligned Bullish** | F+ M+ S+ | ✅ YES (LONG) |
| **Aligned Bearish** | F- M- S- | ❌ NO (SHORT) |
| **Misaligned** | Mixed signs | ⚠️ UNCLEAR |

### The Equation Explained

```
Fast OBV: 5000↑ | Medium OBV: 3000↑ | Slow OBV: 1500↑ | 
% Changes: F→M +5.2% | M→S +2.1% | F→S +8.1%
```

- `5000↑` = Value is 5000, arrow shows direction
- `F→M +5.2%` = Fast is 5.2% higher than Medium
- **Good**: All positive and large changes
- **Bad**: Negative changes or opposite directions

### % Change Interpretation

| Change | Means | Risk |
|--------|-------|------|
| F→M **+5%** | Fast stronger than Medium | Pullback likely |
| F→M **-5%** | Medium stronger than Fast | Acceleration coming |
| F→M **-50%** | Opposite directions | DIVERGENCE - reversal risk |

### Quick Signal Reference

```python
Strong Bullish Signal When:
✓ Fast OBV: POSITIVE
✓ Medium OBV: POSITIVE
✓ Slow OBV: POSITIVE
✓ All trending UP
✓ % changes > 5%
→ STRONG MOMENTUM, BUY SIGNAL

Bearish Divergence When:
✓ Fast OBV: NEGATIVE
✓ Medium OBV: POSITIVE
✓ Slow OBV: POSITIVE
✓ Fast declining, others stable
→ POTENTIAL REVERSAL, CAUTION

Reversal Warning When:
✓ Fast OBV transition (sign change)
✓ Medium OBV changing direction
✓ Previous aligned, now misaligned
→ TREND CHANGING, WATCH CLOSELY
```

### Common Setups to Trade

#### Setup 1: Aligned Breakout
```
Entry: Strong Bullish signal appears
Stop: 1% below recent support
Target: 2-3% above entry
Risk:Reward: 1:2
```

#### Setup 2: Divergence Bounce
```
Entry: Fast + Medium bullish, Slow bearish
Stop: Below Fast OBV low
Target: Back to Medium OBV level
Risk:Reward: 1:1.5
```

#### Setup 3: Trend Ride
```
Entry: Slow OBV becomes positive
Stop: When Slow OBV becomes negative
Target: Ride the trend
Risk:Reward: Variable
```

### Threshold Selection Guide

| Style | Threshold | Audio | TTS |
|-------|-----------|-------|-----|
| **Scalpers** | 1-2% | ✓ | ✗ |
| **Day Traders** | 3-5% | ✓ | ✓ |
| **Swing Traders** | 5-10% | ✓ | ✓ |
| **Position Traders** | 10-20% | ✓ | ✓ |

### Troubleshooting Checklist

| Problem | Check | Fix |
|---------|-------|-----|
| No analysis | ☑ Enabled? | Enable feature |
| No analysis | ☑ Indicators enabled? | Enable Fast/Medium/Slow OBV |
| Too many alerts | ↑ Threshold | Increase to 10% |
| Too few alerts | ↓ Threshold | Decrease to 2% |
| No audio | Muted? | Unmute browser |
| Bad signals | Wrong setup? | Review signal types |

### Data Fields Available

```python
# Signal
data.multiOBVSignal              # "strong_bullish", "bullish", etc.

# Values  
data.fastOBVValue               # Fast OBV number
data.mediumOBVValue             # Medium OBV number
data.slowOBVValue               # Slow OBV number

# Changes
data.fastMediumPctChange        # % F→M
data.mediumSlowPctChange        # % M→S
data.fastSlowPctChange          # % F→S

# Display
data.multiOBVEquation           # "Fast OBV: 5000↑ | ..."

# Alert
data.obvTTSAlert.description    # "Very strong bullish..."
```

### Key Concepts Summary

| Concept | Definition | Why Matters |
|---------|-----------|------------|
| **Alignment** | All OBVs same direction | Confirms trend strength |
| **Divergence** | OBVs opposite directions | Signals potential reversal |
| **Transition** | Sign change in OBV | Early warning of shift |
| **Strength** | Magnitude of changes | Confidence in signal |
| **% Change** | Relative differences | Momentum comparison |

### Red Flags 🚩

| Flag | Means | Action |
|------|-------|--------|
| F→M: -50% | Strong divergence | REDUCE position |
| Medium transition | Mid-term reversal | TIGHTEN stop |
| All three negative | Downtrend active | NO new longs |
| Misaligned signal | Unclear direction | WAIT for clarity |

### Green Lights 🟢

| Light | Means | Action |
|-------|-------|--------|
| F→M: +10% | Strong momentum | INCREASE position |
| Slow transition (bearish→bullish) | Long-term reversal | NEW long signal |
| All three positive + rising | Perfect alignment | AGGRESSIVE entry |
| Strong → Strong Bullish | Signal strengthening | ADD to position |

### Pro Tips

1. **Wait for alignment**: Don't trade misaligned signals
2. **Use Slow OBV as anchor**: If Slow negative, expect pullback in any bounce
3. **Watch transitions**: Early sign of trend change before other indicators
4. **Combine with price**: Best signals when price supports OBV direction
5. **Use higher threshold**: Fewer alerts = higher quality signals
6. **Scale in**: Use Strong Bullish for large position, Bullish for half size

### Common Mistakes to Avoid

❌ Trading misaligned signals (wait for clarity)  
❌ Ignoring divergence warnings (early reversal sign)  
❌ Using too low threshold (too many false alerts)  
❌ Fighting the Slow OBV trend (strong trend foundation)  
❌ Entering without stop loss (always have risk management)  
❌ Ignoring transitions (sign of change coming)

### Related Documentation

| Need | Read | Location |
|------|------|----------|
| Step-by-step | MULTI_OBV_QUICK_START.md | Root folder |
| Technical details | OBV_ANALYSIS_ENHANCEMENTS.md | Root folder |
| Code architecture | ARCHITECTURE_IMPLEMENTATION.md | Root folder |
| Full summary | IMPLEMENTATION_SUMMARY.md | Root folder |

### Quick Test

Can you answer these?
1. When should you buy? ➜ Strong Bullish signal
2. When should you exit? ➜ When Slow/Medium OBV transitions
3. What does F→M +5% mean? ➜ Fast is 5% higher than Medium
4. What's divergence? ➜ OBVs moving in opposite directions
5. When to wait? ➜ When signal is Neutral/misaligned

---

**Version**: 1.0 Quick Reference  
**Size**: ~2 pages when printed  
**Use**: Print and post on wall or save to phone  
**Last Updated**: May 4, 2026
