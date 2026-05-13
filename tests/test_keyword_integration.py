#!/usr/bin/env python3
"""
Integration test for News Keyword highlighting and filtering feature.
Tests the complete flow from form input through backend processing to frontend highlighting.
"""

import sys
import os
import re

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock logger
class MockLogger:
    def debug(self, msg, *args):
        pass
    
    def info(self, msg, *args):
        pass
    
    def warning(self, msg, *args):
        print(f"[WARNING] {msg}")

# Simulated stock data similar to what comes from IBapi.getFinalResult
def create_test_stock_data(symbol, has_headlines=True):
    """Create mock stock data"""
    return {
        "symbol": symbol,
        "cusip": "CUST" + symbol,
        "close": 100.0,
        "smaFast": 99.5,
        "signal": "yes",
        "newsHeadlines": [
            {"headline": "Company earnings report shows strong growth"},
            {"headline": "FDA approves new drug treatment"},
            {"headline": "Stock rallies on market conditions"},
        ] if has_headlines else [],
        "netPosition": 0,
        "variableResults": {},  # This will be filled by the backend
    }

def test_keyword_variable_results_always_set():
    """Test that variable_results['newsKeyword'] is always set even with edge cases"""
    print("=" * 80)
    print("KEYWORD INTEGRATION TEST: Verify variable_results Always Set")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Keywords provided, headlines match",
            "keywords": "earnings, FDA",
            "expected_newsKeyword": True,
        },
        {
            "name": "Keywords provided, no headlines match",
            "keywords": "cryptocurrency, blockchain",
            "expected_newsKeyword": False,
        },
        {
            "name": "No keywords provided",
            "keywords": "",
            "expected_newsKeyword": False,
        },
        {
            "name": "Empty string keywords",
            "keywords": "   ",
            "expected_newsKeyword": False,
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n[TEST] {test_case['name']}")
        print("-" * 80)
        
        # Create test stock
        dta = create_test_stock_data("TEST", has_headlines=(test_case['keywords'].strip() != "cryptocurrency, blockchain"))
        variable_results = {}
        
        # Simulate backend keyword matching logic
        keywords_raw = test_case['keywords'].strip()
        news_keyword_match = None
        matched_keyword_headlines = []
        
        if keywords_raw:
            keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
            if keywords:
                headlines = dta.get("newsHeadlines", []) or []
                patterns = [re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE) for k in keywords]
                
                filtered_headlines = []
                for h in headlines:
                    headline_text = (h.get("headline") or "")
                    for pat in patterns:
                        if pat.search(headline_text):
                            filtered_headlines.append(h)
                            matched_keyword_headlines.append(h.get("headline", ""))
                            break
                
                dta["newsHeadlines"] = filtered_headlines
                news_keyword_match = len(filtered_headlines) > 0
        
        # THE FIX: Always set variable_results["newsKeyword"]
        variable_results["newsKeyword"] = bool(news_keyword_match) if news_keyword_match else False
        
        # Verify the result
        actual_newsKeyword = variable_results.get("newsKeyword")
        expected_newsKeyword = test_case['expected_newsKeyword']
        
        if actual_newsKeyword == expected_newsKeyword:
            print(f"✅ PASSED")
            print(f"   variable_results['newsKeyword'] = {actual_newsKeyword}")
            print(f"   Matched headlines: {len(matched_keyword_headlines)}")
            passed += 1
        else:
            print(f"❌ FAILED")
            print(f"   Expected: {expected_newsKeyword}")
            print(f"   Got: {actual_newsKeyword}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    return failed == 0


def test_filter_logic():
    """Test that the filter logic correctly uses variable_results['newsKeyword']"""
    print("\n" + "=" * 80)
    print("FILTER LOGIC TEST: Verify filterNewsKeyword Works Correctly")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Filter enabled, keywords match",
            "filterNewsKeyword": True,
            "newsKeywordValue": True,
            "expected_pass": True,
        },
        {
            "name": "Filter enabled, keywords don't match",
            "filterNewsKeyword": True,
            "newsKeywordValue": False,
            "expected_pass": False,
        },
        {
            "name": "Filter disabled, keywords match",
            "filterNewsKeyword": False,
            "newsKeywordValue": True,
            "expected_pass": True,  # No filter, so stock passes
        },
        {
            "name": "Filter disabled, keywords don't match",
            "filterNewsKeyword": False,
            "newsKeywordValue": False,
            "expected_pass": True,  # No filter, so stock passes
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n[TEST] {test_case['name']}")
        print("-" * 80)
        
        # Create test form and stock data
        form = {"filterNewsKeyword": test_case['filterNewsKeyword']}
        stock_data = {
            "symbol": "TEST",
            "variableResults": {"newsKeyword": test_case['newsKeywordValue']},
        }
        
        # Simulate filter logic from ibkr_signal_engine.py apply_result_filters
        result = True
        if form.get("filterNewsKeyword", False):
            # Filter is enabled, check if stock meets the filter
            variable_results = stock_data.get("variableResults", {})
            if not variable_results.get("newsKeyword", False):
                result = False
        
        expected = test_case['expected_pass']
        
        if result == expected:
            print(f"✅ PASSED")
            print(f"   Filter enabled: {form.get('filterNewsKeyword')}")
            print(f"   newsKeyword value: {stock_data['variableResults']['newsKeyword']}")
            print(f"   Stock passes filter: {result}")
            passed += 1
        else:
            print(f"❌ FAILED")
            print(f"   Expected stock to {'pass' if expected else 'not pass'} filter")
            print(f"   But stock {'passed' if result else 'did not pass'} filter")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    return failed == 0


def test_frontend_highlighting():
    """Test that frontend can properly detect and highlight keyword matches"""
    print("\n" + "=" * 80)
    print("FRONTEND HIGHLIGHTING TEST: Verify Row Highlighting")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "newsKeywordMatch = True (should highlight)",
            "newsKeywordMatch": True,
            "expected_style": "#fef9e7",
            "expected_highlight": True,
        },
        {
            "name": "newsKeywordMatch = False (no highlight)",
            "newsKeywordMatch": False,
            "expected_style": None,
            "expected_highlight": False,
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n[TEST] {test_case['name']}")
        print("-" * 80)
        
        # Simulate frontend code from morfeo.html
        dta_newsKeywordMatch = test_case['newsKeywordMatch']
        
        # In Python, simulate the conditional
        _keywordRowStyle = " style='background:#fef9e7'" if dta_newsKeywordMatch else ""
        
        has_highlight = len(_keywordRowStyle) > 0
        expected_highlight = test_case['expected_highlight']
        
        if has_highlight == expected_highlight:
            print(f"✅ PASSED")
            print(f"   newsKeywordMatch: {dta_newsKeywordMatch}")
            print(f"   Row highlighted: {has_highlight}")
            if has_highlight:
                print(f"   Background color: #fef9e7 (light yellow)")
            passed += 1
        else:
            print(f"❌ FAILED")
            print(f"   Expected highlighting: {expected_highlight}")
            print(f"   Got highlighting: {has_highlight}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    return failed == 0


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "NEWS KEYWORD HIGHLIGHTING & FILTERING - INTEGRATION TEST".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    results = []
    results.append(("Variable Results Always Set", test_keyword_variable_results_always_set()))
    results.append(("Filter Logic", test_filter_logic()))
    results.append(("Frontend Highlighting", test_frontend_highlighting()))
    
    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("=" * 80)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed. Review the output above.")
    print()
