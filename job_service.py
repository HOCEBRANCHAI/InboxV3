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
        
        return response.data if response.data else []
        
    except Exception as e:
        logger.error(f"Error getting pending jobs from Supabase: {e}")
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
    Retrieve file metadata for a job from Supabase.
    
    Returns:
        List of file dictionaries with {filename, file_path, suffix, size}
    """
    if not supabase:
        return None
    
    try:
        job = get_job(job_id)
        if job and job.get("file_data"):
            # Parse JSON string to get file metadata
            if isinstance(job["file_data"], str):
                file_data = json.loads(job["file_data"])
            else:
                file_data = job["file_data"]
            
            logger.info(f"Retrieved file metadata for job {job_id} ({len(file_data)} files)")
            return file_data
        return None
        
    except Exception as e:
        logger.error(f"Error getting file data for job {job_id}: {e}")
        return None

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
        
        # Delete the job
        supabase.table("inbox_jobs").delete().eq("id", job_id).execute()
        logger.info(f"Deleted job {job_id} from Supabase")
        
        # Also clean up files on disk if they still exist
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

