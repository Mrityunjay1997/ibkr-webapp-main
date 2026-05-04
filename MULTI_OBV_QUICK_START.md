# Quick Start: Multi-OBV Analysis

## What is Multi-OBV Analysis?

Multi-OBV Analysis compares three On-Balance Volume (OBV) indicators with different sensitivities:
- **Fast OBV** (5-bar): Quick response to volume changes
- **Medium OBV** (10-bar): Balanced medium-term view
- **Slow OBV** (20-bar): Long-term trend confirmation

When all three are **aligned** and moving in the same direction, it creates **strong signals**.

---

## How to Enable Multi-OBV Analysis

### Step 1: Configure Form Settings
In your scan configuration form, find the **OBV Analysis** section:

1. ✅ Enable **"Enable Multi-OBV Analysis"** checkbox
2. Set **"Multi-OBV Change Threshold (%)"** - Default: 5.0%
   - Lower = More sensitive (more alerts)
   - Higher = Less sensitive (fewer alerts)
3. ✅ Check **"Enable Multi-OBV Audio Alerts"** (optional - plays sound)
4. ✅ Check **"Enable Multi-OBV Text-to-Speech"** (optional - reads alert)

### Step 2: Configure Individual OBV Indicators
Make sure the three OBV indicators are enabled:

1. In the **OBV Indicators** section:
   - **FastOBV**: Set comparison operator (e.g., ">", "between")
   - **MediumOBV**: Set comparison operator
   - **SlowOBV**: Set comparison operator

2. Set window periods (optional - defaults are good):
   - **OBV Trend Period**: 20 bars (how far back to look for trend)
   - **OBV Moving Average Period**: 10 bars

---

## Understanding the Results

### Signal Types

#### 🟢 **Strong Bullish** - BEST BUY SIGNAL
- All three OBVs are **positive and rising**
- Fast OBV just transitioned from bearish to bullish
- All changes exceed threshold
- **Action**: Consider LONG trades

#### 🟢 **Bullish** - BUY SIGNAL
- All three OBVs are **positive**
- Growing steadily
- **Action**: Monitor for entry on pullback

#### 🟡 **Neutral** - WAIT FOR CLARITY
- OBVs showing **mixed signals**
- Some positive, some negative
- Conflicting directions
- **Action**: Wait for stronger signal

#### 🔴 **Bearish** - SELL SIGNAL
- All three OBVs are **negative**
- Declining together
- **Action**: Consider SHORT trades or exit longs

#### 🔴 **Strong Bearish** - BEST SELL SIGNAL
- All three OBVs are **negative and declining**
- Fast OBV just transitioned from bullish to bearish
- All changes exceed threshold
- **Action**: Exit longs, consider shorts

---

## The OBV Equation (What You'll See)

Example output:
```
Fast OBV: 5000↑ | Medium OBV: 3000↑ | Slow OBV: 1500↑ | 
% Changes: F→M +5.2% | M→S +2.1% | F→S +8.1%
```

**Decode this:**
- `5000↑` = Fast OBV is 5000 and rising (↑ = positive, ↓ = negative)
- `F→M +5.2%` = Fast OBV is 5.2% higher than Medium OBV
- `M→S +2.1%` = Medium OBV is 2.1% higher than Slow OBV
- `F→S +8.1%` = Fast OBV is 8.1% higher than Slow OBV

**Good sign**: F > M > S all with same direction = Momentum
**Warning sign**: F > M but M < S = Divergence/Reversal risk

---

## Percentage Changes Explained

### Fast → Medium (F→M)
- **Positive %**: Fast OBV is higher (short-term stronger)
- **Negative %**: Fast OBV is lower (medium-term stronger)

### Medium → Slow (M→S)
- **Positive %**: Medium OBV is higher (mid-term stronger)
- **Negative %**: Medium OBV is lower (long-term stronger)

### Fast → Slow (F→S)
- **Positive %**: Fast OBV is higher than Slow (short-term outpacing long-term)
- **Negative %**: Slow OBV is higher (long-term momentum stronger)

**Key**: When all % changes are positive and large (>5%), you have **aligned bullish momentum**.

---

## Practical Trading Examples

### Example 1: Strong Bullish Setup ✅
```
Fast OBV: +5000↑
Medium OBV: +3000↑
Slow OBV: +1500↑
% Changes: F→M +5.2% | M→S +2.1% | F→S +8.1%

Signal: STRONG BULLISH
Interpretation: All three indicators positive, all rising, 
short-term leading long-term. Perfect alignment.
Trade: BUY or add to longs
Stop: Below recent support
```

### Example 2: Bullish Divergence ⚠️
```
Fast OBV: +5000↑
Medium OBV: +3000↑
Slow OBV: -1500↓
% Changes: F→M +5.2% | M→S -68.1% | F→S +106.8%

Signal: NEUTRAL (Misaligned)
Interpretation: Short-term bullish but long-term bearish.
Potential reversal coming.
Trade: WAIT for resolution, watch closely
Action: Set alerts for transition signals
```

### Example 3: Strong Bearish Setup ✅
```
Fast OBV: -5000↓
Medium OBV: -3000↓
Slow OBV: -1500↓
% Changes: F→M -5.2% | M→S -2.1% | F→S -8.1%

Signal: STRONG BEARISH
Interpretation: All three indicators negative, all declining,
short-term leading long-term in bearish direction.
Trade: SHORT or exit existing longs
Stop: Above recent resistance
```

### Example 4: Transition (Signal Change Coming) 🔔
```
Previous:
Fast OBV: +2000↑
Medium OBV: +3000↑
Slow OBV: +1500↑

Current:
Fast OBV: -1000↓  ← CHANGED FROM POSITIVE!
Medium OBV: +3000↑
Slow OBV: +1500↑
Transitions: Fast=TRUE (bullish→bearish)

Signal: NEUTRAL
Interpretation: Fast OBV just flipped from positive to negative.
This is early warning of potential trend reversal.
Trade: REDUCE exposure, tighten stops
Alert: Watch for Medium OBV to transition next
```

---

## Audio & TTS Alerts

### When Enabled
The system will play audio signals and/or read aloud:

**Bullish Sound**: 🎵 Triumphant arpeggio (C-E-G-C ascending)
**Bearish Sound**: 🎵 Descending notes (C-G-E-C descending)
**Message**: "Apple. Strong bullish O B V signal detected. All indicators positive with significant upward momentum."

### Configuration Tips
- **Aggressive**: Threshold 2-3% (more alerts, more noise)
- **Balanced**: Threshold 5% (recommended, good signal quality)
- **Conservative**: Threshold 10% (fewer alerts, only high-confidence signals)

---

## Recommended Settings by Trading Style

### Day Traders (High Sensitivity)
```
Change Threshold: 2.0%
Trend Period: 20 bars
MA Period: 5 bars (faster response)
Audio Alerts: ON
TTS: OFF (too many alerts)
```

### Swing Traders (Balanced)
```
Change Threshold: 5.0%  ← RECOMMENDED
Trend Period: 20 bars
MA Period: 10 bars
Audio Alerts: ON
TTS: ON
```

### Position Traders (Low Sensitivity)
```
Change Threshold: 10.0%
Trend Period: 50 bars
MA Period: 20 bars
Audio Alerts: ON
TTS: ON
```

---

## Troubleshooting

### "I'm not seeing any Multi-OBV Analysis"
1. ✅ Check "Enable Multi-OBV Analysis" is checked
2. ✅ Check at least one OBV indicator is enabled (FastOBV, MediumOBV, or SlowOBV)
3. ✅ Check stock has enough historical data (minimum 20 bars)
4. Run scan again - give it 30 seconds to process

### "I'm getting too many alerts"
1. Increase "Multi-OBV Change Threshold" (e.g., from 5% to 10%)
2. Disable "Enable Multi-OBV Audio Alerts" to reduce noise
3. Disable "Enable Multi-OBV Text-to-Speech"

### "I'm not getting any alerts"
1. Decrease "Multi-OBV Change Threshold" (e.g., from 10% to 5%)
2. Make sure "Enable Multi-OBV TTS" is checked
3. Check browser audio is not muted
4. Check browser allows audio playback

### "The equation looks wrong"
- Check stock symbol is correct
- Verify Fast OBV is always smallest, Slow OBV largest (expected in trending market)
- If all zeros, insufficient volume data for stock

---

## Data Fields Available (For Technical Users)

If you want to display custom Multi-OBV results:

```javascript
data.multiOBVSignal           // "strong_bullish", "bullish", "neutral", etc.
data.multiOBVAlignment        // "aligned_bullish", "aligned_bearish", "misaligned"
data.multiOBVStrength         // "very_strong", "strong", "moderate", "weak"
data.multiOBVDivergence       // true/false
data.multiOBVEquation         // Full equation string for display

data.fastOBVValue             // Fast OBV numeric value
data.mediumOBVValue           // Medium OBV numeric value
data.slowOBVValue             // Slow OBV numeric value

data.fastMediumPctChange      // % change F→M
data.mediumSlowPctChange      // % change M→S
data.fastSlowPctChange        // % change F→S

data.obvTTSAlert              // { symbol, signal, description, equation }
```

---

## FAQ

**Q: Can I use Multi-OBV Analysis without the audio alerts?**
A: Yes! Just uncheck "Enable Multi-OBV Audio Alerts" and "Enable Multi-OBV Text-to-Speech". The data will still be calculated and displayed.

**Q: Which OBV (Fast/Medium/Slow) matters most?**
A: When **all three agree** and move together, that's the strongest signal. Fast responds quickest, Slow confirms the longest trend.

**Q: What if only Fast OBV is bullish but Medium and Slow are bearish?**
A: That's a "Neutral" signal with "Misaligned" indicators. This suggests a bounce against the longer-term bearish trend. Risk of reversal - wait for clearer signal.

**Q: How do I know when to take profits?**
A: When Fast or Medium OBV transitions from positive to negative (their "Transition" flag goes True), that's often a good time to take partial profits.

**Q: Can I filter results to only show Strong Bullish/Bearish signals?**
A: Yes! In the filter section, enable filtering on "multiOBVAlignment" to only show aligned signals.

**Q: What's the difference between OBV Analysis and Multi-OBV Analysis?**
A: OBV Analysis looks at a single OBV with moving average comparison. Multi-OBV Analysis compares three OBVs against each other for stronger confirmation signals.

---

**For detailed technical information, see: OBV_ANALYSIS_ENHANCEMENTS.md**
