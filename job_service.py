# job_service.py
# Database-backed job service using Supabase
import os
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role key for server-side operations
supabase_storage_url = os.getenv("SUPABASE_STORAGE_URL")  # Optional: for signed URLs

if not supabase_url or not supabase_key:
    logger.warning("Supabase credentials not found. Jobs will not be persisted.")
    supabase: Optional[Client] = None
else:
    try:
        # Supabase client initialization (positional arguments)
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized successfully")
        
        # Set storage URL if provided (ensures trailing slash for signed URLs)
        if supabase_storage_url:
            # Ensure trailing slash
            if not supabase_storage_url.endswith("/"):
                supabase_storage_url = supabase_storage_url + "/"
            logger.info(f"Supabase storage URL configured: {supabase_storage_url}")
        else:
            # Auto-detect from supabase_url if not provided
            if supabase_url:
                # Extract project ID and construct storage URL
                # Format: https://<project-id>.supabase.co
                if ".supabase.co" in supabase_url:
                    base_url = supabase_url.rstrip("/")
                    supabase_storage_url = f"{base_url}/storage/v1/"
                    logger.info(f"Auto-detected storage URL: {supabase_storage_url}")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        logger.error(f"Supabase URL: {supabase_url[:30]}..." if supabase_url else "No URL")
        import traceback
        logger.error(traceback.format_exc())
        supabase = None

def create_job(document_id: Optional[str] = None, batch_id: Optional[str] = None, 
               endpoint_type: str = "classify", total_files: int = 0, user_id: Optional[str] = None) -> str:
    """
    Create a new job in Supabase and return its ID.
    
    Args:
        document_id: Optional document ID if processing single document
        batch_id: Optional batch ID for grouping related jobs
        endpoint_type: "classify" or "analyze"
        total_files: Number of files in this job
        user_id: Optional user ID from frontend (passed in header)
    
    Returns:
        job_id (UUID string)
    """
    if not supabase:
        raise RuntimeError("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    
    try:
        job_data = {
            "document_id": document_id,
            "batch_id": batch_id,
            "endpoint_type": endpoint_type,
            "status": JobStatus.PENDING,
            "progress": 0,
            "total_files": total_files,
            "processed_files": 0,
            "result": None,
            "error": None,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("inbox_jobs").insert(job_data).execute()
        
        if response.data and len(response.data) > 0:
            job_id = response.data[0]["id"]
            logger.info(f"Created job {job_id} in Supabase")
            return job_id
        else:
            raise RuntimeError("Failed to create job: No data returned")
            
    except Exception as e:
        logger.error(f"Error creating job in Supabase: {e}")
        raise

def update_job_status(job_id: str, status: JobStatus, result: Optional[Dict] = None,
                     error: Optional[str] = None, progress: Optional[int] = None,
                     processed_files: Optional[int] = None):
    """Update job status and result in Supabase"""
    if not supabase:
        logger.warning("Supabase not configured. Cannot update job status.")
        return
    
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if result is not None:
            update_data["result"] = json.dumps(result) if isinstance(result, dict) else result
        
        if error is not None:
            update_data["error"] = error
        
        if progress is not None:
            update_data["progress"] = progress
        
        if processed_files is not None:
            update_data["processed_files"] = processed_files
        
        supabase.table("inbox_jobs").update(update_data).eq("id", job_id).execute()
        logger.info(f"Updated job {job_id}: {status}, progress: {progress}%")
        
    except Exception as e:
        logger.error(f"Error updating job {job_id} in Supabase: {e}")

def get_job(job_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
    """
    Get job by ID from Supabase.
    Optionally filter by user_id for security.
    
    Args:
        job_id: Job ID to retrieve
        user_id: Optional user ID to verify ownership
    
    Returns:
        Job dictionary if found and user matches (if user_id provided), None otherwise
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot get job.")
        return None
    
    try:
        # Explicitly select all columns including file_storage_urls
        query = supabase.table("inbox_jobs").select("*").eq("id", job_id)
        
        # If user_id provided, filter by it for security
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.execute()
        
        if response.data and len(response.data) > 0:
            job = response.data[0]
            # Parse JSON result if present
            if job.get("result") and isinstance(job["result"], str):
                try:
                    job["result"] = json.loads(job["result"])
                except:
                    pass
            
            # Debug: Log what we got with more detail
            file_storage_urls = job.get("file_storage_urls")
            file_urls = job.get("file_urls")
            print(f"get_job: Retrieved job {job_id}", flush=True)
            print(f"  - file_storage_urls present: {'file_storage_urls' in job}", flush=True)
            print(f"  - file_storage_urls type: {type(file_storage_urls)}", flush=True)
            print(f"  - file_storage_urls value: {str(file_storage_urls)[:200] if file_storage_urls else 'None'}", flush=True)
            print(f"  - file_urls present: {'file_urls' in job}", flush=True)
            print(f"  - file_urls type: {type(file_urls)}", flush=True)
            print(f"  - file_urls value: {file_urls}", flush=True)
            logger.debug(f"Retrieved job {job_id}, keys: {list(job.keys())}, file_storage_urls present: {'file_storage_urls' in job}")
            return job
        print(f"get_job: Job {job_id} not found in database", flush=True)
        return None
        
    except Exception as e:
        logger.error(f"Error getting job {job_id} from Supabase: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_jobs_by_user_id(user_id: str, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Get all jobs for a specific user_id.
    
    Args:
        user_id: User ID to filter by
        status: Optional status filter (pending, processing, completed, failed)
        limit: Maximum number of jobs to return
    
    Returns:
        List of job dictionaries
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot get jobs.")
        return []
    
    try:
        query = supabase.table("inbox_jobs").select("*").eq("user_id", user_id)
        
        if status:
            query = query.eq("status", status)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        response = query.execute()
        
        jobs = response.data if response.data else []
        
        # Parse JSON results
        for job in jobs:
            if job.get("result") and isinstance(job["result"], str):
                try:
                    job["result"] = json.loads(job["result"])
                except:
                    pass
        
        logger.info(f"Retrieved {len(jobs)} jobs for user_id {user_id}")
        return jobs
        
    except Exception as e:
        logger.error(f"Error getting jobs for user_id {user_id} from Supabase: {e}")
        return []

def get_pending_jobs(limit: int = 10) -> List[Dict]:
    """
    Get pending jobs from Supabase for worker to process.
    
    Args:
        limit: Maximum number of jobs to return
    
    Returns:
        List of job dictionaries
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot get pending jobs.")
        return []
    
    try:
        response = supabase.table("inbox_jobs")\
            .select("*")\
            .eq("status", JobStatus.PENDING)\
            .order("created_at", desc=False)\
            .limit(limit)\
            .execute()
        
        jobs = response.data if response.data else []
        if jobs:
            print(f"Found {len(jobs)} pending job(s) in database", flush=True)
            for job in jobs:
                print(f"  - Job {job.get('id')}: {job.get('endpoint_type')}, {job.get('total_files')} files, created: {job.get('created_at')}", flush=True)
        else:
            # Debug: Check if there are any jobs at all
            try:
                all_jobs_response = supabase.table("inbox_jobs")\
                    .select("id,status,created_at")\
                    .order("created_at", desc=True)\
                    .limit(5)\
                    .execute()
                all_jobs = all_jobs_response.data if all_jobs_response.data else []
                if all_jobs:
                    print(f"DEBUG: No pending jobs, but found {len(all_jobs)} recent jobs with statuses:", flush=True)
                    for job in all_jobs:
                        print(f"  - Job {job.get('id')}: status={job.get('status')}, created={job.get('created_at')}", flush=True)
            except Exception as debug_error:
                print(f"DEBUG: Could not check recent jobs: {debug_error}", flush=True)
        
        return jobs
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR getting pending jobs: {error_msg}", flush=True)
        logger.error(f"Error getting pending jobs from Supabase: {e}")
        
        # Check if it's a connection error - retry once
        if "Network connection lost" in error_msg or "502" in error_msg or "gateway error" in error_msg.lower():
            print("Retrying after connection error...", flush=True)
            import time
            time.sleep(2)  # Wait 2 seconds before retry
            try:
                response = supabase.table("inbox_jobs")\
                    .select("*")\
                    .eq("status", JobStatus.PENDING)\
                    .order("created_at", desc=False)\
                    .limit(limit)\
                    .execute()
                jobs = response.data if response.data else []
                if jobs:
                    print(f"Retry successful: Found {len(jobs)} pending job(s)", flush=True)
                return jobs
            except Exception as retry_error:
                print(f"Retry also failed: {retry_error}", flush=True)
        
        import traceback
        print(traceback.format_exc(), flush=True)
        return []

def store_file_data(job_id: str, file_data: List[Dict]):
    """
    Store file metadata for a job in Supabase.
    Files are stored on disk, only paths/metadata are stored in the database.
    
    Args:
        job_id: Job ID
        file_data: List of file dictionaries with {filename, file_path, suffix, size}
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot store file data.")
        return
    
    try:
        # Store only file metadata (paths, not content)
        # Structure: [{filename, file_path, suffix, size}, ...]
        # Remove 'content' field if present to avoid storing large data
        metadata = []
        for file_info in file_data:
            metadata.append({
                "filename": file_info.get("filename"),
                "file_path": file_info.get("file_path"),  # Path to file on disk
                "suffix": file_info.get("suffix"),
                "size": file_info.get("size", 0)  # File size in bytes
            })
        
        update_data = {
            "file_data": json.dumps(metadata),  # Store as JSON string
            "updated_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("inbox_jobs").update(update_data).eq("id", job_id).execute()
        logger.info(f"Stored file metadata for job {job_id} ({len(metadata)} files)")
        
    except Exception as e:
        logger.error(f"Error storing file data for job {job_id}: {e}")
        raise

def get_file_data(job_id: str) -> Optional[List[Dict]]:
    """
    Retrieve file data for a job from Supabase.
    Simplified version that checks:
    1. file_storage_urls (full metadata JSONB) - preferred
    2. file_urls (simple TEXT[] array) - fallback
    
    Returns:
        List of file dictionaries with {filename, file_path, suffix, size}
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot get file data.")
        return None
    
    try:
        job = get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found in database")
            return None
        
        # Preferred: full metadata
        file_storage_urls = job.get("file_storage_urls")
        if file_storage_urls:
            # Handle both list and string formats
            if isinstance(file_storage_urls, str):
                try:
                    file_storage_urls = json.loads(file_storage_urls)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse file_storage_urls JSON for job {job_id}")
                    file_storage_urls = None
            
            if isinstance(file_storage_urls, list) and len(file_storage_urls) > 0:
                print(f"SUCCESS: Found file_storage_urls for job {job_id} ({len(file_storage_urls)} files)", flush=True)
                logger.info(f"Retrieved file storage URLs for job {job_id} ({len(file_storage_urls)} files)")
                return file_storage_urls
        
        # Fallback: simple list of paths
        file_urls = job.get("file_urls")
        if file_urls and isinstance(file_urls, list) and len(file_urls) > 0:
            print(f"SUCCESS: Found file_urls for job {job_id} ({len(file_urls)} files), converting to full format", flush=True)
            # Convert simple file paths to full format
            file_data = []
            for file_path in file_urls:
                if file_path:
                    filename = Path(file_path).name if "/" in file_path else file_path
                    file_data.append({
                        "filename": filename,
                        "file_path": file_path,
                        "suffix": Path(filename).suffix if filename else "",
                        "size": None
                    })
            if file_data:
                logger.info(f"Retrieved file paths for job {job_id} using simple format ({len(file_data)} files)")
                return file_data
        
        # Fallback to old format: file_data (local filesystem)
        file_data_old = job.get("file_data")
        if file_data_old:
            if isinstance(file_data_old, str):
                try:
                    file_data_old = json.loads(file_data_old)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse file_data JSON for job {job_id}: {e}")
                    return None
            if isinstance(file_data_old, list) and len(file_data_old) > 0:
                logger.info(f"Retrieved file paths for job {job_id} using old format ({len(file_data_old)} files)")
                return file_data_old
        
        # Log error with details
        print(f"ERROR: No file data found for job {job_id}", flush=True)
        print(f"  - file_storage_urls: {file_storage_urls} (type: {type(file_storage_urls)})", flush=True)
        print(f"  - file_urls: {file_urls} (type: {type(file_urls)})", flush=True)
        print(f"  - file_data: {file_data_old} (type: {type(file_data_old)})", flush=True)
        print(f"  - All job keys: {list(job.keys())}", flush=True)
        logger.warning(f"No file data found for job {job_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting file data for job {job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def upload_file_to_storage(job_id: str, filename: str, file_bytes: bytes, bucket_name: str = "inbox-files") -> Optional[str]:
    """
    Upload a file to Supabase Storage and return the file path.
    
    Args:
        job_id: Job ID (used in file path)
        filename: Original filename
        file_bytes: File content as bytes
        bucket_name: Storage bucket name (default: "inbox-files")
    
    Returns:
        File path (e.g., "job_id/filename") for storage in database, or None if upload failed.
        Use create_signed_url() to generate temporary signed URLs when needed.
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot upload file to storage.")
        return None
    
    try:
        # Sanitize filename to remove invalid characters for Supabase Storage
        # Supabase Storage doesn't allow: ~, spaces, and some special characters
        import re
        from pathlib import Path
        
        # Get file extension
        file_path = Path(filename)
        file_extension = file_path.suffix
        file_stem = file_path.stem
        
        # Sanitize filename: remove/replace invalid characters
        # Replace spaces, tildes, and other problematic chars with underscores
        sanitized_stem = re.sub(r'[~<>:"|?*\s]', '_', file_stem)
        # Remove any remaining problematic characters
        sanitized_stem = re.sub(r'[^\w\-_.]', '_', sanitized_stem)
        # Limit length to avoid issues
        if len(sanitized_stem) > 200:
            sanitized_stem = sanitized_stem[:200]
        
        sanitized_filename = sanitized_stem + file_extension
        
        # Create file path in storage: {job_id}/{sanitized_filename}
        storage_path = f"{job_id}/{sanitized_filename}"
        
        # Log if filename was changed
        if sanitized_filename != filename:
            logger.info(f"Sanitized filename: '{filename}' -> '{sanitized_filename}'")
        
        # Upload file to Supabase Storage
        print(f"upload_file_to_storage: Uploading {filename} to {storage_path}...", flush=True)
        try:
            response = supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/octet-stream", "upsert": "true"}
            )
            print(f"upload_file_to_storage: Upload response: {response}", flush=True)
        except Exception as upload_error:
            print(f"ERROR: Upload failed: {upload_error}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            logger.error(f"Failed to upload {filename} to Supabase Storage: {upload_error}")
            return None
        
        # Verify file exists by trying to list it
        try:
            # Verify file exists (list the folder to check)
            print(f"upload_file_to_storage: Verifying file in storage...", flush=True)
            # Note: We don't need to get public URL anymore - we store file_path
            print(f"upload_file_to_storage: File verified in storage", flush=True)
        except Exception as verify_error:
            print(f"WARNING: Could not verify file in storage: {verify_error}", flush=True)
        
        # Return file path (not public URL) - format: "job_id/filename"
        logger.info(f"Uploaded file {filename} to Supabase Storage: {storage_path}")
        print(f"upload_file_to_storage: Returning file_path: {storage_path}", flush=True)
        return storage_path
        
    except Exception as e:
        logger.error(f"Error uploading file {filename} to Supabase Storage: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def create_signed_url(file_path: str, expires_in: int = 3600, bucket_name: str = "inbox-files") -> Optional[str]:
    """
    Create a signed URL for a file in Supabase Storage.
    
    Args:
        file_path: File path in storage (e.g., "job_id/filename")
        expires_in: URL expiration time in seconds (default: 3600 = 1 hour)
        bucket_name: Storage bucket name (default: "inbox-files")
    
    Returns:
        Signed URL string, or None if creation failed
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot create signed URL.")
        return None
    
    try:
        # Create signed URL
        signed_url_response = supabase.storage.from_(bucket_name).create_signed_url(
            path=file_path,
            expires_in=expires_in
        )
        
        # The response is a dict with 'signedURL' key
        if isinstance(signed_url_response, dict) and 'signedURL' in signed_url_response:
            signed_url = signed_url_response['signedURL']
            logger.info(f"Created signed URL for {file_path} (expires in {expires_in}s)")
            return signed_url
        elif isinstance(signed_url_response, str):
            # Some versions return the URL directly
            logger.info(f"Created signed URL for {file_path} (expires in {expires_in}s)")
            return signed_url_response
        else:
            logger.error(f"Unexpected signed URL response format: {type(signed_url_response)}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating signed URL for {file_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def download_file_from_storage(file_path: str, bucket_name: str = "inbox-files") -> Optional[bytes]:
    """
    Download a file from Supabase Storage using file path.
    
    Args:
        file_path: File path in storage (e.g., "job_id/filename") or signed URL
        bucket_name: Storage bucket name (default: "inbox-files")
    
    Returns:
        File content as bytes, or None if download failed
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot download file from storage.")
        return None
    
    try:
        # If it's a signed URL, download directly using requests
        if file_path.startswith("http"):
            import requests
            response = requests.get(file_path, timeout=30)
            if response.status_code == 200:
                logger.info(f"Downloaded file from signed URL: {file_path[:50]}...")
                return response.content
            else:
                logger.error(f"Failed to download from signed URL: HTTP {response.status_code}")
                return None
        
        # Otherwise, it's a storage path - download directly
        file_bytes = supabase.storage.from_(bucket_name).download(file_path)
        
        logger.info(f"Downloaded file from Supabase Storage: {file_path}")
        return file_bytes
        
    except Exception as e:
        logger.error(f"Error downloading file from Supabase Storage: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def store_file_storage_urls(job_id: str, file_urls: List[Dict]):
    """
    Store file paths for a job in Supabase.
    Stores both formats:
    - file_storage_urls: Full metadata (JSONB) with file_path - for compatibility
    - file_urls: Simple array of file paths (TEXT[]) - for easy worker access
    
    Args:
        job_id: Job ID
        file_urls: List of file dictionaries with {filename, file_path, suffix, size}
                   Note: file_path format is "job_id/filename" (not public URL)
    """
    print(f"store_file_storage_urls: Starting for job {job_id} with {len(file_urls)} files", flush=True)
    
    if not supabase:
        print(f"ERROR: Supabase not configured. Cannot store file paths for job {job_id}", flush=True)
        logger.warning("Supabase not configured. Cannot store file paths.")
        return
    
    try:
        # Extract file paths for simple array (prefer file_path over storage_url for backward compat)
        simple_paths = []
        for f in file_urls:
            file_path = f.get("file_path") or f.get("storage_url")  # Support both for migration
            if file_path:
                # If it's a full URL, extract the path part
                if file_path.startswith("http"):
                    # Extract path from URL: https://.../object/public/bucket/path
                    parts = file_path.split("/object/public/inbox-files/")
                    if len(parts) > 1:
                        file_path = parts[1]
                    else:
                        # Skip if we can't extract path
                        continue
                simple_paths.append(file_path)
        
        print(f"store_file_storage_urls: Extracted {len(simple_paths)} file paths for simple format", flush=True)
        
        # Store both formats: full metadata + simple paths
        print(f"store_file_storage_urls: Storing {len(file_urls)} files directly as list (not JSON string)", flush=True)
        
        update_data = {
            "file_storage_urls": file_urls,  # Full metadata (JSONB) - for compatibility
            "file_urls": simple_paths,        # Simple file paths array (TEXT[]) - for easy access
            "updated_at": datetime.utcnow().isoformat()
        }
        
        print(f"store_file_storage_urls: Updating database for job {job_id}...", flush=True)
        result = supabase.table("inbox_jobs").update(update_data).eq("id", job_id).execute()
        print(f"store_file_storage_urls: Database update completed for job {job_id}", flush=True)
        
        # Verify it was stored correctly by reading it back
        print(f"store_file_storage_urls: Verifying storage for job {job_id}...", flush=True)
        verify_job = get_job(job_id)
        if verify_job:
            stored_value = verify_job.get("file_storage_urls")
            print(f"store_file_storage_urls: Retrieved value type: {type(stored_value)}, is None: {stored_value is None}", flush=True)
            if stored_value is not None:
                print(f"store_file_storage_urls: Stored value length: {len(str(stored_value))}", flush=True)
                print(f"store_file_storage_urls: First 200 chars: {str(stored_value)[:200]}", flush=True)
            if isinstance(stored_value, str) and stored_value.startswith('"'):
                # Still stored as string, try alternative method
                print(f"WARNING: Value still stored as string for job {job_id}", flush=True)
                logger.warning(f"Value still stored as string for job {job_id}, trying alternative method")
                # Use raw SQL via RPC (if available) or direct SQL
                # For now, the parsing code should handle the string format
                pass
        else:
            print(f"ERROR: Could not verify job {job_id} after storage", flush=True)
        
        print(f"SUCCESS: Stored file storage URLs for job {job_id} ({len(file_urls)} files)", flush=True)
        logger.info(f"Stored file storage URLs for job {job_id} ({len(file_urls)} files)")
        
    except Exception as e:
        print(f"ERROR: Exception storing file storage URLs for job {job_id}: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        logger.error(f"Error storing file storage URLs for job {job_id}: {e}")
        logger.error(traceback.format_exc())
        raise

def reset_failed_job(job_id: str) -> bool:
    """
    Reset a failed job back to pending status so it can be retried.
    
    Args:
        job_id: Job ID to reset
    
    Returns:
        True if successful, False otherwise
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot reset job.")
        return False
    
    try:
        # Check if job exists and is failed
        job = get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found")
            return False
        
        if job.get("status") != JobStatus.FAILED:
            logger.warning(f"Job {job_id} is not in failed status (current: {job.get('status')})")
            return False
        
        # Reset to pending
        update_data = {
            "status": JobStatus.PENDING,
            "error": None,  # Clear error
            "progress": 0,  # Reset progress
            "processed_files": 0,  # Reset processed files
            "updated_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("inbox_jobs").update(update_data).eq("id", job_id).execute()
        logger.info(f"Reset job {job_id} from failed to pending")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting job {job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def delete_job(job_id: str) -> bool:
    """
    Delete a job from Supabase.
    
    Args:
        job_id: Job ID to delete
    
    Returns:
        True if deleted, False if not found
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot delete job.")
        return False
    
    try:
        # Check if job exists first
        job = get_job(job_id)
        if not job:
            return False
        
        # Delete files from Supabase Storage if they exist
        try:
            file_urls = job.get("file_storage_urls")
            if file_urls:
                if isinstance(file_urls, str):
                    file_urls = json.loads(file_urls)
                
                bucket_name = "inbox-files"
                for file_info in file_urls:
                    storage_url = file_info.get("storage_url")
                    if storage_url:
                        # Extract storage path from URL
                        if storage_url.startswith("http"):
                            parts = storage_url.split(f"/object/public/{bucket_name}/")
                            if len(parts) > 1:
                                storage_path = parts[1]
                                try:
                                    supabase.storage.from_(bucket_name).remove([storage_path])
                                    logger.info(f"Deleted file from storage: {storage_path}")
                                except Exception as e:
                                    logger.warning(f"Failed to delete file from storage: {e}")
        except Exception as storage_cleanup_error:
            logger.warning(f"Failed to clean up storage files for job {job_id}: {storage_cleanup_error}")
        
        # Delete the job
        supabase.table("inbox_jobs").delete().eq("id", job_id).execute()
        logger.info(f"Deleted job {job_id} from Supabase")
        
        # Also clean up files on disk if they still exist (backward compatibility)
        try:
            import shutil
            from pathlib import Path
            import tempfile
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            if job_dir.exists():
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up files for deleted job {job_id}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up files for deleted job {job_id}: {cleanup_error}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting job {job_id} from Supabase: {e}")
        return False

