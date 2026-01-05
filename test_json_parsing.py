#!/usr/bin/env python3
"""Test JSON parsing for file_storage_urls format from database"""

import json

# This is the exact format from your database
test_data = '[{\"size\": 4361368, \"suffix\": \".jpg\", \"filename\": \"5ccb62ee-d416-4988-a919-e58c4c40d196-copied-media~2.jpg\", \"storage_url\": \"https://jdftjmzcvdnxfgxcgthg.supabase.co/storage/v1/object/public/inbox-files/e9305f92-8d02-494f-850c-35f8fbbd8727/5ccb62ee-d416-4988-a919-e58c4c40d196-copied-media_2.jpg\"}, {\"size\": 4354563, \"suffix\": \".jpg\", \"filename\": \"91f25c28-0798-4df5-8cae-5adfe3815e7b-copied-media~2.jpg\", \"storage_url\": \"https://jdftjmzcvdnxfgxcgthg.supabase.co/storage/v1/object/public/inbox-files/e9305f92-8d02-494f-850c-35f8fbbd8727/91f25c28-0798-4df5-8cae-5adfe3815e7b-copied-media_2.jpg\"}]'

print("Original data:")
print(test_data[:200])
print("\n" + "="*80 + "\n")

# Test 1: Direct parse (should work)
try:
    parsed1 = json.loads(test_data)
    print("SUCCESS: Test 1 - Direct parse")
    print(f"   Type: {type(parsed1)}, Length: {len(parsed1) if isinstance(parsed1, list) else 'N/A'}")
    if isinstance(parsed1, list) and len(parsed1) > 0:
        print(f"   First item keys: {list(parsed1[0].keys())}")
        print(f"   First item storage_url: {parsed1[0].get('storage_url', 'NOT FOUND')}")
except Exception as e:
    print(f"FAILED: Test 1 - Direct parse: {e}")

# Test 2: If wrapped in quotes (double-encoded)
test_data_wrapped = f'"{test_data}"'
print("\n" + "="*80 + "\n")
print("Testing double-encoded format:")
print(test_data_wrapped[:200])

try:
    # Remove outer quotes
    cleaned = test_data_wrapped[1:-1] if test_data_wrapped.startswith('"') and test_data_wrapped.endswith('"') else test_data_wrapped
    # Unescape
    cleaned = cleaned.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
    parsed2 = json.loads(cleaned)
    print("SUCCESS: Test 2 - Double-encoded parse")
    print(f"   Type: {type(parsed2)}, Length: {len(parsed2) if isinstance(parsed2, list) else 'N/A'}")
except Exception as e:
    print(f"FAILED: Test 2 - Double-encoded parse: {e}")

print("\n" + "="*80 + "\n")
print("CONCLUSION: The data should parse directly with json.loads()")
print("If it's wrapped in quotes, remove them first, then parse.")

