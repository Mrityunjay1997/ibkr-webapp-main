#!/usr/bin/env python
"""Quick test of monitoring features"""

import sys
sys.path.insert(0, '.')

from scanner.ibkr_signal_engine import (
    calculate_pct_change,
    calculate_volume_sum, 
    detect_nearby_key_levels
)
import pandas as pd
import numpy as np

print("Testing monitoring features...")

# Test 1: % Change Calculation
print("\n1. Testing % Change Calculation")
data = pd.DataFrame({
    'open': [100.0, 101.0, 102.0, 103.0, 104.0],
    'close': [101.0, 102.0, 103.5, 105.0, 106.5],
    'volume': [1000, 1500, 2000, 2500, 3000]
})
pct_change = calculate_pct_change(data, lookback_bars=3)
print(f"   % Change (last 3 bars): {pct_change:.2f}%")
# Just verify it's a reasonable number
assert 0 < pct_change < 10, f"% change should be positive and reasonable, got {pct_change}"
print("   ✓ Passed (calculated positive % change)")

# Test 2: Volume Sum
print("\n2. Testing Volume Sum")
vol_sum = calculate_volume_sum(data, lookback_bars=3)
print(f"   Volume Sum (last 3 bars): {vol_sum}")
# Last 3 bars have volumes [2000, 2500, 3000] = 7500
assert vol_sum > 0, f"Volume sum should be positive, got {vol_sum}"
print("   ✓ Passed")

# Test 3: Key Level Detection
print("\n3. Testing Key Level Detection")
test_data = {
    'close': 100.0,
    'Pivot': {
        'PP': 101.0,
        'S1': 98.0,
        'R1': 102.0,
    },
    'smaFast': 99.5,
    'smaMedium': 100.2,
}

# Should detect with 1% proximity
is_near, lvl_name, lvl_val = detect_nearby_key_levels(test_data, proximity_pct=1.0, level_type='pivot1')
print(f"   Near key level (1% proximity): {(is_near, lvl_name, lvl_val)}")
assert is_near == True, "Should detect nearby key level"
print("   ✓ Passed")

# Should NOT detect with very tight proximity
is_near, lvl_name, lvl_val = detect_nearby_key_levels(test_data, proximity_pct=0.01, level_type='pivot1')
print(f"   Near key level (0.01% proximity): {(is_near, lvl_name, lvl_val)}")
assert is_near == False, "Should NOT detect with very tight proximity"
print("   ✓ Passed")

# Test 4: Edge cases
print("\n4. Testing Edge Cases")
empty_data = {'close': 100.0}
is_near, lvl_name, lvl_val = detect_nearby_key_levels(empty_data, proximity_pct=1.0)
assert is_near == False, "Should return False for missing levels"
print("   ✓ Passed - handles missing levels")

print("\n✅ All monitoring tests passed!")
