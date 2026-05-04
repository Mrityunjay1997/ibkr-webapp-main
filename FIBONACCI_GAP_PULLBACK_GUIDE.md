# Fibonacci Gap Pullback Analysis - Implementation Guide

## Overview

This document describes the Phase 1 implementation of the Fibonacci Gap Pullback analysis system with intelligent level selection, recent peak/valley context, and risk/reward evaluation.

## Architecture

### 1. Enhanced FibonacciCalculator (`indicators.py`)

**What it does:**
- Calculates Fibonacci retracement levels from gap moves
- Now includes 100% retracement level
- Supports levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
- Calculates entry prices, pullback amounts, and position percentages

**Example Usage:**

```python
from indicators import FibonacciCalculator

# Setup: Stock gapped from 100 (prev close) to 110 (today high)
fib = FibonacciCalculator(prev_close=100, high_of_day=110)

# Get all Fib levels
levels = fib.calculate_levels()
# Returns:
# {
#   '0.236': {'entry': 107.64, 'pullback': 2.36, ...},
#   '0.382': {'entry': 106.18, 'pullback': 3.82, ...},
#   '0.500': {'entry': 105.00, 'pullback': 5.00, ...},
#   ...
#   '1.000': {'entry': 100.00, 'pullback': 10.00, ...}
# }

# Get order prices for specific level with risk/reward
order = fib.calculate_order_prices(
    level=0.382,  # 38.2% retracement
    entry_offset_pct=0,  # No offset from calculated level
    stop_loss_pct=2.0,   # Stop 2% of gap move below entry
    target_profit_pct=3.0 # Target 3% of gap move above entry
)
# Returns entry, stop_loss, target, risk_reward_ratio, etc.
```

### 2. RiskRewardEvaluator (`indicators.py`)

**What it does:**
- Scores Fibonacci levels based on multiple criteria (0-100 score)
- Evaluates proximity to current price
- Considers technical context (recent highs/lows)
- Ranks levels by quality
- Provides trading recommendations

**Scoring Factors:**
- **Price Proximity (0-20 pts)**: How close entry is to current price
- **Level Quality (0-20 pts)**: Prefers mid-range levels (38.2%-61.8%)
- **Technical Context (0-20 pts)**: Recent high/low support
- **Zone Quality (0-20 pts)**: Position in support/resistance zone
- **Entry Safety (0-20 pts)**: Distance from extremes

**Example Usage:**

```python
from indicators import RiskRewardEvaluator

evaluator = RiskRewardEvaluator()

# Score a single level
fib_levels = fib.calculate_levels()
scored = evaluator.score_level(
    fib_level=fib_levels['0.382'],
    current_price=106.5,
    recent_high=112,
    recent_low=98
)
# Returns: score 0-100, breakdown, recommendation

# Rank all levels
ranked = evaluator.rank_levels(
    fib_levels=fib_levels,
    current_price=106.5,
    recent_high=112,
    recent_low=98
)
# Returns sorted list by quality score (best first)
```

### 3. FibonacciGapPullbackAnalyzer (`indicators.py`)

**What it does:**
- Complete gap pullback analysis pipeline
- Incorporates recent peak/valley context
- Handles both LONG and SHORT trades
- Returns comprehensive analysis with recommendations

**Key Features:**
- Detects gaps (up/down)
- Finds recent peaks/valleys from configurable lookback period
- Calculates all Fib levels
- Scores and ranks levels
- Selects best setup automatically

**Example Usage:**

```python
from indicators import FibonacciGapPullbackAnalyzer

analyzer = FibonacciGapPullbackAnalyzer(lookback_days=20)

# Prepare data
price_data = {
    'prev_close': 100.0,
    'today_high': 110.0,
    'today_low': 99.5,
    'current_price': 106.5
}

recent_daily_data = [
    {'date': '2024-01-01', 'open': 98, 'high': 104, 'low': 97, 'close': 103},
    {'date': '2024-01-02', 'open': 103, 'high': 108, 'low': 102, 'close': 107},
    # ... 20 days of data
]

# Run analysis for LONG trades
result = analyzer.analyze_gap_pullback(
    prev_close=100.0,
    today_high=110.0,
    today_low=99.5,
    current_price=106.5,
    recent_daily_data=recent_daily_data,
    trade_direction='long'
)

# Access results
print(result['gap_analysis'])          # Basic gap info
print(result['recent_context'])        # Recent peaks/valleys
print(result['ranked_levels'])         # All levels ranked by quality
print(result['recommended_setup'])     # Best trade setup
```

### 4. GapPlaybookEngine (`gap_playbook_engine.py`)

**What it does:**
- Manages multiple trading playbooks
- Each playbook defines strategy rules and preferences
- Generates trading signals from playbooks
- Saves/loads playbook configurations
- Runs multiple playbooks simultaneously

**Playbook Configuration Includes:**
- Trade direction (LONG/SHORT)
- Preferred Fibonacci levels
- Risk/reward requirements
- Gap size filters
- Entry/exit parameters
- Confidence thresholds
- Associated technical indicators

**Example Usage:**

```python
from gap_playbook_engine import GapPlaybookEngine, PlaybookConfig, save_default_playbooks

# Initialize engine
engine = GapPlaybookEngine(playbooks_dir='./setups')

# Option A: Use default playbooks
save_default_playbooks(engine)

# Option B: Create custom playbook
custom_pb = PlaybookConfig(
    name='My Long Strategy',
    description='Conservative long with 50%+ retracements',
    trade_direction='long',
    preferred_levels=[0.5, 0.618, 0.786],
    min_reward_risk_ratio=2.0,
    min_gap_pct=1.5,
    max_gap_pct=8.0,
    minimum_confidence_score=75.0
)
engine.create_playbook(custom_pb)
engine.save_playbook('My Long Strategy')

# Run playbook on symbol
price_data = {
    'prev_close': 100.0,
    'today_high': 110.0,
    'today_low': 99.5,
    'current_price': 106.5
}

result = engine.run_playbook(
    playbook_name='Conservative Long',
    symbol='AAPL',
    price_data=price_data,
    recent_daily_data=recent_daily_data
)

if result.status == 'success':
    print(f"Entry: ${result.signal.entry_price}")
    print(f"Stop: ${result.signal.stop_loss}")
    print(f"Target: ${result.signal.target_price}")
    print(f"R:R Ratio: {result.signal.risk_reward_ratio}:1")

# Run all enabled playbooks on a symbol
all_results = engine.run_all_playbooks(
    symbol='AAPL',
    price_data=price_data,
    recent_daily_data=recent_daily_data,
    enabled_only=True
)

# Process results
for result in all_results:
    if result.status == 'success':
        print(f"{result.playbook_name}: {result.signal.entry_price}")
```

## Pre-built Playbooks

The engine comes with 5 default playbooks:

### 1. Conservative Long
- **Purpose**: Risk-averse long trades
- **Levels**: 50%, 61.8%, 78.6%
- **R:R Ratio**: Minimum 2.0:1
- **Gap Range**: 1.5% - 8.0%
- **Confidence**: 75%+ required
- **Best for**: Swing trades with strong setups

### 2. Aggressive Long
- **Purpose**: Early entry, higher risk
- **Levels**: 23.6%, 38.2%
- **R:R Ratio**: Minimum 1.5:1
- **Gap Range**: 1.0% - 12.0%
- **Confidence**: 60%+ required
- **Best for**: Fast-moving gappers

### 3. Mid-Range Long
- **Purpose**: Balanced approach
- **Levels**: 38.2%, 50%, 61.8%
- **R:R Ratio**: Minimum 1.8:1
- **Gap Range**: 1.2% - 10.0%
- **Confidence**: 70%+ required
- **Best for**: Most market conditions

### 4. Conservative Short
- **Purpose**: Risk-averse short trades
- **Levels**: 50%, 61.8%, 78.6%
- **R:R Ratio**: Minimum 2.0:1
- **Gap Range**: 1.5% - 8.0%
- **Confidence**: 75%+ required
- **Best for**: Gap down pullback shorts

### 5. Quick Scalp
- **Purpose**: Rapid scalping on small gaps
- **Levels**: 23.6%, 38.2%
- **R:R Ratio**: Minimum 1.2:1
- **Gap Range**: 1.0% - 3.0%
- **Confidence**: 65%+ required
- **Stop/Target**: Tighter exits (1.0% / 1.5%)
- **Best for**: Day traders, high frequency

## Data Requirements

### For Basic Gap Pullback Analysis:

```python
price_data = {
    'prev_close': float,      # Previous day's close
    'today_high': float,      # Today's high of day
    'today_low': float,       # Today's low of day
    'current_price': float    # Current intraday price
}
```

### For Recent Peak/Valley Context:

```python
recent_daily_data = [
    {
        'date': '2024-01-01',  # Date string
        'open': float,
        'high': float,
        'low': float,
        'close': float
    },
    # ... 20+ days of historical data
]
```

## Output Examples

### Recommended Setup Output:

```python
{
    'recommended_level': 38.2,
    'entry_price': 106.18,
    'confidence_score': 78.5,
    'recommendation': 'Good - Viable entry point',
    'gap_size': 10.0,
    'gap_pct': 10.0,
    'distance_from_current': 0.32,
    'recent_peak_context': 112.0,
    'recent_valley_context': 98.5
}
```

### Ranked Levels Output:

```python
[
    {
        'level': 0.382,
        'level_percent': 38.2,
        'entry': 106.18,
        'current_price': 106.5,
        'distance_pct': 0.30,
        'total_score': 78.5,
        'recommendation': 'Good - Viable entry point',
        'scores': {
            'price_proximity': 20,
            'level_quality': 20,
            'technical_context': 18,
            'zone_quality': 15,
            'entry_safety': 20
        }
    },
    # ... more levels ranked by score
]
```

## Integration with Forms

The new form fields in `forms.py` allow UI configuration:

```python
# New fields available:
FibGapLookbackDays        # Configurable recent peak/valley lookback
FibGapMinGapPct           # Minimum gap % filter
FibGapMaxGapPct           # Maximum gap % filter
FibGapMinRewardRiskRatio  # Minimum R:R requirement
FibGapMinConfidence       # Minimum confidence score
FibGapPreferredLevels     # Multi-select preferred Fib levels
FibGapEntryOffset         # Entry offset from calculated level
FibGapStopLossPct         # Stop loss as % of gap
FibGapTargetProfitPct     # Target profit as % of gap
FibGapDirection           # long/short/both
FibGapUseRecentContext    # Boolean toggle for context usage
FibGap_tf                 # Timeframe selection
```

## Phase 2 Future Enhancements

### Coming Soon:
- **Whole Numbers**: Round price levels (101.00, 102.00, etc.)
- **Natural Fibonacci Sequence**: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, etc.
- **Stock % Move**: Daily percentage move as trading level
- **Multiple Moving Averages**: SMA/EMA at different timeframes
- **Flexible Indicator System**: Easy add/remove of technical indicators
- **Multi-timeframe Analysis**: Run same playbook across different timeframes
- **Advanced Risk Management**: ATR-based stops, trailing stops, volatility adjustment
- **Pattern Recognition**: Gap consolidation patterns, reversal signals
- **Machine Learning**: Predictive confidence scoring

### Architecture for Phase 2:
- `indicator_framework.py`: Flexible indicator registration system
- `multi_timeframe_analyzer.py`: Simultaneous analysis across timeframes
- `pattern_analyzer.py`: Gap pattern detection
- `ml_confidence_scorer.py`: ML-based confidence prediction

## Testing

### Example Test Script:

```python
from indicators import FibonacciGapPullbackAnalyzer
from gap_playbook_engine import GapPlaybookEngine, save_default_playbooks

# Create test data
test_price_data = {
    'prev_close': 100.0,
    'today_high': 110.0,
    'today_low': 99.5,
    'current_price': 106.5
}

# Create recent daily data (sample)
import pandas as pd
dates = pd.date_range('2024-01-01', periods=20)
test_daily_data = [
    {
        'date': str(d.date()),
        'open': 100 + i,
        'high': 105 + i,
        'low': 95 + i,
        'close': 102 + i
    }
    for i, d in enumerate(dates)
]

# Test analyzer
analyzer = FibonacciGapPullbackAnalyzer(lookback_days=20)
analysis = analyzer.analyze_gap_pullback(
    prev_close=100.0,
    today_high=110.0,
    today_low=99.5,
    current_price=106.5,
    recent_daily_data=test_daily_data,
    trade_direction='long'
)

print("Gap Analysis:", analysis['gap_analysis'])
print("Recent Context:", analysis['recent_context'])
print("Top Levels:", analysis['ranked_levels'][:3])
print("Recommended:", analysis['recommended_setup'])

# Test playbooks
engine = GapPlaybookEngine()
save_default_playbooks(engine)

results = engine.run_all_playbooks(
    symbol='TEST',
    price_data=test_price_data,
    recent_daily_data=test_daily_data,
    enabled_only=True
)

for result in results:
    print(f"{result.playbook_name}: {result.status}")
    if result.signal:
        print(f"  Entry: ${result.signal.entry_price}, Target: ${result.signal.target_price}")
```

## Troubleshooting

### No Setup Found
- Check gap size is within playbook's min/max range
- Verify confidence score threshold isn't too high
- Ensure recent daily data is sufficient (at least 5 bars)

### Low Confidence Scores
- Increase lookback period for better context
- Ensure price data is accurate
- Check recent peak/valley availability

### Missing Levels
- Verify Fib levels aren't filtered too aggressively
- Check level range settings (min_level, max_level)
- Ensure gap is large enough (minimum 1%)

## Summary

This Phase 1 implementation provides:

✅ Enhanced Fibonacci calculations with 100% level
✅ Intelligent level scoring based on risk/reward
✅ Recent peak/valley context integration
✅ Comprehensive gap pullback analysis
✅ Multi-playbook framework with pre-built strategies
✅ Flexible configuration for custom strategies
✅ Ready for Phase 2 enhancements

The system is production-ready and can be integrated with your scanning/trading engine immediately.
