#!/usr/bin/env python3
"""Diagnostic script to check what's wrong with job processing"""

import os
import sys
import json
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Get Supabase credentials
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
    sys.exit(1)

# Create Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Get the most recent failed job
print("=" * 80)
print("DIAGNOSING JOB PROCESSING ISSUE")
print("=" * 80)

# Get recent failed jobs
response = supabase.table("inbox_jobs")\
    .select("*")\
    .eq("status", "failed")\
    .order("created_at", desc=True)\
    .limit(1)\
    .execute()

if not response.data:
    print("No failed jobs found")
    sys.exit(0)

job = response.data[0]
job_id = job.get("id")

print(f"\nJob ID: {job_id}")
print(f"Status: {job.get('status')}")
print(f"Error: {job.get('error')}")
print(f"Total files: {job.get('total_files')}")
print(f"Created: {job.get('created_at')}")

print("\n" + "=" * 80)
print("CHECKING DATABASE COLUMNS")
print("=" * 80)

# Check what columns exist
print(f"\nAll columns in job: {list(job.keys())}")

# Check file_storage_urls
file_storage_urls = job.get("file_storage_urls")
print(f"\nfile_storage_urls:")
print(f"  - Exists: {'file_storage_urls' in job}")
print(f"  - Value: {file_storage_urls}")
print(f"  - Type: {type(file_storage_urls)}")
print(f"  - Is None: {file_storage_urls is None}")
print(f"  - Is empty string: {file_storage_urls == ''}")
print(f"  - Is empty list: {file_storage_urls == []}")

if file_storage_urls is not None:
    if isinstance(file_storage_urls, str):
        print(f"  - String length: {len(file_storage_urls)}")
        print(f"  - First 500 chars: {file_storage_urls[:500]}")
        # Try to parse it
        try:
            parsed = json.loads(file_storage_urls)
            print(f"  - Can parse as JSON: YES")
            print(f"  - Parsed type: {type(parsed)}")
            if isinstance(parsed, list):
                print(f"  - Parsed length: {len(parsed)}")
                if len(parsed) > 0:
                    print(f"  - First item: {parsed[0]}")
        except Exception as e:
            print(f"  - Can parse as JSON: NO - {e}")
    elif isinstance(file_storage_urls, list):
        print(f"  - List length: {len(file_storage_urls)}")
        if len(file_storage_urls) > 0:
            print(f"  - First item: {file_storage_urls[0]}")

# Check file_data (old format)
file_data = job.get("file_data")
print(f"\nfile_data (old format):")
print(f"  - Exists: {'file_data' in job}")
print(f"  - Value: {file_data}")
print(f"  - Type: {type(file_data)}")
print(f"  - Is None: {file_data is None}")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

if file_storage_urls is None:
    print("\nPROBLEM: file_storage_urls is NULL in database")
    print("   This means store_file_storage_urls() either:")
    print("   1. Was never called")
    print("   2. Failed silently")
    print("   3. The column doesn't exist")
elif file_storage_urls == "":
    print("\nPROBLEM: file_storage_urls is empty string")
    print("   This means it was stored as empty")
elif file_storage_urls == []:
    print("\nPROBLEM: file_storage_urls is empty list")
    print("   This means no files were stored")
elif isinstance(file_storage_urls, str):
    print("\nINFO: file_storage_urls is a string (needs parsing)")
    try:
        parsed = json.loads(file_storage_urls)
        if isinstance(parsed, list) and len(parsed) > 0:
            print("   SUCCESS: Can be parsed and has data")
            print("   SUCCESS: The worker should be able to process this")
            print("\n   *** THIS IS THE ISSUE ***")
            print("   The data exists and can be parsed, but get_file_data()")
            print("   is not parsing it correctly. Check the parsing logic.")
        else:
            print("   ERROR: Parsed but empty or not a list")
    except Exception as e:
        print(f"   ERROR: Cannot parse as JSON: {e}")
elif isinstance(file_storage_urls, list):
    print("\nSUCCESS: file_storage_urls is a list (ready to use)")
    if len(file_storage_urls) > 0:
        print("   SUCCESS: Has data - worker should be able to process this")
    else:
        print("   ERROR: Empty list - no files stored")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

if file_storage_urls is None or file_storage_urls == "" or file_storage_urls == []:
    print("\n1. Check web service logs for 'store_file_storage_urls' messages")
    print("2. Verify the file_storage_urls column exists in Supabase")
    print("3. Check if store_file_storage_urls() is being called")
    print("4. Check if there are any errors during storage")
else:
    print("\n1. Data exists in database - check worker logs")
    print("2. Verify get_file_data() is parsing correctly")
    print("3. Check worker exception logs")

print("\n" + "=" * 80)

