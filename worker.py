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
from dotenv import load_dotenv
import textract_service
import openai_service
from job_service import (
    get_pending_jobs, 
    update_job_status, 
    get_file_data,
    JobStatus,
    download_file_from_storage
)

load_dotenv()

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

async def process_classify_job(job: Dict):
    """Process a classification job"""
    job_id = job["id"]
    endpoint_type = job.get("endpoint_type", "classify")
    
    try:
        logger.info(f"Processing job {job_id} (type: {endpoint_type})")
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
                # Check if file is in Supabase Storage (new way)
                if "storage_url" in file_info:
                    storage_url = file_info.get("storage_url")
                    if not storage_url:
                        raise ValueError(f"Storage URL not found for {file_info.get('filename')}")
                    
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
                
                # Fallback to local filesystem (old way, backward compatibility)
                elif "file_path" in file_info:
                    file_path = file_info.get("file_path")
                    if not file_path or not os.path.exists(file_path):
                        raise ValueError(f"File not found: {file_path}")
                    
                    # Read file from disk
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                else:
                    raise ValueError(f"No file source found for {file_info.get('filename')}. Missing 'storage_url' or 'file_path'.")
                
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
        logger.error(f"Job {job_id} failed: {error_msg}")
        logger.error(traceback.format_exc())
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
                # Check if file is in Supabase Storage (new way)
                if "storage_url" in file_info:
                    storage_url = file_info.get("storage_url")
                    if not storage_url:
                        raise ValueError(f"Storage URL not found for {file_info.get('filename')}")
                    
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
                
                # Fallback to local filesystem (old way, backward compatibility)
                elif "file_path" in file_info:
                    file_path = file_info.get("file_path")
                    if not file_path or not os.path.exists(file_path):
                        raise ValueError(f"File not found: {file_path}")
                    
                    # Read file from disk
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                else:
                    raise ValueError(f"No file source found for {file_info.get('filename')}. Missing 'storage_url' or 'file_path'.")
                
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
        logger.error(f"Analyze job {job_id} failed: {error_msg}")
        logger.error(traceback.format_exc())
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
    logger.info("=" * 80)
    logger.info("Worker Process Starting")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info("=" * 80)
    
    poll_interval = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5"))  # Poll every 5 seconds
    
    while True:
        try:
            # Get pending jobs
            pending_jobs = get_pending_jobs(limit=10)
            
            if pending_jobs:
                logger.info(f"Found {len(pending_jobs)} pending job(s)")
                
                # Process jobs concurrently (up to 3 at a time)
                # Dispatch based on endpoint_type
                tasks = []
                for job in pending_jobs[:3]:
                    endpoint_type = job.get("endpoint_type", "classify")
                    if endpoint_type == "analyze":
                        tasks.append(process_analyze_job(job))
                    else:
                        tasks.append(process_classify_job(job))
                
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # No jobs, wait before next poll
                await asyncio.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    asyncio.run(worker_loop())

