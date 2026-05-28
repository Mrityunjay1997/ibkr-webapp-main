#!/usr/bin/env python3
"""Debug test to verify news filtering logic."""

from datetime import datetime, timezone, timedelta
from news.utils import news_within_minutes, is_within_news_window, parse_news_datetime

def test_scenario_1():
    """Test: User sets 5 days in NewsWithinValue, 'days' in NewsTimeUnit"""
    form = {
        "NewsWithinValue": 5,
        "NewsTimeUnit": "days"
    }
    
    minutes = news_within_minutes(form)
    print(f"Scenario 1 (5 days): news_within_minutes returned {minutes} (expected 7200)")
    assert minutes == 7200, f"Expected 7200 but got {minutes}"
    
    # Test filtering with a recent headline
    now = datetime.now(timezone.utc)
    recent_headline_time = now - timedelta(days=2)  # 2 days ago
    recent_headline_str = recent_headline_time.isoformat()
    
    within = is_within_news_window(recent_headline_str, minutes, now=now)
    print(f"  Recent headline (2 days ago): within={within} (expected True)")
    assert within == True, "Recent headline should be within 5-day window"
    
    # Test filtering with an old headline
    old_headline_time = now - timedelta(days=10)  # 10 days ago
    old_headline_str = old_headline_time.isoformat()
    
    outside = is_within_news_window(old_headline_str, minutes, now=now)
    print(f"  Old headline (10 days ago): within={outside} (expected False)")
    assert outside == False, "Old headline should be outside 5-day window"
    
    print("✓ Scenario 1 passed\n")

def test_scenario_2():
    """Test: User sets 0 (default) - should show all headlines"""
    form = {
        "NewsWithinValue": 0,
        "NewsTimeUnit": "minutes"
    }
    
    minutes = news_within_minutes(form)
    print(f"Scenario 2 (default 0): news_within_minutes returned {minutes} (expected 0)")
    assert minutes == 0, f"Expected 0 but got {minutes}"
    
    now = datetime.now(timezone.utc)
    
    # Any time should pass when minutes == 0
    recent_headline_time = now - timedelta(days=2)
    recent_headline_str = recent_headline_time.isoformat()
    
    within = is_within_news_window(recent_headline_str, minutes, now=now)
    print(f"  Any headline with 0 minutes: within={within} (expected True)")
    assert within == True, "With 0 minutes, all headlines should pass"
    
    print("✓ Scenario 2 passed\n")

def test_scenario_3():
    """Test: String values from form submission"""
    # This is what comes from serializeArray()
    form = {
        "NewsWithinValue": "5",  # STRING
        "NewsTimeUnit": "days"   # STRING
    }
    
    minutes = news_within_minutes(form)
    print(f"Scenario 3 (string '5' days): news_within_minutes returned {minutes} (expected 7200)")
    assert minutes == 7200, f"Expected 7200 but got {minutes}"
    
    print("✓ Scenario 3 passed\n")

def test_scenario_4():
    """Test: String '10' with missing NewsTimeUnit - should default to minutes"""
    form = {
        "NewsWithinValue": "10",
        # NewsTimeUnit missing
    }
    
    minutes = news_within_minutes(form)
    print(f"Scenario 4 (10 with missing unit): news_within_minutes returned {minutes}")
    print(f"  Expected 10 (defaulting to minutes, not days!)")
    assert minutes == 10, f"Expected 10 but got {minutes}"
    
    print("✓ Scenario 4 passed (reveals potential issue!)\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing news headline filtering logic")
    print("=" * 60 + "\n")
    
    try:
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()
        test_scenario_4()
        print("=" * 60)
        print("All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        print("=" * 60)
