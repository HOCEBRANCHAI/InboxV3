#!/usr/bin/env python3
"""Check what error a failed job has"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Get the most recent failed job
response = supabase.table("inbox_jobs")\
    .select("*")\
    .eq("status", "failed")\
    .order("created_at", desc=True)\
    .limit(1)\
    .execute()

if response.data:
    job = response.data[0]
    print("=" * 80)
    print("MOST RECENT FAILED JOB")
    print("=" * 80)
    print(f"Job ID: {job.get('id')}")
    print(f"Status: {job.get('status')}")
    print(f"Error: {job.get('error')}")
    print(f"Total files: {job.get('total_files')}")
    print(f"Processed files: {job.get('processed_files')}")
    print(f"Created: {job.get('created_at')}")
    print(f"Updated: {job.get('updated_at')}")
    
    print("\n" + "=" * 80)
    print("FILE STORAGE URLS")
    print("=" * 80)
    file_storage_urls = job.get("file_storage_urls")
    if file_storage_urls:
        print(f"Type: {type(file_storage_urls)}")
        if isinstance(file_storage_urls, str):
            print(f"Length: {len(file_storage_urls)}")
            print(f"First 500 chars: {file_storage_urls[:500]}")
        elif isinstance(file_storage_urls, list):
            print(f"List length: {len(file_storage_urls)}")
    else:
        print("NULL or empty")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    error = job.get("error")
    if error:
        print(f"Error message: {error}")
        if "No file data found" in error:
            print("\n*** THIS IS THE PROBLEM ***")
            print("The worker cannot find file data, but we know it exists in the database.")
            print("This means get_file_data() is returning None even though data exists.")
            print("\nPossible causes:")
            print("1. get_file_data() is not being called correctly")
            print("2. The parsing logic is failing silently")
            print("3. There's a timing issue with database reads")
    else:
        print("No error message stored")
else:
    print("No failed jobs found")

