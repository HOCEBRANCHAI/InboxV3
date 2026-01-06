import os
import tempfile
import logging
import asyncio
import time
import signal
import sys
import traceback
import psutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import textract_service
import openai_service

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Document Analysis API")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Enhanced logging configuration with detailed formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 80)
logger.info("Application Starting")
logger.info(f"Python version: {sys.version}")
logger.info(f"Process ID: {os.getpid()}")
logger.info(f"Max file size: {os.getenv('MAX_FILE_SIZE_MB', '100')} MB")
logger.info(f"Max total size: {os.getenv('MAX_TOTAL_SIZE_MB', '2000')} MB")
logger.info(f"Request timeout: {os.getenv('REQUEST_TIMEOUT_SECONDS', '1800')} seconds")
logger.info(f"Per-file timeout: {os.getenv('PER_FILE_TIMEOUT_SECONDS', '120')} seconds")
logger.info("=" * 80)

# File size limits (in bytes) - configurable via environment variables
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024  # Default 100MB per file
MAX_TOTAL_SIZE = int(os.getenv("MAX_TOTAL_SIZE_MB", "2000")) * 1024 * 1024  # Default 2GB total for 30 files
MAX_FILES_PER_REQUEST = int(os.getenv("MAX_FILES_PER_REQUEST", "30"))  # Default 30 files per request

# Request timeout (in seconds) - configurable via environment variables
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800"))  # 30 minutes default

# Per-file processing timeout (in seconds) - configurable via environment variables
# This is the maximum time allowed for processing a single file (text extraction + OpenAI API call)
# Normal processing: 5-10 seconds per file
# Edge cases (large files, slow API): up to 120 seconds
PER_FILE_TIMEOUT = int(os.getenv("PER_FILE_TIMEOUT_SECONDS", "120"))  # 2 minutes default per file

# Allowed file extensions
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".rtf", ".pptx", ".odt"]

# Memory monitoring function (defined early so it can be used during startup)
def log_memory_usage(context: str = ""):
    """Log current memory usage for debugging."""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = process.memory_percent()
        logger.info(f"Memory usage {context}: {memory_mb:.2f} MB ({memory_percent:.1f}%)")
    except Exception as e:
        logger.warning(f"Could not get memory info: {e}")

# Log memory at startup
log_memory_usage("(startup)")

# Thread pool executor for CPU-bound text extraction operations
# This allows synchronous I/O operations to run without blocking the async event loop
TEXT_EXTRACTION_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="text_extract")

# Thread pool executor for blocking I/O operations (Supabase uploads)
# This prevents file uploads from blocking the async event loop
STORAGE_UPLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="storage_upload")

# ============================================================================
# JOB-BASED ARCHITECTURE - Decouples HTTP requests from long-running processing
# ============================================================================
# HTTP is not suitable for long-running document processing, so we decouple
# requests from execution using a job-based architecture with Supabase storage
# and a separate worker process.

from job_service import (
    create_job, get_job, get_jobs_by_user_id, store_file_data, 
    delete_job, JobStatus, upload_file_to_storage, store_file_storage_urls
)

# Note: Job processing is handled by worker.py (separate process)
# The web server only creates jobs in Supabase and returns immediately

# Global request timeout handler
class RequestTimeoutHandler:
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self.start_time = None
    
    def start(self):
        self.start_time = time.time()
    
    def check_timeout(self):
        if self.start_time and (time.time() - self.start_time) > self.timeout_seconds:
            raise HTTPException(status_code=408, detail="Request timeout exceeded")
    
    def get_remaining_time(self):
        if self.start_time:
            return max(0, self.timeout_seconds - (time.time() - self.start_time))
        return self.timeout_seconds

# Global exception handler for request entity too large
@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc: HTTPException):
    logger.warning(f"Request entity too large: {request.url}")
    log_memory_usage("(413 error)")
    return JSONResponse(
        status_code=413,
        content={
            "error": "Request Entity Too Large",
            "detail": "The uploaded file(s) exceed the maximum allowed size.",
            "max_file_size_mb": MAX_FILE_SIZE // (1024*1024),
            "max_total_size_mb": MAX_TOTAL_SIZE // (1024*1024)
        }
    )

# Rate limit exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.
    Returns a user-friendly error message with retry information.
    """
    client_ip = get_remote_address(request)
    logger.warning(f"Rate limit exceeded for IP {client_ip}: {request.url}")
    response = _rate_limit_exceeded_handler(request, exc)
    # Enhance the response with retry information
    if hasattr(response, 'body') and response.body:
        import json
        try:
            content = json.loads(response.body.decode())
            content["retry_after"] = 60
            content["message"] = "Please wait a minute before making more requests."
            response.body = json.dumps(content).encode()
        except:
            pass  # If parsing fails, use default response
    return response

# Global exception handler for all unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them with full traceback."""
    error_id = time.time()
    logger.error("=" * 80)
    logger.error(f"UNHANDLED EXCEPTION [{error_id}]")
    logger.error(f"URL: {request.method} {request.url}")
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Exception message: {str(exc)}")
    logger.error("Full traceback:")
    logger.error(traceback.format_exc())
    log_memory_usage("(unhandled exception)")
    logger.error("=" * 80)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again.",
            "error_id": str(error_id)
        }
    )

# Request validation middleware to handle invalid HTTP requests gracefully
class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to catch and handle invalid HTTP requests gracefully."""
    
    async def dispatch(self, request: StarletteRequest, call_next):
        try:
            # Validate request method
            if request.method not in ["GET", "POST", "OPTIONS", "HEAD"]:
                logger.warning(f"Invalid HTTP method: {request.method} for {request.url}")
                return JSONResponse(
                    status_code=405,
                    content={"error": "Method not allowed", "detail": f"Method {request.method} is not allowed"}
                )
            
            # Validate request path (basic sanity check)
            path = str(request.url.path)
            if len(path) > 2000:  # Prevent path traversal attacks
                logger.warning(f"Path too long: {len(path)} characters")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Bad request", "detail": "Request path too long"}
                )
            
            # Process request
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Catch any malformed request errors
            logger.error(f"Request validation error: {str(e)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=400,
                content={"error": "Bad request", "detail": "Invalid HTTP request format"}
            )

# Add request validation middleware (should be first)
app.add_middleware(RequestValidationMiddleware)

# Add GZip middleware for better performance with large files
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS - configurable via environment variable
# Set ALLOWED_ORIGINS as comma-separated list: "https://example.com,https://app.example.com"
# Or use "*" for development (not recommended for production)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if allowed_origins == ["*"]:
    logger.warning("CORS is set to allow all origins. Restrict this in production using ALLOWED_ORIGINS env var.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

def validate_file(file: UploadFile):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

def validate_file_size(file: UploadFile):
    """Validate file size before processing."""
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

def validate_multiple_files_size(files: List[UploadFile]):
    """Validate total size of multiple files."""
    total_size = 0
    for file in files:
        if hasattr(file, 'size') and file.size:
            total_size += file.size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Total files size too large. Maximum total size allowed: {MAX_TOTAL_SIZE // (1024*1024)}MB"
            )

async def analyze_single_file_direct(file: UploadFile, timeout_handler: RequestTimeoutHandler) -> dict:
    """Analyze a single file using only Prompt 2 (Topic-Aware Analysis) - no routing."""
    tmp_path = None
    try:
        # Check timeout before processing
        timeout_handler.check_timeout()
        
        validate_file(file)
        validate_file_size(file)

        # Save file temporarily to disk
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            file_bytes = await file.read()
            tmp.write(file_bytes)
            tmp_path = tmp.name

        # Check timeout before text extraction
        timeout_handler.check_timeout()
        
        # 1. Extract text using the hybrid service with timeout (async via thread pool)
        try:
            log_memory_usage(f"before text extraction - {file.filename}")
            # Run synchronous text extraction in thread pool to avoid blocking event loop
            extracted_text = await asyncio.get_event_loop().run_in_executor(
                TEXT_EXTRACTION_EXECUTOR,
                textract_service.extract_text_from_upload,
                tmp_path,
                file_bytes
            )
            log_memory_usage(f"after text extraction - {file.filename}")
        except Exception as e:
            logger.error(f"Text extraction failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(text extraction error - {file.filename})")
            return {
                "filename": file.filename,
                "error": f"Text extraction failed: {str(e)}",
                "status": "failed"
            }
        
        if not extracted_text or not extracted_text.strip():
            return {
                "filename": file.filename,
                "error": "Failed to extract meaningful text from document.",
                "status": "failed"
            }

        # Check timeout before analysis
        timeout_handler.check_timeout()
        
        # 2. PROMPT 2: Topic-Aware Analysis (direct, no routing)
        try:
            analysis_result = await asyncio.wait_for(
                openai_service.analyze_document(
                    extracted_text,
                    channel=None,  # No routing, so no channel
                    topic_type=None,  # No routing, so no topic_type
                    topic_title=None  # No routing, so no topic_title
                ),
                timeout=timeout_handler.get_remaining_time()
            )
        except asyncio.TimeoutError:
            logger.error(f"Analysis timeout for {file.filename}")
            log_memory_usage(f"(analysis timeout - {file.filename})")
            return {
                "filename": file.filename,
                "error": "Analysis timeout - document too complex",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Analysis failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(analysis error - {file.filename})")
            return {
                "filename": file.filename,
                "error": f"Analysis failed: {str(e)}",
                "status": "failed"
            }
        
        logger.info(f"Successfully analyzed {file.filename}")

        return {
            "filename": file.filename,
            "analysis": analysis_result,
            "status": "success",
            "extracted_text": extracted_text[:1000]  # Keep first 1000 chars for reference
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}")
        logger.error(traceback.format_exc())
        log_memory_usage(f"(processing error - {file.filename})")
        return {
            "filename": file.filename,
            "error": str(e),
            "status": "failed"
        }
    finally:
        # Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

async def process_single_file(file: UploadFile, timeout_handler: RequestTimeoutHandler) -> dict:
    """Process a single file with routing and analysis (two-prompt system)."""
    tmp_path = None
    try:
        # Check timeout before processing
        timeout_handler.check_timeout()
        
        validate_file(file)
        validate_file_size(file)

        # Save file temporarily to disk
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            file_bytes = await file.read()
            tmp.write(file_bytes)
            tmp_path = tmp.name

        # Check timeout before text extraction
        timeout_handler.check_timeout()
        
        # 1. Extract text using the hybrid service with timeout (async via thread pool)
        try:
            log_memory_usage(f"before text extraction - {file.filename}")
            # Run synchronous text extraction in thread pool to avoid blocking event loop
            extracted_text = await asyncio.get_event_loop().run_in_executor(
                TEXT_EXTRACTION_EXECUTOR,
                textract_service.extract_text_from_upload,
                tmp_path,
                file_bytes
            )
            log_memory_usage(f"after text extraction - {file.filename}")
        except Exception as e:
            logger.error(f"Text extraction failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(text extraction error - {file.filename})")
            return {
                "filename": file.filename,
                "error": f"Text extraction failed: {str(e)}",
                "status": "failed"
            }
        
        if not extracted_text or not extracted_text.strip():
            return {
                "filename": file.filename,
                "error": "Failed to extract meaningful text from document.",
                "status": "failed"
            }

        # Check timeout before routing
        timeout_handler.check_timeout()
        
        # 2. PROMPT 1: Routing + Topic Creation
        try:
            routing_result = await asyncio.wait_for(
                openai_service.classify_document(extracted_text),
                timeout=timeout_handler.get_remaining_time()
            )
        except asyncio.TimeoutError:
            logger.error(f"Routing timeout for {file.filename}")
            log_memory_usage(f"(routing timeout - {file.filename})")
            return {
                "filename": file.filename,
                "error": "Routing timeout - document too complex",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Routing failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(routing error - {file.filename})")
            return {
                "filename": file.filename,
                "error": f"Routing failed: {str(e)}",
                "status": "failed"
            }
        
        # Check if document should go to ARCHIVE
        if routing_result.get("routing") == "ARCHIVE":
            logger.info(f"{file.filename} routed to ARCHIVE")
            return {
                "filename": file.filename,
                "routing": "ARCHIVE",
                "channel": routing_result.get("channel"),
                "reasoning": routing_result.get("reasoning"),
                "status": "success",
                "message": "This document has been stored in your Archive for future use."
            }
        
        # Check timeout before analysis
        timeout_handler.check_timeout()
        
        # 3. PROMPT 2: Topic-Aware Analysis (only for INBOX documents)
        try:
            analysis_result = await asyncio.wait_for(
                openai_service.analyze_document(
                    extracted_text,
                    channel=routing_result.get("channel"),
                    topic_type=routing_result.get("topic_type"),
                    topic_title=routing_result.get("topic_title")
                ),
                timeout=timeout_handler.get_remaining_time()
            )
        except asyncio.TimeoutError:
            logger.error(f"Analysis timeout for {file.filename}")
            log_memory_usage(f"(analysis timeout - {file.filename})")
            return {
                "filename": file.filename,
                "error": "Analysis timeout - document too complex",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Analysis failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(analysis error - {file.filename})")
            return {
                "filename": file.filename,
                "error": f"Analysis failed: {str(e)}",
                "status": "failed"
            }
        
        logger.info(f"Successfully processed {file.filename} - INBOX topic created")

        return {
            "filename": file.filename,
            "routing": "INBOX",
            "channel": routing_result.get("channel"),
            "topic_type": routing_result.get("topic_type"),
            "topic_title": routing_result.get("topic_title"),
            "urgency": routing_result.get("urgency"),
            "deadline": routing_result.get("deadline"),
            "authority": routing_result.get("authority"),
            "analysis": analysis_result,
            "status": "success",
            "extracted_text": extracted_text[:1000]  # Keep first 1000 chars for reference
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}")
        logger.error(traceback.format_exc())
        log_memory_usage(f"(processing error - {file.filename})")
        return {
            "filename": file.filename,
            "error": str(e),
            "status": "failed"
        }
    finally:
        # Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# CONSOLIDATED ANALYSIS FUNCTION (Commented out - not needed for MVP)
# Keeping code for future use if needed
async def analyze_multiple_files_consolidated_DISABLED(files: List[UploadFile], channel: str = None) -> dict:
    """
    Analyze multiple files in a channel together and provide consolidated channel analysis.
    Uses the two-prompt system: routing for each file, then consolidated analysis for the channel.
    """
    timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
    timeout_handler.start()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > MAX_FILES_PER_REQUEST:  # Limit to prevent abuse
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request")
    
    validate_multiple_files_size(files)
    
    # Process all files to extract text and route
    file_results = []
    inbox_files = []
    archive_files = []
    all_texts = []
    file_info = []
    topics = []
    
    logger.info(f"Starting to process {len(files)} files for consolidated analysis")
    
    for i, file in enumerate(files):
        # Check timeout for each file
        timeout_handler.check_timeout()
        
        logger.info(f"Processing file {i+1}/{len(files)}: {file.filename}")
        
        # Extract text and route document
        tmp_path = None
        try:
            validate_file(file)
            validate_file_size(file)
            
            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                file_bytes = await file.read()
                tmp.write(file_bytes)
                tmp_path = tmp.name
            
            # Extract text (async via thread pool)
            try:
                extracted_text = await asyncio.get_event_loop().run_in_executor(
                    TEXT_EXTRACTION_EXECUTOR,
                    textract_service.extract_text_from_upload,
                    tmp_path,
                    file_bytes
                )
            except Exception as e:
                logger.error(f"Text extraction failed for {file.filename}: {str(e)}")
                logger.error(traceback.format_exc())
                log_memory_usage(f"(text extraction error - {file.filename})")
                continue
            
            if not extracted_text or not extracted_text.strip():
                logger.warning(f"No text extracted from {file.filename}")
                continue
            
            # Route document (Prompt 1)
            try:
                routing_result = await asyncio.wait_for(
                    openai_service.classify_document(extracted_text),
                    timeout=timeout_handler.get_remaining_time()
                )
                
                routing = routing_result.get("routing", "ARCHIVE")
                doc_channel = routing_result.get("channel", "ARCHIVE")
                
                # Only include INBOX documents in consolidated analysis
                if routing == "INBOX":
                    # If channel filter is specified, only include matching documents
                    if channel is None or doc_channel == channel:
                        file_results.append({
                            "filename": file.filename,
                            "text_length": len(extracted_text),
                            "channel": doc_channel,
                            "topic_type": routing_result.get("topic_type"),
                            "topic_title": routing_result.get("topic_title"),
                            "urgency": routing_result.get("urgency"),
                            "deadline": routing_result.get("deadline"),
                            "status": "inbox"
                        })
                        all_texts.append(extracted_text)
                        file_info.append({
                            "filename": file.filename,
                            "text_length": len(extracted_text),
                            "channel": doc_channel,
                            "topic_title": routing_result.get("topic_title")
                        })
                        topics.append({
                            "topic_type": routing_result.get("topic_type"),
                            "topic_title": routing_result.get("topic_title"),
                            "urgency": routing_result.get("urgency"),
                            "deadline": routing_result.get("deadline")
                        })
                        inbox_files.append(file.filename)
                        
                        logger.info(f"Added {file.filename} to INBOX - Channel: {doc_channel}, Topic: {routing_result.get('topic_title')}")
                    else:
                        logger.info(f"Skipped {file.filename} - different channel ({doc_channel} != {channel})")
                else:
                    archive_files.append(file.filename)
                    logger.info(f"{file.filename} routed to ARCHIVE")
                
            except asyncio.TimeoutError:
                logger.error(f"Routing timeout for {file.filename}")
                continue
            except Exception as e:
                logger.error(f"Routing failed for {file.filename}: {str(e)}")
                logger.error(traceback.format_exc())
                log_memory_usage(f"(routing error - {file.filename})")
                continue
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(processing error - {file.filename})")
            continue
        finally:
            # Clean up temporary file
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    logger.info(f"Completed file processing: {len(inbox_files)} inbox files, {len(archive_files)} archive files")
    
    if not file_results:
        return {
            "total_files": len(files),
            "inbox_files": 0,
            "archive_files": len(archive_files),
            "message": "All documents were routed to archive. No consolidated analysis needed.",
            "archived_files": archive_files,
            "status": "success",
            "processing_time": time.time() - timeout_handler.start_time
        }
    
    # Check timeout before consolidated analysis
    timeout_handler.check_timeout()
    
    # Combine all extracted texts for consolidated channel analysis
    combined_text = "\n\n--- DOCUMENT SEPARATOR ---\n\n".join(all_texts)
    detected_channel = file_results[0].get("channel") if file_results else "GENERAL_ACTIONABLE"
    
    # Check topic type compatibility for better consolidation
    topic_types = [t.get("topic_type") for t in topics if t.get("topic_type")]
    unique_topic_types = list(set(topic_types))
    
    if len(unique_topic_types) > 3:
        logger.warning(f"Multiple diverse topic types detected ({len(unique_topic_types)}). Consolidated analysis may be less specific.")
        logger.warning(f"Topic types: {unique_topic_types}")
    
    logger.info(f"Starting consolidated channel analysis for {detected_channel}")
    logger.info(f"Analyzing {len(all_texts)} documents with {len(combined_text)} total characters")
    logger.info(f"Topic types in consolidation: {unique_topic_types}")
    
    # Perform consolidated channel analysis (Prompt 3)
    try:
        logger.info(f"Calling OpenAI API for consolidated channel analysis...")
        consolidated_analysis = await asyncio.wait_for(
            openai_service.analyze_multiple_documents_consolidated(
                combined_text, 
                file_info,
                detected_channel,
                topics
            ),
            timeout=timeout_handler.get_remaining_time()
        )
        logger.info(f"OpenAI API call completed successfully")
        
        return {
            "total_files": len(files),
            "inbox_files": len(inbox_files),
            "archive_files": len(archive_files),
            "channel": detected_channel,
            "file_info": file_info,
            "topics": topics,
            "consolidated_analysis": consolidated_analysis,
            "archived_files": archive_files,
            "status": "success",
            "processing_time": time.time() - timeout_handler.start_time
        }
        
    except asyncio.TimeoutError:
        logger.error("Consolidated channel analysis timeout")
        raise HTTPException(status_code=408, detail="Analysis timeout - too many complex documents")
    except Exception as e:
        logger.error(f"Error in consolidated channel analysis: {e}")
        logger.error(traceback.format_exc())
        log_memory_usage("(consolidated analysis error)")
        raise HTTPException(status_code=500, detail=f"Consolidated analysis failed: {str(e)}")

# ============================================================================
# ASYNC JOB ENDPOINTS - Return immediately, process in background
# ============================================================================

@app.post("/classify-documents-async")
@limiter.limit("25/minute")
async def classify_documents_async(
    request: Request, 
    files: List[UploadFile] = File(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier from frontend (optional)")
):
    """
    Submit documents for classification (async job pattern).
    Returns job_id immediately. Use /job/{job_id} to check status and get results.
    Solves Cloudflare 504 timeout issues by returning immediately.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request")
    
    validate_multiple_files_size(files)
    
    # Extract user_id from header (optional)
    user_id = x_user_id or request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    
    # Create job in Supabase database first (CREATED -> not worker-visible yet)
    job_id = create_job(endpoint_type="classify", total_files=len(files), user_id=user_id, status=JobStatus.CREATED)
    
    # Read all files into memory quickly (async, fast)
    # This is fast because we're just reading bytes, not processing
    file_data_list = []
    for file in files:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        file_data_list.append({
            "filename": file.filename,
            "bytes": file_bytes,
            "size": file_size,
            "suffix": Path(file.filename).suffix
        })
    
    # Upload files to Supabase Storage in parallel (async via thread pool)
    # We wait for uploads to complete before returning to ensure files are stored
    # before the worker picks up the job
    async def upload_files_async():
        """Upload files to storage and update DB - runs in thread pool but we await it"""
        def upload_files_background():
            """Upload files to storage and update DB - runs in thread pool"""
            file_urls = []
            for file_data in file_data_list:
                try:
                    # Upload file to Supabase Storage (blocking operation)
                    # Returns file_path (e.g., "job_id/filename"), not public URL
                    file_path = upload_file_to_storage(job_id, file_data["filename"], file_data["bytes"])
                    
                    if file_path:
                        file_urls.append({
                            "filename": file_data["filename"],
                            "file_path": file_path,  # Store file path (not public URL)
                            "suffix": file_data["suffix"],
                            "size": file_data["size"]
                        })
                    else:
                        # Fallback: local filesystem
                        logger.error(f"Failed to upload {file_data['filename']} to Supabase Storage, falling back to local storage")
                        job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
                        job_dir.mkdir(parents=True, exist_ok=True)
                        file_path = job_dir / file_data["filename"]
                        with open(file_path, "wb") as f:
                            f.write(file_data["bytes"])
                        file_urls.append({
                            "filename": file_data["filename"],
                            "file_path": str(file_path),
                            "suffix": file_data["suffix"],
                            "size": file_data["size"]
                        })
                except Exception as e:
                    logger.error(f"Error uploading {file_data['filename']}: {e}")
                    # Continue with other files
            
            # Store file paths in database
            if file_urls:
                try:
                    if any("file_path" in f for f in file_urls):
                        store_file_storage_urls(job_id, file_urls)
                    elif any("storage_url" in f for f in file_urls):
                        # Legacy format with storage_url - still supported
                        store_file_storage_urls(job_id, file_urls)
                    else:
                        store_file_data(job_id, file_urls)
                except Exception as e:
                    logger.error(f"Failed to store file data for job {job_id}: {e}")
                    # Update job with error but don't fail the request
                    from job_service import update_job_status, JobStatus
                    update_job_status(job_id, JobStatus.FAILED, error=f"Failed to store file data: {str(e)}")
        
        # Run in thread pool and await completion
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(STORAGE_UPLOAD_EXECUTOR, upload_files_background)
    
    # Wait for file uploads to complete before returning.
    # IMPORTANT: Only after uploads + metadata are stored do we mark job READY.
    await upload_files_async()

    # Mark job READY (worker-visible) only after all required inputs are committed
    from job_service import update_job_status
    update_job_status(job_id, JobStatus.READY, progress=0, processed_files=0)
    
    # Worker process will pick up this job from the database
    
    return {
        "job_id": job_id,
        "status": "created",
        "message": "Job created. Use /job/{job_id} to check status and get results.",
        "total_files": len(files),
        "status_endpoint": f"/job/{job_id}",
        "estimated_time_seconds": len(files) * 10  # Rough estimate: 10 seconds per file
    }

@app.post("/analyze-multiple-async")
@limiter.limit("7/minute")
async def analyze_multiple_async(
    request: Request, 
    files: List[UploadFile] = File(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier from frontend (optional)")
):
    """
    Submit documents for analysis (async job pattern).
    Returns job_id immediately. Use /job/{job_id} to check status and get results.
    Solves Cloudflare 504 timeout issues by returning immediately.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request")
    
    validate_multiple_files_size(files)
    
    # Extract user_id from header (optional)
    user_id = x_user_id or request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    
    # Create job in Supabase database first (CREATED -> not worker-visible yet)
    job_id = create_job(endpoint_type="analyze", total_files=len(files), user_id=user_id, status=JobStatus.CREATED)
    
    # Upload files to Supabase Storage and store URLs
    file_urls = []
    for file in files:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        # Upload file to Supabase Storage
        # Returns file_path (e.g., "job_id/filename"), not public URL
        file_path = upload_file_to_storage(job_id, file.filename, file_bytes)
        
        if file_path:
            # Store file path (not public URL)
            file_urls.append({
                "filename": file.filename,
                "file_path": file_path,  # File path format: "job_id/filename"
                "suffix": Path(file.filename).suffix,
                "size": file_size
            })
        else:
            # Fallback: if storage upload fails, log error but continue
            logger.error(f"Failed to upload {file.filename} to Supabase Storage, falling back to local storage")
            # Fallback to local filesystem (backward compatibility)
            job_dir = Path(tempfile.gettempdir()) / "inbox_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            file_path = job_dir / file.filename
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            file_urls.append({
                "filename": file.filename,
                "file_path": str(file_path),  # Local path (fallback)
                "suffix": Path(file.filename).suffix,
                "size": file_size
            })
    
    # Ensure we have file data to store
    if not file_urls:
        raise HTTPException(status_code=500, detail="Failed to process files. No file data to store.")
    
    # Store file paths in Supabase (preferred) or file paths (fallback)
    try:
        if any("file_path" in f for f in file_urls):
            # Use new file_path format
            store_file_storage_urls(job_id, file_urls)
        elif any("storage_url" in f for f in file_urls):
            # Legacy format with storage_url - still supported
            store_file_storage_urls(job_id, file_urls)
        else:
            # Fallback to old file_data format
            store_file_data(job_id, file_urls)
    except Exception as e:
        logger.error(f"Failed to store file data for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store file data: {str(e)}")

    # Mark job READY (worker-visible) only after all required inputs are committed
    from job_service import update_job_status
    update_job_status(job_id, JobStatus.READY, progress=0, processed_files=0)
    
    # Worker process will pick up this job from the database
    
    return {
        "job_id": job_id,
        "status": "created",
        "message": "Job created. Use /job/{job_id} to check status and get results.",
        "total_files": len(files),
        "status_endpoint": f"/job/{job_id}",
        "estimated_time_seconds": len(files) * 15  # Rough estimate: 15 seconds per file
    }

@app.get("/job/{job_id}")
async def get_job_status(
    job_id: str, 
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier for security (optional, verifies job ownership)")
):
    """
    Get job status and results.
    Returns job status, progress, and results (if completed).
    """
    # Extract user_id from header (optional, for security)
    user_id = x_user_id or request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    
    # Get job (with user_id verification if provided)
    job = get_job(job_id, user_id=user_id)
    
    if not job:
        if user_id:
            raise HTTPException(
                status_code=404, 
                detail=f"Job {job_id} not found. Possible reasons: (1) Job doesn't exist, (2) Job was created with different X-User-ID, or (3) Job was created without X-User-ID header. Try querying without X-User-ID header or use the same X-User-ID used when creating the job."
            )
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Job {job_id} not found. The job may not exist in the database or was deleted."
            )
    
    response = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"]
    }
    
    if job.get("total_files"):
        response["total_files"] = job["total_files"]
        response["processed_files"] = job.get("processed_files", 0)
    
    # Include result if completed
    if job["status"] == JobStatus.COMPLETED and job.get("result"):
        response["result"] = job["result"]
    
    # Include error if failed
    if job["status"] == JobStatus.FAILED and job.get("error"):
        response["error"] = job["error"]
    
    return response

@app.get("/jobs")
async def get_user_jobs(
    request: Request, 
    status: Optional[str] = None, 
    limit: int = 100,
    x_user_id: str = Header(..., alias="X-User-ID", description="User identifier from frontend (required)")
):
    """
    Get all jobs for the current user (from X-User-ID header).
    
    Query Parameters:
        status (optional): Filter by status (pending, processing, completed, failed)
        limit (optional): Maximum number of jobs to return (default: 100)
    """
    # user_id is now required via Header parameter, so it's guaranteed to be set
    user_id = x_user_id
    
    # Validate status if provided
    if status and status not in ["created", "ready", "processing", "completed", "failed", "pending"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be: created, ready, processing, completed, or failed",
        )
    
    # Get jobs for user
    jobs = get_jobs_by_user_id(user_id, status=status, limit=limit)
    
    return {
        "user_id": user_id,
        "total_jobs": len(jobs),
        "status_filter": status,
        "jobs": jobs
    }

@app.delete("/job/{job_id}")
async def delete_job_endpoint(
    job_id: str, 
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier for security (optional, verifies job ownership)")
):
    """
    Delete a job from Supabase (cleanup).
    """
    # Extract user_id from header (optional, for security)
    user_id = x_user_id or request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    
    # Verify job belongs to user if user_id provided
    if user_id:
        job = get_job(job_id, user_id=user_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or doesn't belong to user")
    
    success = delete_job(job_id)
    if success:
        logger.info(f"Job {job_id} deleted")
        return {"message": f"Job {job_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

# ============================================================================
# ORIGINAL SYNC ENDPOINTS (kept for backward compatibility)
# ============================================================================

@app.get("/", status_code=200)
async def root():
    """Root endpoint for load balancer health checks"""
    return {"status": "ok", "message": "Document Analysis API", "timestamp": time.time()}

@app.get("/health", status_code=200)
async def health_check():
    """Health check endpoint for load balancer and monitoring"""
    return {"status": "ok", "timestamp": time.time()}

@app.post("/analyze")
@limiter.limit("12/minute")  # 10-15 requests per minute (using 12 as middle)
async def analyze_single(request: Request, file: UploadFile = File(...)):
    """Analyze a single document using only Prompt 2 (Topic-Aware Analysis) - no routing."""
    timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
    timeout_handler.start()
    
    result = await analyze_single_file_direct(file, timeout_handler)
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    result["processing_time"] = time.time() - timeout_handler.start_time
    return result

@app.post("/analyze-multiple")
@limiter.limit("7/minute")  # 5-10 requests per minute (using 7 as middle)
async def analyze_multiple(request: Request, files: List[UploadFile] = File(...)):
    """
    Analyze multiple documents individually using two-prompt system.
    Each file goes through: Prompt 1 (Routing) → Prompt 2 (Analysis if INBOX)
    """
    timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
    timeout_handler.start()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > MAX_FILES_PER_REQUEST:  # Limit to prevent abuse
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request")
    
    validate_multiple_files_size(files)
    
    logger.info(f"Processing {len(files)} files with two-prompt system")
    
    # Process all files with timeout handling
    results = []
    inbox_count = 0
    archive_count = 0
    
    for i, file in enumerate(files):
        # Check timeout for each file
        timeout_handler.check_timeout()
        
        logger.info(f"Processing file {i+1}/{len(files)}: {file.filename}")
        result = await process_single_file(file, timeout_handler)
        results.append(result)
        
        # Track routing stats
        if result.get("routing") == "INBOX":
            inbox_count += 1
        elif result.get("routing") == "ARCHIVE":
            archive_count += 1
    
    # Count successes and failures
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - successful
    
    logger.info(f"Completed: {successful} successful, {failed} failed")
    logger.info(f"Routing: {inbox_count} inbox, {archive_count} archive")
    
    return {
        "total_files": len(results),
        "successful": successful,
        "failed": failed,
        "inbox_count": inbox_count,
        "archive_count": archive_count,
        "results": results,
        "processing_time": time.time() - timeout_handler.start_time
    }

# CONSOLIDATED ANALYSIS DISABLED (Commented out - not needed for MVP)
# @app.post("/analyze-consolidated")
# async def analyze_consolidated(files: List[UploadFile] = File(...)):
#     """Analyze multiple documents together with timeout handling."""
#     return await analyze_multiple_files_consolidated(files)

async def classify_single_file(file: UploadFile, timeout_handler: RequestTimeoutHandler, semaphore: asyncio.Semaphore) -> dict:
    """
    Helper function to classify a single file (extract text + route).
    Used for parallel processing in classify_documents endpoint.
    """
    tmp_path = None
    try:
        # Check timeout before processing
        timeout_handler.check_timeout()
        
        validate_file(file)
        validate_file_size(file)
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            file_bytes = await file.read()
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        # Extract text (async via thread pool)
        timeout_handler.check_timeout()
        try:
            extracted_text = await asyncio.get_event_loop().run_in_executor(
                TEXT_EXTRACTION_EXECUTOR,
                textract_service.extract_text_from_upload,
                tmp_path,
                file_bytes
            )
        except Exception as e:
            logger.error(f"Text extraction failed for {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            log_memory_usage(f"(text extraction error - {file.filename})")
            return {
                "filename": file.filename,
                "routing": "ARCHIVE",
                "channel": "ARCHIVE",
                "topic_type": None,
                "topic_title": None,
                "urgency": "LOW",
                "deadline": None,
                "authority": None,
                "reasoning": f"Text extraction failed: {str(e)}",
                "status": "failed"
            }
        
        if not extracted_text or not extracted_text.strip():
            return {
                "filename": file.filename,
                "routing": "ARCHIVE",
                "channel": "ARCHIVE",
                "topic_type": None,
                "topic_title": None,
                "urgency": "LOW",
                "deadline": None,
                "authority": None,
                "reasoning": "No text extracted from document",
                "status": "failed"
            }
        
        # Route document (Prompt 1) - Use semaphore to limit concurrent OpenAI API calls
        timeout_handler.check_timeout()
        async with semaphore:  # Limit concurrent OpenAI API calls
            try:
                # Use configurable per-file timeout instead of full remaining time
                # This prevents individual files from blocking the entire request
                # Normal processing: 5-10 seconds per file
                # Edge cases (large files, slow API, network issues): up to PER_FILE_TIMEOUT seconds
                per_file_timeout = min(PER_FILE_TIMEOUT, timeout_handler.get_remaining_time())
                if per_file_timeout <= 0:
                    raise asyncio.TimeoutError("No time remaining")
                routing_result = await asyncio.wait_for(
                    openai_service.classify_document(extracted_text),
                    timeout=per_file_timeout
                )
                
                return {
                    "filename": file.filename,
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
                
            except asyncio.TimeoutError:
                logger.error(f"Routing timeout for {file.filename}")
                return {
                    "filename": file.filename,
                    "routing": "ARCHIVE",
                    "channel": "ARCHIVE",
                    "topic_type": None,
                    "topic_title": None,
                    "urgency": "LOW",
                    "deadline": None,
                    "authority": None,
                    "reasoning": "Routing timeout",
                    "status": "timeout"
                }
            except Exception as e:
                logger.error(f"Routing failed for {file.filename}: {str(e)}")
                logger.error(traceback.format_exc())
                log_memory_usage(f"(routing error - {file.filename})")
                return {
                    "filename": file.filename,
                    "routing": "ARCHIVE",
                    "channel": "ARCHIVE",
                    "topic_type": None,
                    "topic_title": None,
                    "urgency": "LOW",
                    "deadline": None,
                    "authority": None,
                    "reasoning": f"Routing failed: {str(e)}",
                    "status": "failed"
                }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}")
        logger.error(traceback.format_exc())
        log_memory_usage(f"(processing error - {file.filename})")
        return {
            "filename": file.filename,
            "routing": "ARCHIVE",
            "channel": "ARCHIVE",
            "topic_type": None,
            "topic_title": None,
            "urgency": "LOW",
            "deadline": None,
            "authority": None,
            "reasoning": f"Processing error: {str(e)}",
            "status": "error"
        }
    finally:
        # Clean up temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/classify-documents")
@limiter.limit("25/minute")  # 20-30 requests per minute (using 25 as middle)
async def classify_documents(request: Request, files: List[UploadFile] = File(...)):
    """
    Route and classify bulk documents using the two-prompt system.
    Returns routing decisions and topic information for each document.
    Uses parallel processing to handle multiple files efficiently.
    """
    timeout_handler = RequestTimeoutHandler(REQUEST_TIMEOUT)
    timeout_handler.start()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES_PER_REQUEST} files allowed per request")
    
    validate_multiple_files_size(files)
    
    logger.info(f"Starting parallel routing and classification of {len(files)} files")
    
    # Create semaphore to limit concurrent OpenAI API calls (avoid rate limits)
    # Dynamic semaphore based on file count for optimal performance:
    # - Small batches (1-10 files): 5 concurrent (safe for all OpenAI tiers)
    # - Medium batches (11-20 files): 8 concurrent (good balance)
    # - Large batches (21-30 files): 12 concurrent (faster, requires Tier 2+ OpenAI)
    if len(files) <= 10:
        max_concurrent_api_calls = 5
    elif len(files) <= 20:
        max_concurrent_api_calls = 8
    else:  # 21-30 files
        max_concurrent_api_calls = 12
    
    logger.info(f"Using {max_concurrent_api_calls} concurrent OpenAI API calls for {len(files)} files")
    semaphore = asyncio.Semaphore(max_concurrent_api_calls)
    
    # Process all files in parallel
    tasks = [
        classify_single_file(file, timeout_handler, semaphore)
        for file in files
    ]
    
    # Wait for all files to complete
    routing_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions that occurred during parallel processing
    processed_results = []
    for i, result in enumerate(routing_results):
        if isinstance(result, Exception):
            logger.error(f"Exception processing file {files[i].filename}: {result}")
            logger.error(traceback.format_exc())
            processed_results.append({
                "filename": files[i].filename,
                "routing": "ARCHIVE",
                "channel": "ARCHIVE",
                "topic_type": None,
                "topic_title": None,
                "urgency": "LOW",
                "deadline": None,
                "authority": None,
                "reasoning": f"Processing exception: {str(result)}",
                "status": "error"
            })
        else:
            processed_results.append(result)
    
    # Build channel summary from results
    channel_summary = {}
    inbox_count = 0
    archive_count = 0
    
    for result in processed_results:
        routing = result.get("routing", "ARCHIVE")
        channel = result.get("channel", "ARCHIVE")
        
        if routing == "INBOX":
            inbox_count += 1
        else:
            archive_count += 1
        
        if channel not in channel_summary:
            channel_summary[channel] = {
                "count": 0,
                "inbox_count": 0,
                "archive_count": 0,
                "files": [],
                "topics": [],
                "urgent_items": 0
            }
        
        channel_summary[channel]["count"] += 1
        channel_summary[channel]["files"].append(result.get("filename"))
        
        if routing == "INBOX":
            channel_summary[channel]["inbox_count"] += 1
            if result.get("topic_title"):
                channel_summary[channel]["topics"].append(result.get("topic_title"))
            if result.get("urgency") == "HIGH":
                channel_summary[channel]["urgent_items"] += 1
        else:
            channel_summary[channel]["archive_count"] += 1
        
        if result.get("status") == "success":
            logger.info(f"Routed {result.get('filename')} to {routing} - Channel: {channel}, Topic: {result.get('topic_title')}")
    
    # Count successes and failures
    successful = sum(1 for r in processed_results if r.get("status") == "success")
    failed = len(processed_results) - successful
    
    logger.info(f"Routing completed: {successful} successful, {failed} failed")
    logger.info(f"Results: {inbox_count} inbox items, {archive_count} archive items")
    
    return {
        "total_files": len(files),
        "successful_routing": successful,
        "failed_routing": failed,
        "inbox_count": inbox_count,
        "archive_count": archive_count,
        "routing_results": processed_results,
        "channel_summary": channel_summary,
        "available_channels": list(channel_summary.keys()),
        "status": "success",
        "processing_time": time.time() - timeout_handler.start_time
    }


# Catch-all handler for invalid paths - MUST BE LAST to not interfere with specific routes
# Returns 404 instead of crashing worker on invalid paths
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def catch_all(path: str, request: Request):
    """Catch-all route handler for invalid paths to prevent worker crashes from vulnerability scanners."""
    logger.warning(f"Invalid path requested: {request.method} {request.url.path}")
    logger.warning(f"Client IP: {request.client.host if request.client else 'unknown'}")
    
    # Return proper 404 JSON response instead of letting it crash
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": f"The requested path '{path}' was not found on this server.",
            "available_endpoints": [
                "/",
                "/health",
                "/analyze",
                "/analyze-multiple",
                "/classify-documents",
                "/classify-documents-async",
                "/analyze-multiple-async",
                "/job/{job_id}"
            ]
        }
    )

# Graceful shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    # Shutdown thread pool executor gracefully
    TEXT_EXTRACTION_EXECUTOR.shutdown(wait=True)
    logger.info("Thread pool executor shut down")

if __name__ == "__main__":
    import uvicorn
    # Use PORT from environment (Render provides this) or default to 8000
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)