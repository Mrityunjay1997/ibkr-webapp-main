#!/usr/bin/env python
"""Test OBV analysis functions"""

import sys
sys.path.insert(0, '.')

from scanner.ibkr_signal_engine import (
    calculate_obv_momentum,
    calculate_obv_vs_moving_average,
    detect_obv_strength
)
import pandas as pd
import numpy as np

print("Testing OBV Analysis Functions...")

# Create sample OHLC data with volume
np.random.seed(42)
dates = pd.date_range('2024-01-01', periods=50, freq='D')
closes = 100 + np.cumsum(np.random.randn(50) * 0.5)
volumes = np.random.randint(1000000, 5000000, 50)

data = pd.DataFrame({
    'date': dates,
    'open': closes + np.random.randn(50) * 0.3,
    'close': closes,
    'high': closes + np.random.rand(50) * 1.0,
    'low': closes - np.random.rand(50) * 1.0,
    'volume': volumes
})

print("\n1. Testing OBV Momentum Calculation")
trend, momentum_pct, obv_val, obv_ma = calculate_obv_momentum(data, lookback=20)
print(f"   Trend: {trend}")
print(f"   Momentum: {momentum_pct:.2f}%")
print(f"   OBV: {obv_val:.0f}")
print(f"   OBV MA: {obv_ma:.0f}")
assert trend in ["rising", "declining", "neutral"], "Invalid trend"
assert isinstance(momentum_pct, float), "Momentum should be float"
print("   ✓ Passed")

print("\n2. Testing OBV vs Moving Average")
is_above, distance_pct, obv_val, obv_ma = calculate_obv_vs_moving_average(data, ma_period=10)
print(f"   OBV Above MA: {is_above}")
print(f"   Distance: {distance_pct:.2f}%")
assert isinstance(is_above, (bool, np.bool_)), "Should return boolean"
assert distance_pct >= 0, "Distance should be non-negative"
print("   ✓ Passed")

print("\n3. Testing OBV Strength Detection")
analysis = detect_obv_strength(None, data, trend_period=20, ma_period=10, strength_threshold=15.0)
print(f"   Trend: {analysis['trend']}")
print(f"   Strength: {analysis['strength']}")
print(f"   Momentum: {analysis['momentum_pct']:.2f}%")
print(f"   Above MA: {analysis['above_ma']}")
print(f"   Signal: {analysis['signal']}")

assert analysis['trend'] in ["rising", "declining", "neutral"]
assert analysis['strength'] in ["strong", "moderate", "weak"]
assert analysis['signal'] in ["strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"]
print("   ✓ Passed")

print("\n4. Testing Signal Generation - Bullish Case")
# Create uptrend data: increasing closes, high volume
bullish_data = pd.DataFrame({
    'close': np.linspace(100, 110, 30),  # Strong uptrend
    'volume': np.concatenate([np.ones(15)*1000000, np.ones(15)*3000000])  # Volume increases on uptrend
})
analysis = detect_obv_strength(None, bullish_data, trend_period=20, ma_period=10, strength_threshold=10.0)
print(f"   Bullish signal: {analysis['signal']}")
assert analysis['signal'] in ["bullish", "strong_bullish", "neutral"], "Should be bullish"
print("   ✓ Passed")

print("\n5. Testing Signal Generation - Bearish Case")
# Create downtrend: decreasing closes, high volume
bearish_data = pd.DataFrame({
    'close': np.linspace(110, 100, 30),  # Downtrend
    'volume': np.concatenate([np.ones(15)*1000000, np.ones(15)*3000000])
})
analysis = detect_obv_strength(None, bearish_data, trend_period=20, ma_period=10, strength_threshold=10.0)
print(f"   Bearish signal: {analysis['signal']}")
assert analysis['signal'] in ["bearish", "strong_bearish", "neutral"], "Should be bearish"
print("   ✓ Passed")

print("\n6. Testing Edge Cases")
# Test with minimal data
minimal_data = pd.DataFrame({
    'close': [100, 101, 102],
    'volume': [1000000, 1000000, 1000000]
})
analysis = detect_obv_strength(None, minimal_data, trend_period=5, ma_period=2, strength_threshold=5.0)
assert analysis['trend'] in ["rising", "declining", "neutral"]
print("   ✓ Minimal data handled")

# Test with None data
analysis = detect_obv_strength(None, None, trend_period=20, ma_period=10, strength_threshold=15.0)
assert analysis['trend'] == 'neutral'
print("   ✓ None data handled safely")

print("\n✅ All OBV analysis tests passed!")
