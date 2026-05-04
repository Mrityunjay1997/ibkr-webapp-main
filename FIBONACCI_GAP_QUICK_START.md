# Fibonacci Gap Pullback - Quick Start Guide

## Installation & Setup (5 minutes)

### 1. Initialize Engine
```python
from gap_playbook_engine import GapPlaybookEngine, save_default_playbooks

engine = GapPlaybookEngine(playbooks_dir='./setups')
save_default_playbooks(engine)
```

### 2. Load Your Stock Data
```python
price_data = {
    'prev_close': 100.0,
    'today_high': 110.0,
    'today_low': 99.5,
    'current_price': 106.5
}

# Get 20 days of daily candles
recent_daily_data = [
    {'date': '2024-01-01', 'open': 98, 'high': 104, 'low': 97, 'close': 103},
    # ... more candles
]
```

### 3. Run Analysis
```python
# Run single playbook
result = engine.run_playbook(
    'Conservative Long',
    'AAPL',
    price_data,
    recent_daily_data
)

# Or run all playbooks
results = engine.run_all_playbooks(
    'AAPL',
    price_data,
    recent_daily_data
)
```

## Understanding the Output

### Successful Signal
```python
if result.status == 'success':
    signal = result.signal
    print(f"ENTRY: ${signal.entry_price}")
    print(f"STOP: ${signal.stop_loss}")
    print(f"TARGET: ${signal.target_price}")
    print(f"Ratio: {signal.risk_reward_ratio}:1")
    print(f"Fib Level: {signal.fib_level_percent}%")
    print(f"Confidence: {signal.confidence_score}%")
```

### No Setup
```python
if result.status in ['no_gap', 'no_setup']:
    print(f"Reason: {result.error_message}")
```

## Playbook Quick Reference

| Playbook | Direction | Levels | R:R | Gap % | Confidence |
|----------|-----------|--------|-----|-------|------------|
| **Conservative Long** | Long | 50,61,78 | 2.0 | 1.5-8 | 75 |
| **Aggressive Long** | Long | 24,38 | 1.5 | 1.0-12 | 60 |
| **Mid-Range Long** | Long | 38,50,62 | 1.8 | 1.2-10 | 70 |
| **Conservative Short** | Short | 50,61,78 | 2.0 | 1.5-8 | 75 |
| **Quick Scalp** | Long | 24,38 | 1.2 | 1.0-3 | 65 |

## Creating Custom Playbooks

```python
from gap_playbook_engine import PlaybookConfig

my_playbook = PlaybookConfig(
    name='My Strategy',
    description='My custom gap strategy',
    trade_direction='long',
    preferred_levels=[0.382, 0.5, 0.618],
    min_reward_risk_ratio=1.8,
    min_gap_pct=1.5,
    max_gap_pct=8.0,
    minimum_confidence_score=72.0
)

engine.create_playbook(my_playbook)
engine.save_playbook('My Strategy')
```

## Confidence Score Breakdown

Each level gets scored 0-100 based on:
- **Price Proximity** (20 pts): How close to current price
- **Level Quality** (20 pts): Natural Fib levels preferred
- **Technical Context** (20 pts): Support from recent highs/lows
- **Zone Quality** (20 pts): Good position in support/resistance
- **Entry Safety** (20 pts): Not too close to extremes

**Score 85+**: Excellent (High confidence)
**Score 70-85**: Good (Viable)
**Score 55-70**: Fair (Consider alternatives)
**Score <55**: Poor (Avoid)

## Example Trades

### Setup 1: Gap Up to 38.2% Pullback
```
Prev Close: 100
Gap High:   110
Current:    106.5

38.2% Entry: 106.18
Recent High: 112 (good context)
Score: 82 (Good)

Recommendation: BUY at 106.18
  Stop: 104.18 (2% risk)
  Target: 109.18 (3% reward)
  Ratio: 1.5:1
```

### Setup 2: Gap Down to 61.8% Pullback
```
Prev Close: 100
Gap Low:    90
Current:    93.5

61.8% Entry: 93.82
Recent Low: 88 (good support context)
Score: 75 (Good)

Recommendation: SHORT at 93.82
  Stop: 95.82 (2% risk)
  Target: 91.82 (2% reward)
  Ratio: 1.0:1
```

## Integration with Existing Code

### In your scanner loop:
```python
for symbol in symbols_to_scan:
    price_data = get_current_price_data(symbol)
    daily_data = get_daily_candles(symbol, 20)
    
    results = engine.run_all_playbooks(
        symbol,
        price_data,
        daily_data
    )
    
    for result in results:
        if result.status == 'success' and result.signal.confidence_score >= 70:
            print(f"SIGNAL: {symbol} - {result.signal.entry_price}")
            # Place trade or add to watchlist
```

### In your order placement system:
```python
if result.status == 'success':
    signal = result.signal
    
    order = {
        'symbol': signal.symbol,
        'action': 'BUY' if signal.direction == 'long' else 'SELL',
        'quantity': calculate_shares(signal.risk_reward_ratio),
        'entry': signal.entry_price,
        'stop': signal.stop_loss,
        'target': signal.target_price,
        'strategy': signal.playbook_name,
    }
    execute_order(order)
```

## Common Parameters to Adjust

### For More Conservative Trades:
```python
config.min_reward_risk_ratio = 2.0  # Higher R:R requirement
config.minimum_confidence_score = 75  # Higher confidence needed
config.max_risk_per_trade_pct = 1.5  # Tighter stops
config.preferred_levels = [0.5, 0.618, 0.786]  # Deeper retracements
```

### For More Aggressive Trades:
```python
config.min_reward_risk_ratio = 1.2  # Lower R:R acceptable
config.minimum_confidence_score = 60  # Lower confidence needed
config.max_risk_per_trade_pct = 2.5  # Wider stops
config.preferred_levels = [0.236, 0.382]  # Shallower retracements
```

### For Small Gaps/Scalping:
```python
config.min_gap_pct = 0.5
config.max_gap_pct = 2.0
config.stop_loss_pct = 0.5
config.target_profit_pct = 1.0
```

### For Large Gaps/Swing Trades:
```python
config.min_gap_pct = 3.0
config.max_gap_pct = 15.0
config.stop_loss_pct = 3.0
config.target_profit_pct = 4.0
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No signals generated | Check gap size, confidence threshold, and recent data |
| Low confidence scores | Increase lookback days, verify price accuracy |
| Wrong entries | Verify trade_direction matches your intention |
| Poor risk/reward | Adjust stop_loss_pct and target_profit_pct |

## Performance Tips

1. **Cache playbooks**: Load once, reuse multiple times
2. **Batch processing**: Run all playbooks at once vs individual calls
3. **Limit lookback**: 20 days is standard; reduce for faster processing
4. **Filter early**: Check gap before running full analysis

```python
# Good: Filter gaps before analysis
if abs(price_data['today_high'] - price_data['prev_close']) < min_gap:
    continue

# Then run playbooks
results = engine.run_all_playbooks(...)
```

## Next Steps

1. ✅ Run on your watchlist symbols
2. ✅ Create custom playbooks for your style
3. ✅ Track results and adjust parameters
4. ✅ Integrate with your order system
5. ⏳ Wait for Phase 2 (whole numbers, natural Fibs, moving averages)

---

**Need Help?** See FIBONACCI_GAP_PULLBACK_GUIDE.md for detailed documentation.
