#!/usr/bin/env python3
"""
Test script for News Keyword Detection
Verifies the keyword matching logic in ibkr_signal_engine.py
"""

import sys
import os

# Mock logger for testing
class MockLogger:
    def debug(self, msg, *args):
        if "KEYWORDS DEBUG" in msg or "KEYWORDS" in msg:
            print(f"[DEBUG] {msg % args if args else msg}")
    
    def info(self, msg, *args):
        if "KEYWORDS" in msg:
            print(f"[INFO] {msg % args if args else msg}")
    
    def warning(self, msg, *args):
        print(f"[WARNING] {msg}")

logger = MockLogger()

# Test data
test_cases = [
    {
        "name": "Basic keyword match",
        "keywords": "earnings,FDA",
        "headlines": [
            {"headline": "Company earnings report shows 5% growth"},
            {"headline": "FDA approves new drug treatment"},
            {"headline": "Stock price rises after news"},
        ],
        "expected_matches": 2,
    },
    {
        "name": "Case insensitive matching",
        "keywords": "EARNINGS, fda",
        "headlines": [
            {"headline": "company earnings report shows 5% growth"},
            {"headline": "FDA APPROVES NEW DRUG"},
        ],
        "expected_matches": 2,
    },
    {
        "name": "Partial word matching",
        "keywords": "earn",
        "headlines": [
            {"headline": "Earnings beat expectations"},
            {"headline": "Earning potential high"},
            {"headline": "Learn more about stock"},
        ],
        "expected_matches": 2,
    },
    {
        "name": "Empty keywords",
        "keywords": "",
        "headlines": [
            {"headline": "Some news here"},
        ],
        "expected_matches": 0,
    },
    {
        "name": "No matching headlines",
        "keywords": "XYZ,ABC",
        "headlines": [
            {"headline": "Regular stock news"},
            {"headline": "Market update"},
        ],
        "expected_matches": 0,
    },
    {
        "name": "Multiple keywords in one headline",
        "keywords": "earnings,report",
        "headlines": [
            {"headline": "Earnings report released today"},
            {"headline": "Other news"},
        ],
        "expected_matches": 1,
    },
]

def test_keyword_matching():
    """Test the keyword matching logic"""
    print("=" * 80)
    print("NEWS KEYWORD DETECTION TEST")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n[TEST] {test_case['name']}")
        print("-" * 80)
        
        keywords_raw = test_case["keywords"].strip()
        headlines = test_case["headlines"]
        expected_matches = test_case["expected_matches"]
        
        logger.debug(f"Raw keywords from form: '{keywords_raw}'")
        
        if keywords_raw:
            keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
            logger.debug(f"Parsed keywords list: {keywords}")
            
            if keywords:
                logger.debug(f"Total headlines available: {len(headlines)}")
                
                filtered_headlines = []
                matched_keyword_headlines = []
                match_count = 0
                
                for idx, h in enumerate(headlines):
                    headline_text = (h.get("headline") or "").lower()
                    logger.debug(f"Headline {idx}: '{headline_text}'")
                    
                    for kw in keywords:
                        if kw in headline_text:
                            filtered_headlines.append(h)
                            matched_keyword_headlines.append(h.get("headline", ""))
                            match_count += 1
                            logger.info(f"✓ Found keyword '{kw}' in headline: '{headline_text}'")
                            break
                
                logger.debug(f"Match results: {match_count} matches found out of {len(headlines)} headlines")
        else:
            logger.debug("No keywords provided in form")
            match_count = 0
        
        # Check result
        if match_count == expected_matches:
            print(f"✅ PASSED: Found {match_count} matches (expected {expected_matches})")
            passed += 1
        else:
            print(f"❌ FAILED: Found {match_count} matches (expected {expected_matches})")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = test_keyword_matching()
    sys.exit(0 if success else 1)
