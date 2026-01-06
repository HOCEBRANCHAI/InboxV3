#!/usr/bin/env python3
"""Complete verification script to check everything is working"""

import os
import sys
import json
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

print("=" * 80)
print("COMPLETE SYSTEM VERIFICATION")
print("=" * 80)

# ============================================================================
# 1. CHECK ENVIRONMENT VARIABLES
# ============================================================================
print("\n[1/8] Checking Environment Variables...")
print("-" * 80)

required_vars = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENAI_API_KEY"
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if "KEY" in var or "SECRET" in var:
            display_value = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
        else:
            display_value = value
        print(f"  OK: {var} = {display_value}")
    else:
        print(f"  ERROR: {var} is not set")
        missing_vars.append(var)

if missing_vars:
    print(f"\n  FAILED: Missing {len(missing_vars)} environment variable(s)")
    sys.exit(1)
else:
    print("  SUCCESS: All environment variables are set")

# ============================================================================
# 2. CHECK SUPABASE CONNECTION
# ============================================================================
print("\n[2/8] Checking Supabase Connection...")
print("-" * 80)

try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Test connection by querying a table
    response = supabase.table("inbox_jobs").select("id").limit(1).execute()
    print("  SUCCESS: Connected to Supabase")
    print(f"  INFO: Can query inbox_jobs table")
except Exception as e:
    print(f"  ERROR: Failed to connect to Supabase: {e}")
    sys.exit(1)

# ============================================================================
# 3. CHECK DATABASE SCHEMA
# ============================================================================
print("\n[3/8] Checking Database Schema...")
print("-" * 80)

try:
    # Get a sample job to see all columns
    response = supabase.table("inbox_jobs").select("*").limit(1).execute()
    
    if response.data:
        job = response.data[0]
        columns = list(job.keys())
        
        required_columns = [
            "id",
            "status",
            "endpoint_type",
            "file_storage_urls",
            "file_data",
            "user_id",
            "created_at",
            "updated_at"
        ]
        
        missing_columns = []
        for col in required_columns:
            if col in columns:
                print(f"  OK: Column '{col}' exists")
            else:
                print(f"  ERROR: Column '{col}' is missing")
                missing_columns.append(col)
        
        if missing_columns:
            print(f"\n  FAILED: Missing {len(missing_columns)} column(s)")
            print(f"  Run migration: supabase_storage_migration.sql")
        else:
            print("  SUCCESS: All required columns exist")
    else:
        print("  WARNING: No jobs in database (this is OK for new setup)")
        print("  INFO: Will check schema by creating a test job")
        
except Exception as e:
    print(f"  ERROR: Failed to check schema: {e}")
    sys.exit(1)

# ============================================================================
# 4. CHECK STORAGE BUCKET
# ============================================================================
print("\n[4/8] Checking Supabase Storage...")
print("-" * 80)

try:
    bucket_name = "inbox-files"
    # Try to list buckets
    buckets = supabase.storage.list_buckets()
    
    bucket_exists = False
    for bucket in buckets:
        if bucket.name == bucket_name:
            bucket_exists = True
            print(f"  SUCCESS: Bucket '{bucket_name}' exists")
            print(f"  INFO: Bucket is {'public' if bucket.public else 'private'}")
            break
    
    if not bucket_exists:
        print(f"  ERROR: Bucket '{bucket_name}' does not exist")
        print(f"  ACTION: Create bucket in Supabase Dashboard -> Storage")
    else:
        # Try to list files (should not error even if empty)
        try:
            files = supabase.storage.from_(bucket_name).list()
            print(f"  SUCCESS: Can access bucket (found {len(files) if files else 0} files)")
        except Exception as e:
            print(f"  WARNING: Cannot list files in bucket: {e}")
            print(f"  INFO: This might be a permissions issue")
            
except Exception as e:
    print(f"  ERROR: Failed to check storage: {e}")

# ============================================================================
# 5. CHECK RECENT JOBS DATA FORMAT
# ============================================================================
print("\n[5/8] Checking Recent Jobs Data Format...")
print("-" * 80)

try:
    # Get most recent job
    response = supabase.table("inbox_jobs")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    
    if response.data:
        job = response.data[0]
        job_id = job.get("id")
        status = job.get("status")
        
        print(f"  INFO: Most recent job: {job_id}")
        print(f"  INFO: Status: {status}")
        
        # Check file_storage_urls
        file_storage_urls = job.get("file_storage_urls")
        if file_storage_urls is not None:
            print(f"  OK: file_storage_urls exists")
            print(f"  INFO: Type: {type(file_storage_urls).__name__}")
            
            if isinstance(file_storage_urls, str):
                try:
                    parsed = json.loads(file_storage_urls)
                    if isinstance(parsed, list):
                        print(f"  SUCCESS: Can parse as JSON list")
                        print(f"  INFO: Contains {len(parsed)} file(s)")
                        if len(parsed) > 0:
                            first_file = parsed[0]
                            if "storage_url" in first_file:
                                print(f"  SUCCESS: Has storage_url field")
                            else:
                                print(f"  WARNING: Missing storage_url field")
                    else:
                        print(f"  ERROR: Parsed but not a list: {type(parsed)}")
                except Exception as e:
                    print(f"  ERROR: Cannot parse JSON: {e}")
            elif isinstance(file_storage_urls, list):
                print(f"  SUCCESS: Already a list (ready to use)")
                print(f"  INFO: Contains {len(file_storage_urls)} file(s)")
            else:
                print(f"  WARNING: Unexpected type: {type(file_storage_urls)}")
        else:
            print(f"  WARNING: file_storage_urls is NULL")
            print(f"  INFO: This is OK if job was created before migration")
    else:
        print("  INFO: No jobs in database yet")
        
except Exception as e:
    print(f"  ERROR: Failed to check jobs: {e}")

# ============================================================================
# 6. CHECK WORKER CAN READ DATA
# ============================================================================
print("\n[6/8] Checking Worker Can Read Data...")
print("-" * 80)

try:
    # Import job_service functions
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from job_service import get_file_data, get_pending_jobs
    
    # Check if we can get pending jobs
    pending = get_pending_jobs(limit=5)
    print(f"  INFO: Found {len(pending)} pending job(s)")
    
    # Check if we can read file data from a recent job
    response = supabase.table("inbox_jobs")\
        .select("id,file_storage_urls")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    
    if response.data:
        test_job_id = response.data[0].get("id")
        file_data = get_file_data(test_job_id)
        
        if file_data:
            print(f"  SUCCESS: Can read file data for job {test_job_id}")
            print(f"  INFO: Retrieved {len(file_data)} file(s)")
        else:
            print(f"  WARNING: Cannot read file data for job {test_job_id}")
            print(f"  INFO: Check get_file_data() function")
    else:
        print("  INFO: No jobs to test with")
        
except Exception as e:
    print(f"  ERROR: Failed to check worker functions: {e}")
    import traceback
    print(traceback.format_exc())

# ============================================================================
# 7. CHECK API ENDPOINTS (if possible)
# ============================================================================
print("\n[7/8] Checking API Configuration...")
print("-" * 80)

# Check if main.py exists and can be imported
main_py_path = os.path.join(os.path.dirname(__file__), "main.py")
if os.path.exists(main_py_path):
    print("  OK: main.py exists")
    
    # Check for required imports
    try:
        with open(main_py_path, 'r') as f:
            content = f.read()
            
        required_imports = [
            "from fastapi import",
            "from job_service import",
            "store_file_storage_urls",
            "upload_file_to_storage"
        ]
        
        for imp in required_imports:
            if imp in content:
                print(f"  OK: Has {imp}")
            else:
                print(f"  WARNING: Missing {imp}")
    except Exception as e:
        print(f"  ERROR: Cannot read main.py: {e}")
else:
    print("  ERROR: main.py not found")

# ============================================================================
# 8. SUMMARY AND RECOMMENDATIONS
# ============================================================================
print("\n[8/8] Summary and Recommendations")
print("-" * 80)

print("\nVERIFICATION COMPLETE")
print("\nNext Steps:")
print("1. If any errors above, fix them first")
print("2. Deploy updated code to Render")
print("3. Create a test job via API")
print("4. Check worker logs for processing")
print("5. Verify job completes successfully")

print("\n" + "=" * 80)
print("If everything above shows SUCCESS, your system should work!")
print("=" * 80)

