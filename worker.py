# worker.py
# Separate worker process that polls Supabase for pending jobs and processes them
import os
import sys
import time
import logging
import asyncio
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List

# Print before imports to catch import errors
print("Loading environment variables...", flush=True)
from dotenv import load_dotenv
load_dotenv()

print("Importing modules...", flush=True)
try:
    import textract_service
    print("✓ textract_service imported", flush=True)
except Exception as e:
    print(f"✗ ERROR importing textract_service: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    import openai_service
    print("✓ openai_service imported", flush=True)
except Exception as e:
    print(f"✗ ERROR importing openai_service: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from job_service import (
        get_pending_jobs, 
        update_job_status, 
        get_file_data,
        JobStatus,
        download_file_from_storage,
        create_signed_url
    )
    print("✓ job_service imported", flush=True)
except Exception as e:
    print(f"✗ ERROR importing job_service: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("All modules imported successfully", flush=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Use INFO so debug messages show up
    format='%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
# Also set job_service logger to INFO
logging.getLogger("job_service").setLevel(logging.INFO)

# Worker-specific configuration
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800"))  # 30 minutes default
PER_FILE_TIMEOUT = int(os.getenv("PER_FILE_TIMEOUT_SECONDS", "120"))  # 2 minutes default per file

# Thread pool executor for CPU-bound text extraction operations
from concurrent.futures import ThreadPoolExecutor
TEXT_EXTRACTION_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="text_extract")

# Request timeout handler
class RequestTimeoutHandler:
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self.start_time = None
    
    def start(self):
        self.start_time = time.time()
    
    def check_timeout(self):
        if self.start_time and (time.time() - self.start_time) > self.timeout_seconds:
            raise Exception("Request timeout exceeded")
    
    def get_remaining_time(self):
        if self.start_time:
            return max(0, self.timeout_seconds - (time.time() - self.start_time))
        return self.timeout_seconds

def is_transient_error(error: Exception) -> bool:
    """Check if an error is a transient infrastructure error that should be retried"""
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Supabase connection errors
    if "502" in error_str or "gateway error" in error_str or "network connection lost" in error_str:
        return True
    if "connection" in error_str and ("lost" in error_str or "timeout" in error_str or "reset" in error_str):
        return True
    if error_type in ["ConnectionError", "TimeoutError", "APIError"]:
        # Check if it's a 502/503/504 error
        if hasattr(error, "code"):
            if error.code in [502, 503, 504]:
                return True
        if "502" in error_str or "503" in error_str or "504" in error_str:
            return True
    
    return False

async def process_classify_job(job: Dict, retry_count: int = 0, max_retries: int = 3):
    """Process a classification job with retry logic for transient errors"""
    job_id = job["id"]
    endpoint_type = job.get("endpoint_type", "classify")
    
    try:
        print(f"Processing job {job_id} (type: {endpoint_type}, retry: {retry_count}/{max_retries})", flush=True)
        logger.info(f"Processing job {job_id} (type: {endpoint_type}, retry: {retry_count}/{max_retries})")
        update_job_status(job_id, JobStatus.PROCESSING, progress=0)
        
        # Get file data from job with retry logic
        # Wait longer for files to be uploaded (uploads happen in background thread pool)
        print(f"Getting file data for job {job_id}...", flush=True)
        file_data = None
        max_file_data_retries = 10  # Wait up to 20 seconds for files to be uploaded
        for attempt in range(max_file_data_retries + 1):
            try:
                # IMPORTANT: Always call get_file_data() which fetches fresh data from database
                print(f"  Attempt {attempt + 1}/{max_file_data_retries + 1}: Calling get_file_data({job_id})...", flush=True)
                file_data = get_file_data(job_id)
                print(f"  get_file_data returned: type={type(file_data)}, value={file_data}", flush=True)
                if file_data and len(file_data) > 0:
                    print(f"SUCCESS: Got file data on attempt {attempt + 1}, {len(file_data)} files", flush=True)
                    print(f"  First file: {file_data[0]}", flush=True)
                    break
                # If no data but no exception, wait a bit (files might still be uploading)
                if attempt < max_file_data_retries:
                    wait_time = 2  # Wait 2 seconds between attempts
                    print(f"  No file data yet (got {file_data}), waiting {wait_time} seconds (attempt {attempt + 1}/{max_file_data_retries + 1})...", flush=True)
                    await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"  EXCEPTION in get_file_data: {type(e).__name__}: {e}", flush=True)
                import traceback
                print(f"  Traceback: {traceback.format_exc()}", flush=True)
                if is_transient_error(e) and attempt < max_file_data_retries:
                    wait_time = 2  # Wait 2 seconds for transient errors too
                    print(f"  Transient error getting file data (attempt {attempt + 1}/{max_file_data_retries + 1}): {e}", flush=True)
                    print(f"  Retrying in {wait_time} seconds...", flush=True)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        
        print(f"File data result type: {type(file_data)}, length: {len(file_data) if file_data else 0}", flush=True)
        if file_data:
            print(f"SUCCESS: Got file data, first file: {file_data[0].get('filename') if file_data else 'None'}", flush=True)
        if not file_data:
            print(f"ERROR: No file data found for job {job_id} after {max_file_data_retries + 1} attempts", flush=True)
            # Get the job again to see what's actually in the database
            from job_service import get_job
            job_check = get_job(job_id)
            if job_check:
                print(f"  Job exists in database. Keys: {list(job_check.keys())}", flush=True)
                print(f"  file_storage_urls: {job_check.get('file_storage_urls')}", flush=True)
                print(f"  file_urls: {job_check.get('file_urls')}", flush=True)
                print(f"  file_data: {job_check.get('file_data')}", flush=True)
            raise ValueError("No file data found for job")
        
        print(f"Found {len(file_data)} files for job {job_id}", flush=True)
        
        timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
        timeout_handler.start()
        
        total_files = len(file_data)
        update_job_status(job_id, JobStatus.PROCESSING, progress=0, processed_files=0)
        
        results = []
        inbox_count = 0
        archive_count = 0
        
        # Process files in parallel
        if len(file_data) <= 10:
            max_concurrent_api_calls = 5
        elif len(file_data) <= 20:
            max_concurrent_api_calls = 8
        else:
            max_concurrent_api_calls = 12
        
        semaphore = asyncio.Semaphore(max_concurrent_api_calls)
        
        async def process_file(file_info: Dict):
            """Process a single file"""
            file_bytes = None
            tmp_path = None
            
            try:
                # PRIORITY 1: Check for file_path (storage path format: "job_id/filename")
                if "file_path" in file_info:
                    storage_file_path = file_info.get("file_path")
                    if not storage_file_path:
                        raise ValueError(f"File path not found for {file_info.get('filename')}")
                    
                    # Check if it's a local filesystem path (backward compatibility)
                    if os.path.exists(storage_file_path):
                        # Local filesystem path - read directly
                        file_path = storage_file_path
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                    else:
                        # Storage path (e.g., "job_id/filename") - generate signed URL and download
                        print(f"Generating signed URL for file_path: {storage_file_path}", flush=True)
                        signed_url = create_signed_url(storage_file_path, expires_in=3600)
                        if not signed_url:
                            raise ValueError(f"Failed to create signed URL for: {storage_file_path}")
                        
                        print(f"Downloading file using signed URL...", flush=True)
                        # Download file from Supabase Storage using signed URL
                        file_bytes = download_file_from_storage(signed_url)
                        if not file_bytes:
                            raise ValueError(f"Failed to download file from storage: {storage_file_path}")
                        
                        # Save to temporary file for processing
                        import tempfile
                        filename = file_info.get("filename", "file")
                        suffix = file_info.get("suffix", "")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(file_bytes)
                            tmp_path = tmp.name
                        
                        file_path = tmp_path
                
                # PRIORITY 2: Check for storage_url (legacy format - backward compatibility)
                elif "storage_url" in file_info:
                    storage_url = file_info.get("storage_url")
                    if not storage_url:
                        raise ValueError(f"Storage URL not found for {file_info.get('filename')}")
                    
                    print(f"Downloading file using storage_url (legacy format)...", flush=True)
                    # Download file from Supabase Storage
                    file_bytes = download_file_from_storage(storage_url)
                    if not file_bytes:
                        raise ValueError(f"Failed to download file from storage: {storage_url}")
                    
                    # Save to temporary file for processing
                    import tempfile
                    filename = file_info.get("filename", "file")
                    suffix = file_info.get("suffix", "")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name
                    
                    file_path = tmp_path
                else:
                    raise ValueError(f"No file source found for {file_info.get('filename')}. Missing 'file_path' or 'storage_url'.")
                
                # Extract text
                extracted_text = await asyncio.get_event_loop().run_in_executor(
                    TEXT_EXTRACTION_EXECUTOR,
                    textract_service.extract_text_from_upload,
                    file_path,
                    file_bytes
                )
                
                if not extracted_text or not extracted_text.strip():
                    return {
                        "filename": file_info["filename"],
                        "routing": "ARCHIVE",
                        "channel": "ARCHIVE",
                        "status": "failed",
                        "error": "No text extracted"
                    }
                
                # Route document
                async with semaphore:
                    routing_result = await asyncio.wait_for(
                        openai_service.classify_document(extracted_text),
                        timeout=PER_FILE_TIMEOUT
                    )
                
                return {
                    "filename": file_info["filename"],
                    "routing": routing_result.get("routing", "ARCHIVE"),
                    "channel": routing_result.get("channel"),
                    "topic_type": routing_result.get("topic_type"),
                    "topic_title": routing_result.get("topic_title"),
                    "urgency": routing_result.get("urgency"),
                    "deadline": routing_result.get("deadline"),
                    "authority": routing_result.get("authority"),
                    "reasoning": routing_result.get("reasoning"),
                    "status": "success"
                }
            except Exception as e:
                logger.error(f"Error processing {file_info['filename']}: {e}")
                return {
                    "filename": file_info["filename"],
                    "routing": "ARCHIVE",
                    "channel": "ARCHIVE",
                    "status": "error",
                    "error": str(e)
                }
            finally:
                # Clean up temporary file if created from storage
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up temp file {tmp_path}: {cleanup_error}")
        
        # Process all files in parallel
        tasks = [process_file(file_info) for file_info in file_data]
        routing_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(routing_results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing file: {result}")
                results.append({
                    "filename": file_data[i]["filename"],
                    "routing": "ARCHIVE",
                    "channel": "ARCHIVE",
                    "status": "error",
                    "error": str(result)
                })
            else:
                results.append(result)
                if result.get("routing") == "INBOX":
                    inbox_count += 1
                elif result.get("routing") == "ARCHIVE":
                    archive_count += 1
            
            # Update progress
            processed = len(results)
            progress = int((processed / total_files) * 100)
            update_job_status(job_id, JobStatus.PROCESSING, progress=progress, processed_files=processed)
        
        # Build final result
        successful = sum(1 for r in results if r.get("status") == "success")
        failed = len(results) - successful
        
        final_result = {
            "total_files": len(results),
            "successful": successful,
            "failed": failed,
            "inbox_count": inbox_count,
            "archive_count": archive_count,
            "results": results,
            "processing_time": time.time() - timeout_handler.start_time
        }
        
        update_job_status(job_id, JobStatus.COMPLETED, result=final_result, progress=100)
        logger.info(f"Job {job_id} completed successfully")
        
        # Clean up files after successful processing
        try:
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up files for job {job_id}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up files for job {job_id}: {cleanup_error}")
        
    except Exception as e:
        error_msg = f"Job processing failed: {str(e)}"
        print(f"EXCEPTION in process_classify_job for job {job_id}: {error_msg}", flush=True)
        print(f"Exception type: {type(e).__name__}", flush=True)
        print(f"Full traceback:", flush=True)
        print(traceback.format_exc(), flush=True)
        logger.error(f"Job {job_id} failed: {error_msg}")
        logger.error(traceback.format_exc())
        
        # Check if this is a transient error that should be retried
        if is_transient_error(e) and retry_count < max_retries:
            wait_time = 2 ** retry_count  # Exponential backoff
            print(f"TRANSIENT ERROR detected - will retry job {job_id} in {wait_time} seconds (retry {retry_count + 1}/{max_retries})", flush=True)
            # Reset job to pending for retry
            update_job_status(job_id, JobStatus.PENDING, error=None)
            # Wait before retry
            await asyncio.sleep(wait_time)
            # Retry the job
            return await process_classify_job(job, retry_count=retry_count + 1, max_retries=max_retries)
        else:
            # Permanent failure - mark as failed
            update_job_status(job_id, JobStatus.FAILED, error=error_msg)
        
        # Clean up files even on failure
        try:
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up files for failed job {job_id}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up files for failed job {job_id}: {cleanup_error}")

async def process_analyze_job(job: Dict):
    """Process an analysis job (analyze-multiple-async)"""
    job_id = job["id"]
    
    try:
        logger.info(f"Processing analyze job {job_id}")
        update_job_status(job_id, JobStatus.PROCESSING, progress=0)
        
        # Get file data from job
        file_data = get_file_data(job_id)
        if not file_data:
            raise ValueError("No file data found for job")
        
        timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
        timeout_handler.start()
        
        total_files = len(file_data)
        update_job_status(job_id, JobStatus.PROCESSING, progress=0, processed_files=0)
        
        results = []
        
        # Process files in parallel
        if len(file_data) <= 10:
            max_concurrent_api_calls = 5
        elif len(file_data) <= 20:
            max_concurrent_api_calls = 8
        else:
            max_concurrent_api_calls = 12
        
        semaphore = asyncio.Semaphore(max_concurrent_api_calls)
        
        async def process_file(file_info: Dict):
            """Process a single file for analysis"""
            file_bytes = None
            tmp_path = None
            
            try:
                # PRIORITY 1: Check for file_path (storage path format: "job_id/filename")
                if "file_path" in file_info:
                    storage_file_path = file_info.get("file_path")
                    if not storage_file_path:
                        raise ValueError(f"File path not found for {file_info.get('filename')}")
                    
                    # Check if it's a local filesystem path (backward compatibility)
                    if os.path.exists(storage_file_path):
                        # Local filesystem path - read directly
                        file_path = storage_file_path
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                    else:
                        # Storage path (e.g., "job_id/filename") - generate signed URL and download
                        print(f"Generating signed URL for file_path: {storage_file_path}", flush=True)
                        signed_url = create_signed_url(storage_file_path, expires_in=3600)
                        if not signed_url:
                            raise ValueError(f"Failed to create signed URL for: {storage_file_path}")
                        
                        print(f"Downloading file using signed URL...", flush=True)
                        # Download file from Supabase Storage using signed URL
                        file_bytes = download_file_from_storage(signed_url)
                        if not file_bytes:
                            raise ValueError(f"Failed to download file from storage: {storage_file_path}")
                        
                        # Save to temporary file for processing
                        import tempfile
                        filename = file_info.get("filename", "file")
                        suffix = file_info.get("suffix", "")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(file_bytes)
                            tmp_path = tmp.name
                        
                        file_path = tmp_path
                
                # PRIORITY 2: Check for storage_url (legacy format - backward compatibility)
                elif "storage_url" in file_info:
                    storage_url = file_info.get("storage_url")
                    if not storage_url:
                        raise ValueError(f"Storage URL not found for {file_info.get('filename')}")
                    
                    print(f"Downloading file using storage_url (legacy format)...", flush=True)
                    # Download file from Supabase Storage
                    file_bytes = download_file_from_storage(storage_url)
                    if not file_bytes:
                        raise ValueError(f"Failed to download file from storage: {storage_url}")
                    
                    # Save to temporary file for processing
                    import tempfile
                    filename = file_info.get("filename", "file")
                    suffix = file_info.get("suffix", "")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name
                    
                    file_path = tmp_path
                else:
                    raise ValueError(f"No file source found for {file_info.get('filename')}. Missing 'file_path' or 'storage_url'.")
                
                # Extract text
                extracted_text = await asyncio.get_event_loop().run_in_executor(
                    TEXT_EXTRACTION_EXECUTOR,
                    textract_service.extract_text_from_upload,
                    file_path,
                    file_bytes
                )
                
                if not extracted_text or not extracted_text.strip():
                    return {
                        "filename": file_info["filename"],
                        "status": "failed",
                        "error": "No text extracted"
                    }
                
                # Analyze document (no routing, direct analysis)
                async with semaphore:
                    analysis_result = await asyncio.wait_for(
                        openai_service.analyze_document(
                            extracted_text,
                            channel=None,
                            topic_type=None,
                            topic_title=None
                        ),
                        timeout=PER_FILE_TIMEOUT
                    )
                
                return {
                    "filename": file_info["filename"],
                    "analysis": analysis_result,
                    "status": "success",
                    "extracted_text": extracted_text[:1000]  # First 1000 chars
                }
            except Exception as e:
                logger.error(f"Error processing {file_info['filename']}: {e}")
                return {
                    "filename": file_info["filename"],
                    "status": "error",
                    "error": str(e)
                }
            finally:
                # Clean up temporary file if created from storage
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up temp file {tmp_path}: {cleanup_error}")
        
        # Process all files in parallel
        tasks = [process_file(file_info) for file_info in file_data]
        analysis_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for i, result in enumerate(analysis_results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing file: {result}")
                results.append({
                    "filename": file_data[i]["filename"],
                    "status": "error",
                    "error": str(result)
                })
            else:
                results.append(result)
            
            # Update progress
            processed = len(results)
            progress = int((processed / total_files) * 100)
            update_job_status(job_id, JobStatus.PROCESSING, progress=progress, processed_files=processed)
        
        # Build final result
        successful = sum(1 for r in results if r.get("status") == "success")
        failed = len(results) - successful
        
        final_result = {
            "total_files": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
            "processing_time": time.time() - timeout_handler.start_time
        }
        
        update_job_status(job_id, JobStatus.COMPLETED, result=final_result, progress=100)
        logger.info(f"Analyze job {job_id} completed successfully")
        
        # Clean up files after successful processing
        try:
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up files for job {job_id}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up files for job {job_id}: {cleanup_error}")
        
    except Exception as e:
        error_msg = f"Job processing failed: {str(e)}"
        print(f"EXCEPTION in process_analyze_job for job {job_id}: {error_msg}", flush=True)
        print(f"Exception type: {type(e).__name__}", flush=True)
        print(f"Full traceback:", flush=True)
        print(traceback.format_exc(), flush=True)
        logger.error(f"Analyze job {job_id} failed: {error_msg}")
        logger.error(traceback.format_exc())
        
        # Check if this is a transient error that should be retried
        if is_transient_error(e) and retry_count < max_retries:
            wait_time = 2 ** retry_count
            print(f"TRANSIENT ERROR detected - will retry job {job_id} in {wait_time} seconds (retry {retry_count + 1}/{max_retries})", flush=True)
            update_job_status(job_id, JobStatus.PENDING, error=None)
            await asyncio.sleep(wait_time)
            return await process_analyze_job(job, retry_count=retry_count + 1, max_retries=max_retries)
        else:
            update_job_status(job_id, JobStatus.FAILED, error=error_msg)
        
        # Clean up files even on failure
        try:
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up files for failed job {job_id}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up files for failed job {job_id}: {cleanup_error}")

async def worker_loop():
    """Main worker loop that polls for pending jobs"""
    # Print to stdout for Render visibility
    print("=" * 80, flush=True)
    print("Worker Process Starting", flush=True)
    print(f"Process ID: {os.getpid()}", flush=True)
    print("=" * 80, flush=True)
    
    logger.info("=" * 80)
    logger.info("Worker Process Starting")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info("=" * 80)
    
    poll_interval = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5"))  # Poll every 5 seconds
    print(f"Poll interval: {poll_interval} seconds", flush=True)
    
    while True:
        try:
            # Get pending jobs
            pending_jobs = get_pending_jobs(limit=10)
            
            if pending_jobs:
                print(f"=" * 80, flush=True)
                print(f"FOUND {len(pending_jobs)} PENDING JOB(S) - STARTING PROCESSING", flush=True)
                print(f"=" * 80, flush=True)
                logger.info(f"Found {len(pending_jobs)} pending job(s)")
                
                # Process jobs concurrently (up to 3 at a time)
                # Dispatch based on endpoint_type
                tasks = []
                for job in pending_jobs[:3]:
                    endpoint_type = job.get("endpoint_type", "classify")
                    job_id = job.get("id", "unknown")
                    print(f"DISPATCHING job {job_id} (type: {endpoint_type})", flush=True)
                    print(f"  Job total_files: {job.get('total_files')}", flush=True)
                    print(f"  Job created_at: {job.get('created_at')}", flush=True)
                    if endpoint_type == "analyze":
                        tasks.append(process_analyze_job(job))
                    else:
                        tasks.append(process_classify_job(job))
                
                print(f"PROCESSING {len(tasks)} job(s) concurrently...", flush=True)
                print(f"Waiting for tasks to complete...", flush=True)
                results = await asyncio.gather(*tasks, return_exceptions=True)
                print(f"Tasks completed. Checking results...", flush=True)
                
                # Check for exceptions in results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        job_id = pending_jobs[i].get("id", "unknown") if i < len(pending_jobs) else "unknown"
                        print(f"=" * 80, flush=True)
                        print(f"EXCEPTION CAUGHT from asyncio.gather for job {job_id}", flush=True)
                        print(f"Exception: {result}", flush=True)
                        print(f"Exception type: {type(result).__name__}", flush=True)
                        import traceback
                        # Get traceback from exception if available
                        if hasattr(result, '__traceback__'):
                            print(f"Traceback:", flush=True)
                            print(''.join(traceback.format_exception(type(result), result, result.__traceback__)), flush=True)
                        else:
                            print(f"Traceback: {traceback.format_exc()}", flush=True)
                        print(f"=" * 80, flush=True)
                        logger.error(f"Exception processing job {job_id}: {result}")
                        logger.error(traceback.format_exc())
            else:
                # No jobs, wait before next poll
                print(f"No pending jobs, waiting {poll_interval} seconds...", flush=True)
                await asyncio.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    try:
        # Print to stdout immediately so Render shows it
        print("=" * 80, flush=True)
        print("Starting worker.py...", flush=True)
        print(f"Python version: {sys.version}", flush=True)
        print(f"Working directory: {os.getcwd()}", flush=True)
        print("=" * 80, flush=True)
        
        # Check critical environment variables
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        print(f"SUPABASE_URL: {'SET' if supabase_url else 'NOT SET'}", flush=True)
        print(f"SUPABASE_SERVICE_ROLE_KEY: {'SET' if supabase_key else 'NOT SET'}", flush=True)
        print(f"OPENAI_API_KEY: {'SET' if openai_key else 'NOT SET'}", flush=True)
        print("=" * 80, flush=True)
        
        # Run worker loop
        print("Starting async worker loop...", flush=True)
        try:
            asyncio.run(worker_loop())
        except Exception as loop_error:
            print(f"ERROR in async loop: {loop_error}", flush=True)
            print(traceback.format_exc(), flush=True)
            raise
    except KeyboardInterrupt:
        print("\nWorker interrupted by user", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: Worker failed to start: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        sys.exit(1)

