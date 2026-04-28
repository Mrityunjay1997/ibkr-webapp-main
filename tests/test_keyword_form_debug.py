#!/usr/bin/env python3
"""
Debug script to test if NewsKeywords field is being included in form serialization.
This simulates what jQuery's serializeArray() would do.
"""

# Simulate a form dict that would come from jQuery's serializeArray()
# This tests if the field name is correct

form_data = {
    "FastSMA": "5",
    "ComparisonFastSMA": "lower",
    "NewsMaxHeadlines": "5",
    "NewsKeywords": "earnings, FDA, merger",  # This is what we expect
    "ComparisonNews": "enabled",
}

print("=" * 80)
print("FORM DATA DEBUG TEST")
print("=" * 80)
print(f"\nForm dict: {form_data}")
print(f"\nForm keys: {list(form_data.keys())}")

# Test 1: Check if NewsKeywords is in the form
keywords_raw = form_data.get("NewsKeywords", "").strip()
print(f"\n[TEST 1] NewsKeywords retrieval:")
print(f"  keywords_raw = form.get('NewsKeywords', '').strip()")
print(f"  Result: '{keywords_raw}'")
print(f"  Type: {type(keywords_raw)}")
print(f"  Bool(keywords_raw): {bool(keywords_raw)}")

# Test 2: Parse keywords
if keywords_raw:
    keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
    print(f"\n[TEST 2] Keyword parsing:")
    print(f"  Parsed keywords: {keywords}")
else:
    print(f"\n[TEST 2] No keywords_raw to parse!")

# Test 3: Check what happens with empty keywords
print(f"\n[TEST 3] Empty keywords case:")
form_empty = {"FastSMA": "5"}  # No NewsKeywords field
keywords_raw_empty = form_empty.get("NewsKeywords", "").strip()
print(f"  form.get('NewsKeywords', '').strip() with missing field:")
print(f"  Result: '{keywords_raw_empty}'")
print(f"  Bool(keywords_raw): {bool(keywords_raw_empty)}")

print("\n" + "=" * 80)
print("If Test 1 shows empty result, the field isn't being serialized from the form.")
print("=" * 80)
