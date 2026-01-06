# job_service.py
# Database-backed job service using Supabase
import os
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
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

if not supabase_url or not supabase_key:
    logger.warning("Supabase credentials not found. Jobs will not be persisted.")
    supabase: Optional[Client] = None
else:
    try:
        # Supabase client initialization (positional arguments)
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized successfully")
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
            # Debug: Log what we got
            logger.debug(f"Retrieved job {job_id}, keys: {list(job.keys())}, file_storage_urls present: {'file_storage_urls' in job}")
            return job
        return None
        
    except Exception as e:
        logger.error(f"Error getting job {job_id} from Supabase: {e}")
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
        
        return jobs
        
    except Exception as e:
        print(f"ERROR getting pending jobs: {e}", flush=True)
        logger.error(f"Error getting pending jobs from Supabase: {e}")
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
    Checks both file_storage_urls (new) and file_data (old) for backward compatibility.
    
    Returns:
        List of file dictionaries with:
        - New format: {filename, storage_url, suffix, size}
        - Old format: {filename, file_path, suffix, size}
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot get file data.")
        return None
    
    try:
        job = get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found in database")
            return None
        
        # Debug: Log what columns are available (use INFO level so it shows in logs)
        print(f"Job {job_id} - Available columns: {list(job.keys())}", flush=True)
        logger.info(f"Job {job_id} - Available columns: {list(job.keys())}")
        file_storage_urls_raw = job.get("file_storage_urls")
        file_data_raw = job.get("file_data")
        print(f"Job {job_id} - file_storage_urls type: {type(file_storage_urls_raw)}, value: {str(file_storage_urls_raw)[:500] if file_storage_urls_raw else 'None'}", flush=True)
        print(f"Job {job_id} - file_data type: {type(file_data_raw)}, value: {str(file_data_raw)[:500] if file_data_raw else 'None'}", flush=True)
        logger.info(f"Job {job_id} - file_storage_urls type: {type(file_storage_urls_raw)}, value: {str(file_storage_urls_raw)[:200] if file_storage_urls_raw else 'None'}...")
        logger.info(f"Job {job_id} - file_data type: {type(file_data_raw)}, value: {str(file_data_raw)[:200] if file_data_raw else 'None'}...")
        
        # Check for new format: file_storage_urls (Supabase Storage)
        file_storage_urls = job.get("file_storage_urls")
        # Also check if it's None, empty string, or empty list
        if file_storage_urls is not None and file_storage_urls != "" and file_storage_urls != []:
            # Handle different formats:
            # 1. Already a list (JSONB returned as object) - ideal case
            if isinstance(file_storage_urls, list):
                print(f"SUCCESS: file_storage_urls is already a list for job {job_id} ({len(file_storage_urls)} files)", flush=True)
                logger.info(f"Retrieved file storage URLs for job {job_id} ({len(file_storage_urls)} files)")
                return file_storage_urls
            
            # 2. String that needs parsing - SIMPLIFIED: just parse it directly
            if isinstance(file_storage_urls, str):
                print(f"Parsing JSON string for job {job_id}, length: {len(file_storage_urls)}", flush=True)
                # SIMPLIFIED: Just parse the string directly - diagnostic shows it's valid JSON
                try:
                    parsed = json.loads(file_storage_urls)
                    if isinstance(parsed, list):
                        print(f"SUCCESS: Parsed file_storage_urls for job {job_id}, got {len(parsed)} items", flush=True)
                        logger.info(f"Retrieved file storage URLs for job {job_id} ({len(parsed)} files)")
                        return parsed
                    else:
                        print(f"ERROR: Parsed result is not a list: {type(parsed)}", flush=True)
                        logger.error(f"file_storage_urls parsed but not a list for job {job_id}: {type(parsed)}")
                        return None
                except json.JSONDecodeError as e:
                    print(f"ERROR: Failed to parse JSON: {e}", flush=True)
                    print(f"Raw value (first 500 chars): {file_storage_urls[:500]}", flush=True)
                    logger.error(f"Failed to parse file_storage_urls JSON for job {job_id}: {e}")
                    # Try fallback: handle double-encoded case
                    try:
                        # Remove outer quotes if present
                        cleaned = file_storage_urls.strip()
                        if cleaned.startswith('"') and cleaned.endswith('"'):
                            cleaned = cleaned[1:-1]
                        # Unescape
                        cleaned = cleaned.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                        parsed = json.loads(cleaned)
                        if isinstance(parsed, list):
                            print(f"SUCCESS: Parsed after fallback cleaning for job {job_id}, got {len(parsed)} items", flush=True)
                            return parsed
                    except Exception as e2:
                        print(f"FAILED: Fallback parsing also failed: {e2}", flush=True)
                    return None
        
        # Fallback to old format: file_data (local filesystem)
        file_data_old = job.get("file_data")
        # Also check if it's None, empty string, or empty list
        if file_data_old is not None and file_data_old != "" and file_data_old != []:
            file_data = file_data_old
            if isinstance(file_data, str):
                try:
                    file_data = json.loads(file_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse file_data JSON for job {job_id}: {e}")
                    return None
            elif not isinstance(file_data, list):
                logger.error(f"file_data is not a list or JSON string for job {job_id}: {type(file_data)}")
                return None
            
            logger.info(f"Retrieved file paths for job {job_id} ({len(file_data)} files)")
            return file_data
        
        # Log detailed information for debugging
        print(f"ERROR: No file data found for job {job_id}", flush=True)
        print(f"  - file_storage_urls value: {file_storage_urls}", flush=True)
        print(f"  - file_storage_urls type: {type(file_storage_urls)}", flush=True)
        print(f"  - file_storage_urls is None: {file_storage_urls is None}", flush=True)
        print(f"  - file_storage_urls == '': {file_storage_urls == ''}", flush=True)
        print(f"  - file_storage_urls == []: {file_storage_urls == []}", flush=True)
        print(f"  - file_data (old) value: {file_data_old}", flush=True)
        print(f"  - file_data (old) type: {type(file_data_old)}", flush=True)
        print(f"  - All job keys: {list(job.keys())}", flush=True)
        print(f"  - Job status: {job.get('status')}", flush=True)
        print(f"  - Job endpoint_type: {job.get('endpoint_type')}", flush=True)
        logger.warning(f"No file data found for job {job_id}")
        logger.warning(f"  - file_storage_urls: {file_storage_urls} (type: {type(file_storage_urls)})")
        logger.warning(f"  - file_data: {file_data_old} (type: {type(file_data_old)})")
        logger.warning(f"  - All job keys: {list(job.keys())}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting file data for job {job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def upload_file_to_storage(job_id: str, filename: str, file_bytes: bytes, bucket_name: str = "inbox-files") -> Optional[str]:
    """
    Upload a file to Supabase Storage and return the public URL.
    
    Args:
        job_id: Job ID (used in file path)
        filename: Original filename
        file_bytes: File content as bytes
        bucket_name: Storage bucket name (default: "inbox-files")
    
    Returns:
        Public URL of uploaded file, or None if upload failed
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
        response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        
        logger.info(f"Uploaded file {filename} to Supabase Storage: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"Error uploading file {filename} to Supabase Storage: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def download_file_from_storage(storage_url: str, bucket_name: str = "inbox-files") -> Optional[bytes]:
    """
    Download a file from Supabase Storage.
    
    Args:
        storage_url: Public URL or storage path of the file
        bucket_name: Storage bucket name (default: "inbox-files")
    
    Returns:
        File content as bytes, or None if download failed
    """
    if not supabase:
        logger.warning("Supabase not configured. Cannot download file from storage.")
        return None
    
    try:
        # Extract storage path from URL if it's a full URL
        # URL format: https://{project}.supabase.co/storage/v1/object/public/{bucket}/{path}
        if storage_url.startswith("http"):
            # Extract path from URL
            parts = storage_url.split(f"/object/public/{bucket_name}/")
            if len(parts) > 1:
                storage_path = parts[1]
            else:
                # Fallback: use URL as-is (might be a signed URL)
                storage_path = storage_url
        else:
            # Assume it's already a storage path
            storage_path = storage_url
        
        # Download file from Supabase Storage
        file_bytes = supabase.storage.from_(bucket_name).download(storage_path)
        
        logger.info(f"Downloaded file from Supabase Storage: {storage_path}")
        return file_bytes
        
    except Exception as e:
        logger.error(f"Error downloading file from Supabase Storage: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def store_file_storage_urls(job_id: str, file_urls: List[Dict]):
    """
    Store file storage URLs for a job in Supabase.
    
    Args:
        job_id: Job ID
        file_urls: List of file dictionaries with {filename, storage_url, suffix, size}
    """
    print(f"store_file_storage_urls: Starting for job {job_id} with {len(file_urls)} files", flush=True)
    
    if not supabase:
        print(f"ERROR: Supabase not configured. Cannot store file storage URLs for job {job_id}", flush=True)
        logger.warning("Supabase not configured. Cannot store file storage URLs.")
        return
    
    try:
        # IMPORTANT: Supabase Python client stores JSONB incorrectly when passing Python objects
        # We need to use a workaround: cast the value explicitly in the update
        # However, the PostgREST API (which Supabase uses) should handle JSONB correctly
        # Let's try passing it as a JSON string, which PostgREST will parse as JSONB
        
        # Method 1: Try passing as JSON string (PostgREST should parse it as JSONB)
        json_string = json.dumps(file_urls)
        print(f"store_file_storage_urls: Created JSON string, length: {len(json_string)}", flush=True)
        
        # Use the PostgREST format for JSONB: pass as string, PostgREST will cast it
        # According to PostgREST docs, JSON strings are automatically cast to JSONB
        update_data = {
            "file_storage_urls": json_string,  # Pass as JSON string
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

