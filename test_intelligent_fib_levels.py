"""
Test and demonstration of intelligent Fibonacci gap pullback level selection.

This script demonstrates:
1. Historical gap analysis
2. Intelligent Fib level selection
3. Improved calculations for AEHL example
4. Comparison vs. naive closest-level approach
"""

import json
from datetime import datetime, timedelta
from indicators import (
    FibonacciCalculator,
    GapHistoryAnalyzer,
    IntelligentFibonacciLevelSelector,
    RiskRewardEvaluator,
)


def create_sample_aehl_data():
    """Create sample AEHL daily data for testing."""
    # Realistic AEHL pattern with multiple gaps and gap closes
    historical_data = [
        # Earlier data with gap patterns
        {'date': '2026-04-20', 'open': 1.15, 'high': 1.25, 'low': 1.10, 'close': 1.20, 'volume': 5000000},
        {'date': '2026-04-21', 'open': 1.18, 'high': 1.30, 'low': 1.15, 'close': 1.28, 'volume': 6000000},  # Gap up
        {'date': '2026-04-22', 'open': 1.25, 'high': 1.32, 'low': 1.18, 'close': 1.22, 'volume': 7000000},  # Pullback to 1.20
        {'date': '2026-04-23', 'open': 1.22, 'high': 1.28, 'low': 1.15, 'close': 1.18, 'volume': 5500000},
        {'date': '2026-04-24', 'open': 1.16, 'high': 1.22, 'low': 1.12, 'close': 1.15, 'volume': 4500000},
        # More recent pattern
        {'date': '2026-04-27', 'open': 1.18, 'high': 1.25, 'low': 1.15, 'close': 1.22, 'volume': 5000000},
        {'date': '2026-04-28', 'open': 1.21, 'high': 1.38, 'low': 1.18, 'close': 1.35, 'volume': 8000000},  # Gap up 6%
        {'date': '2026-04-29', 'open': 1.32, 'high': 1.40, 'low': 1.25, 'close': 1.32, 'volume': 7500000},  # Pullback to ~1.30
        {'date': '2026-04-30', 'open': 1.30, 'high': 1.35, 'low': 1.20, 'close': 1.25, 'volume': 6000000},  # Further pullback
        {'date': '2026-05-01', 'open': 1.24, 'high': 1.28, 'low': 1.15, 'close': 1.18, 'volume': 5500000},  # Gap close confirmed
        # Today's setup (AEHL scenario)
        {'date': '2026-05-02', 'open': 1.20, 'high': 1.22, 'low': 1.18, 'close': 1.51, 'volume': 5000000},  # Yesterday
    ]
    return historical_data


def test_aehl_scenario():
    """Test with AEHL real-world scenario."""
    print("\n" + "="*80)
    print("INTELLIGENT FIBONACCI LEVEL SELECTION - AEHL EXAMPLE")
    print("="*80)
    
    # AEHL data
    historical_data = create_sample_aehl_data()
    prev_close = 0.51  # Previous day close
    today_high = 2.33  # High of day (move size of 1.82)
    today_low = 0.56   # Low of day
    current_price = 1.58  # Current intraday price (moving between high and low)
    
    print(f"\nAEHL Setup Parameters:")
    print(f"  Previous Close: ${prev_close}")
    print(f"  Today's High: ${today_high}")
    print(f"  Today's Low: ${today_low}")
    print(f"  Move Size: ${today_high - prev_close:.4f} ({(today_high - prev_close) / prev_close * 100:.1f}%)")
    print(f"  Current Price: ${current_price}")
    
    # =========================================================================
    # 1. Basic Fibonacci Levels
    # =========================================================================
    print(f"\n{'-'*80}")
    print("1. BASIC FIBONACCI LEVELS")
    print(f"{'-'*80}")
    
    fib_calc = FibonacciCalculator(prev_close, today_high)
    fib_levels = fib_calc.calculate_levels()
    
    for level_key in sorted(fib_levels.keys()):
        level_data = fib_levels[level_key]
        print(f"  {level_data['level_percent']:6.1f}%: Entry=${level_data['entry']:.4f}  "
              f"Pullback=${level_data['pullback']:.4f}  "
              f"% from Support={level_data['percent_from_support']:6.1f}%")
    
    # =========================================================================
    # 2. Gap History Analysis
    # =========================================================================
    print(f"\n{'-'*80}")
    print("2. HISTORICAL GAP ANALYSIS")
    print(f"{'-'*80}")
    
    gap_analyzer = GapHistoryAnalyzer(lookback_days=50, min_gap_pct=1.0)
    gap_history = gap_analyzer.analyze_gap_history(historical_data, current_price, 'long')
    
    print(f"\n  Historical Gaps Found: {gap_history['gaps_analyzed']}")
    print(f"  Analysis Period: {gap_history['analysis_period_days']} days")
    
    if gap_history['gap_closes']:
        print(f"\n  Gap Close Patterns:")
        for gap in gap_history['gap_closes']:
            if gap['bars_to_close']:
                print(f"    Date: {gap['date']}, Gap: {gap['gap_pct']:.2f}%, "
                      f"Closed in {gap['bars_to_close']} bars, "
                      f"Close Level: ${gap['gap_close_price']:.4f}")
    
    if gap_history['probability_distribution']:
        print(f"\n  Pullback Distance Distribution:")
        for bucket, pct in sorted(gap_history['probability_distribution'].items()):
            print(f"    {bucket:20s}: {pct:5.1f}%")
    
    if gap_history['recommended_pullback_distance']:
        print(f"\n  **Recommended Historical Pullback Distance: "
              f"{gap_history['recommended_pullback_distance']:.1%}**")
    
    # =========================================================================
    # 3. Risk/Reward Evaluation
    # =========================================================================
    print(f"\n{'-'*80}")
    print("3. TECHNICAL RISK/REWARD SCORING")
    print(f"{'-'*80}")
    
    evaluator = RiskRewardEvaluator()
    ranked_levels = evaluator.rank_levels(fib_levels, current_price)
    
    for i, scored_level in enumerate(ranked_levels[:5], 1):
        print(f"\n  Rank #{i}: {scored_level['level_percent']:.1f}% Fib Level")
        print(f"    Entry Price: ${scored_level['entry']:.4f}")
        print(f"    Total Score: {scored_level['total_score']:.1f}/100")
        print(f"    Recommendation: {scored_level['recommendation']}")
        print(f"    Breakdown: {scored_level['scores']}")
    
    # =========================================================================
    # 4. Intelligent Level Selection
    # =========================================================================
    print(f"\n{'-'*80}")
    print("4. INTELLIGENT FIBONACCI LEVEL SELECTION")
    print(f"{'-'*80}")
    
    selector = IntelligentFibonacciLevelSelector()
    intelligent_selection = selector.select_best_levels(
        historical_data, prev_close, today_high, today_low, current_price,
        direction='long', num_recommendations=3
    )
    
    primary = intelligent_selection['primary_level']
    print(f"\n  PRIMARY RECOMMENDATION: {primary['level_pct']:.1f}% Fib Level")
    print(f"    Entry Price: ${primary['entry_price']:.4f}")
    print(f"    Combined Score: {primary['combined_score']:.1f}/100")
    print(f"      - Technical Score: {primary['technical_score']:.1f}/100")
    print(f"      - Historical Score: {primary['history_score']:.1f}/100")
    print(f"    Reasoning: {primary['reasoning']}")
    
    print(f"\n  ALTERNATIVE RECOMMENDATIONS:")
    for i, level_rec in enumerate(intelligent_selection['recommended_levels'][1:], 2):
        print(f"\n    #{i}: {level_rec['level_pct']:.1f}% Fib Level")
        print(f"      Entry Price: ${level_rec['entry_price']:.4f}")
        print(f"      Combined Score: {level_rec['combined_score']:.1f}/100")
        print(f"      Reasoning: {level_rec['reasoning']}")
    
    # =========================================================================
    # 5. Gap Close Level as Alternative
    # =========================================================================
    print(f"\n{'-'*80}")
    print("5. GAP CLOSE (100% PULLBACK) AS ALTERNATIVE")
    print(f"{'-'*80}")
    
    gap_close_level = fib_levels.get('1.000', {})
    if gap_close_level:
        print(f"\n  Gap Close Level Entry: ${gap_close_level['entry']:.4f}")
        print(f"  (This is near previous close of ${prev_close})")
        print(f"  Gap close represents the 100% pullback to fill the gap")
        print(f"  Historical data shows gap closes occur in {gap_history['gaps_analyzed']} out of "
              f"{len(historical_data)} analyzed days")
    
    # =========================================================================
    # 6. Summary & Recommendations
    # =========================================================================
    print(f"\n{'-'*80}")
    print("6. SUMMARY & TRADING RECOMMENDATIONS")
    print(f"{'-'*80}")
    
    print(f"""
    SETUP ANALYSIS:
    - Stock gapped up {(today_high - prev_close) / prev_close * 100:.1f}% from ${prev_close} to ${today_high}
    - Current pullback price: ${current_price}
    - Distance from high: ${today_high - current_price:.4f} ({(today_high - current_price) / (today_high - prev_close) * 100:.1f}% of gap)
    
    BEST ENTRY LEVEL(S):
    1. Primary: {primary['level_pct']:.1f}% Fib (${primary['entry_price']:.4f})
       Confidence: {primary['combined_score']:.0f}%
       Why: {primary['reasoning']}
    
    2. Historical Probability: {gap_history['recommended_pullback_distance']:.1%} 
       (Based on {gap_history['gaps_analyzed']} historical gap patterns)
    
    3. Gap Close: 100% (${gap_close_level['entry']:.4f})
       This is the previous close level
       Good for lower-risk, but late entries
    
    RISK/REWARD CONSIDERATION:
    - Use stop loss below {primary['entry_price']:.4f} (below entry point)
    - Target profit above entry point for 2:1 or better risk/reward
    - Monitor if stock respects the recommended level
    
    TRAPPED ORDERS ANALYSIS:
    - Check if price moves back through recent highs after pullback
    - Market makers may try to trap orders at round numbers
    - Watch for failed breakouts at resistance levels
    """)


def compare_methods():
    """Compare naive vs intelligent level selection."""
    print("\n" + "="*80)
    print("COMPARISON: NAIVE vs INTELLIGENT LEVEL SELECTION")
    print("="*80)
    
    # Setup
    prev_close = 0.51
    today_high = 2.33
    today_low = 0.56
    current_price = 1.58
    
    # Historical data
    historical_data = create_sample_aehl_data()
    
    # Naive approach - pick closest to current price
    fib_calc = FibonacciCalculator(prev_close, today_high)
    fib_levels = fib_calc.calculate_levels()
    
    closest_level = None
    closest_distance = float('inf')
    
    for level_key, level_data in fib_levels.items():
        distance = abs(level_data['entry'] - current_price)
        if distance < closest_distance:
            closest_distance = distance
            closest_level = level_data
    
    print(f"\nNAIVE APPROACH (Pick closest Fib level):")
    print(f"  Selected: {closest_level['level_percent']:.1f}% Fib")
    print(f"  Entry: ${closest_level['entry']:.4f}")
    print(f"  Distance from current price: ${closest_distance:.4f}")
    
    # Intelligent approach
    selector = IntelligentFibonacciLevelSelector()
    intelligent = selector.select_best_levels(
        historical_data, prev_close, today_high, today_low, current_price,
        direction='long', num_recommendations=1
    )
    
    primary = intelligent['primary_level']
    print(f"\nINTELLIGENT APPROACH (History-informed):")
    print(f"  Selected: {primary['level_pct']:.1f}% Fib")
    print(f"  Entry: ${primary['entry_price']:.4f}")
    print(f"  Combined Score: {primary['combined_score']:.1f}/100")
    print(f"  Reasoning: {primary['reasoning']}")
    
    print(f"\nDIFFERENCE:")
    difference = abs(primary['entry_price'] - closest_level['entry'])
    print(f"  Entry Price Difference: ${difference:.4f}")
    print(f"  Better Historical Alignment: {primary['history_score'] > 50}")


if __name__ == '__main__':
    # Run demonstrations
    test_aehl_scenario()
    compare_methods()
    
    print("\n" + "="*80)
    print("END OF TEST")
    print("="*80)
