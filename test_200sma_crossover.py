#!/usr/bin/env python
"""Test 200 SMA bullish crossover detection"""

import sys
sys.path.insert(0, '.')

from ibkr_signal_engine import detect_200sma_bullish_crossover

print("Testing 200 SMA bullish crossover detection...")

# Test 1: Bullish crossover detected (prev < 200SMA, current > 200SMA)
print("\n1. Testing bullish crossover (prev below, now above)")
test_data = {
    'close': 105.0,      # Current close above 200 SMA
    'smaSlow': 103.0,    # 200 SMA
    'prevClose': 102.0   # Previous close below 200 SMA
}
result = detect_200sma_bullish_crossover(test_data)
print(f"   Bullish crossover detected: {result}")
assert result == True, "Should detect bullish crossover"
print("   ✓ Passed")

# Test 2: No crossover - both above
print("\n2. Testing no crossover (both above 200 SMA)")
test_data = {
    'close': 105.0,
    'smaSlow': 103.0,
    'prevClose': 104.0   # Previous also above
}
result = detect_200sma_bullish_crossover(test_data)
print(f"   Bullish crossover detected: {result}")
assert result == False, "Should NOT detect crossover"
print("   ✓ Passed")

# Test 3: Bearish crossover - close below
print("\n3. Testing bearish (close below 200 SMA)")
test_data = {
    'close': 101.0,      # Current below
    'smaSlow': 103.0,
    'prevClose': 104.0   # Previous above
}
result = detect_200sma_bullish_crossover(test_data)
print(f"   Bullish crossover detected: {result}")
assert result == False, "Should NOT detect crossover"
print("   ✓ Passed")

# Test 4: Edge case - exactly at SMA
print("\n4. Testing price exactly at 200 SMA")
test_data = {
    'close': 103.0,      # Exactly at SMA (not above)
    'smaSlow': 103.0,
    'prevClose': 102.0
}
result = detect_200sma_bullish_crossover(test_data)
print(f"   Bullish crossover detected: {result}")
assert result == False, "Should NOT detect (must be above, not equal)"
print("   ✓ Passed")

# Test 5: Missing data
print("\n5. Testing missing data")
test_data = {'close': 105.0}
result = detect_200sma_bullish_crossover(test_data)
print(f"   Bullish crossover detected: {result}")
assert result == False, "Should return False on missing data"
print("   ✓ Passed")

print("\n✅ All 200 SMA bullish crossover tests passed!")
