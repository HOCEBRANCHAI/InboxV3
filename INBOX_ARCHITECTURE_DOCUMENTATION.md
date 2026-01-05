# Inbox Project - Overall Architecture Documentation

## Q1.1: Overall Architecture (1-2 Pages)

### System Overview

The **Inbox Project** is a document classification and routing system that automatically processes business documents (invoices, bills, notices, etc.) and routes them to either **INBOX** (actionable items) or **ARCHIVE** (passive documents). The system uses AI-powered classification with OpenAI GPT-4o and optional OCR via AWS Textract for scanned documents.

### Components

#### 1. **Frontend Application** (Not Part of This Backend)
- **Status**: Separate frontend application (not included in this backend repository)
- **Interaction**: Frontend sends HTTP requests to the Inbox API
- **Communication**: REST API via HTTPS

#### 2. **Inbox Main API (Backend Service)**
- **Service Name**: InboxV3 API
- **Technology**: Python 3.11, FastAPI, Gunicorn with Uvicorn workers
- **Purpose**: User-facing REST API for document upload and inbox routing
- **Responsibilities**:
  - Receives document uploads from frontend
  - Validates files (size, format, count)
  - Creates job records in database
  - Stores files temporarily on filesystem
  - Returns job ID immediately (< 1 second)
  - Provides job status endpoints
- **Key Features**:
  - Async job creation (prevents timeout issues)
  - User ID-based job tracking
  - Rate limiting (12-25 requests/minute)
  - CORS support for frontend integration
  - Health check endpoint
- **Endpoints:**
  - `POST /classify-documents-async` - Submit documents for inbox classification (async, recommended)
  - `POST /classify-documents` - Classify documents (sync, legacy)
  - `POST /analyze` - Analyze single document (sync)
  - `GET /job/{job_id}` - Get job status and results
  - `GET /jobs` - Get all jobs for a user
  - `DELETE /job/{job_id}` - Delete a job
  - `GET /health` - Health check

#### 3. **Inbox Document Processing Worker**
- **Service Name**: InboxV3 Worker
- **Technology**: Python 3.11, asyncio, standalone process
- **Purpose**: Background worker that processes document classification and analysis jobs asynchronously
- **Responsibilities**:
  - Polls database every 5 seconds for pending jobs
  - Reads files from filesystem
  - Extracts text (native libraries or AWS Textract OCR)
  - Calls OpenAI API for document classification
  - Performs inbox routing (INBOX vs ARCHIVE)
  - Updates job status and results in database
  - Cleans up files after processing
- **Key Features**:
  - Decoupled from HTTP requests
  - Parallel file processing (5-12 concurrent API calls)
  - Automatic error handling and retry logic
  - Progress tracking per file

#### 4. **Document Processing / Extraction Service**
- **Service Name**: Text Extraction Service (library/utility)
- **Technology**: Python libraries (pdfplumber, PyPDF2, python-docx, pandas, boto3)
- **Purpose**: OCR and text extraction from various document formats
- **Responsibilities**:
  - Extract text from PDFs (digital and scanned)
  - Extract text from Word documents (DOCX)
  - Extract data from Excel/CSV files
  - Extract text from images (PNG, JPG, JPEG)
  - Fallback to AWS Textract for scanned documents
- **Key Features**:
  - Multi-format support (PDF, DOCX, XLSX, CSV, TXT, PNG, JPG, JPEG, RTF, PPTX, ODT)
  - Hybrid extraction (native first, OCR fallback)
  - Handles up to 10MB files for Textract
  - Multilingual OCR support (via AWS Textract)

#### 5. **Database Service (Supabase)**
- **Service Name**: Supabase PostgreSQL Database
- **Technology**: PostgreSQL (managed by Supabase)
- **Purpose**: Persistent storage for jobs, results, and metadata
- **Responsibilities**:
  - Store job records (`inbox_jobs` table)
  - Store job status (pending, processing, completed, failed)
  - Store processing results (routing decisions, analysis)
  - Store file metadata (paths, sizes, formats)
  - Provide query interface for job status
- **Key Features**:
  - Durable storage (survives server restarts)
  - User ID-based job filtering
  - JSONB storage for flexible results
  - Automatic timestamps (created_at, updated_at)

#### 6. **AI Classification Service (OpenAI)**
- **Service Name**: OpenAI GPT-4o API
- **Technology**: OpenAI API (external service)
- **Purpose**: Document classification and inbox routing
- **Responsibilities**:
  - Analyze document content
  - Classify documents (INBOX vs ARCHIVE)
  - Extract metadata (channel, topic_type, urgency, deadline)
  - Topic-aware routing decisions
- **Key Features**:
  - Custom prompts for inbox routing (see `prompts.py`)
  - Handles invoices, bills, notices, reminders, etc.
  - Extracts actionable information (deadlines, amounts, due dates)

#### 7. **OCR Service (AWS Textract)** - Optional
- **Service Name**: AWS Textract
- **Technology**: AWS API (external service)
- **Purpose**: OCR for scanned documents and images
- **Responsibilities**:
  - Extract text from scanned PDFs
  - Extract text from images (PNG, JPG, JPEG)
  - Multilingual text recognition
- **Key Features**:
  - Optional dependency (service works without it)
  - Pay-per-use pricing
  - High accuracy OCR
  - Handles up to 10MB files

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INBOX SYSTEM ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────────┘

1. DOCUMENT UPLOAD FLOW
───────────────────────
Frontend App
    │
    │ POST /classify-documents-async
    │ Headers: X-User-ID: user-123
    │ Body: files: [doc1.pdf, doc2.pdf, ...]
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Inbox Main API (Render - Free Tier)                            │
│ - Validates files (size, format, count)                         │
│ - Saves files to filesystem: {tempdir}/inbox_jobs/{job_id}/    │
│ - Creates job record in Supabase (status='pending')            │
│ - Returns job_id immediately (< 1 second)                     │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Writes to
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Supabase Database (PostgreSQL)                                  │
│ Table: inbox_jobs                                               │
│ - id: UUID                                                      │
│ - user_id: TEXT                                                 │
│ - status: 'pending'                                             │
│ - file_data: [{"filename": "...", "file_path": "..."}]         │
│ - result: NULL (will be filled by worker)                       │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Returns job_id
    ▼
Frontend App
    │ Receives: {job_id, status: "pending"}


2. DOCUMENT PROCESSING FLOW
───────────────────────────
┌─────────────────────────────────────────────────────────────────┐
│ Inbox Worker Process (Not yet deployed)                         │
│ - Polls Supabase every 5 seconds                               │
│ - Finds jobs with status='pending'                             │
└─────────────────────────────────────────────────────────────────┘
    │
    │ SELECT * FROM inbox_jobs WHERE status='pending'
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Supabase Database                                               │
│ Returns: Pending jobs                                           │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Worker processes job
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Worker Processing Steps:                                        │
│                                                                 │
│ 1. Mark job as 'processing'                                    │
│ 2. Read files from filesystem                                  │
│ 3. Extract text (pdfplumber/PyPDF2 or AWS Textract)          │
│ 4. Call OpenAI API for classification                          │
│ 5. Determine routing (INBOX vs ARCHIVE)                        │
│ 6. Build result object with metadata                           │
│ 7. Update Supabase: status='completed', result={...}          │
│ 8. Clean up files from filesystem                             │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Updates database
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Supabase Database                                               │
│ - status: 'completed'                                           │
│ - progress: 100                                                 │
│ - result: {                                                     │
│     "total_files": 2,                                           │
│     "inbox_count": 1,                                           │
│     "archive_count": 1,                                        │
│     "results": [                                                │
│       {                                                         │
│         "filename": "invoice.pdf",                              │
│         "routing": "INBOX",                                    │
│         "channel": "BANKING_FINANCIAL",                        │
│         "topic_type": "invoice",                               │
│         "urgency": "medium",                                   │
│         "deadline": "2024-02-15"                               │
│       },                                                        │
│       {                                                         │
│         "filename": "newsletter.pdf",                          │
│         "routing": "ARCHIVE"                                   │
│       }                                                         │
│     ]                                                           │
│   }                                                             │
└─────────────────────────────────────────────────────────────────┘


3. STATUS CHECK FLOW
────────────────────
Frontend App
    │
    │ GET /job/{job_id}
    │ Headers: X-User-ID: user-123
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Inbox Main API                                                  │
│ - Queries Supabase for job                                      │
│ - Returns job status and results                               │
└─────────────────────────────────────────────────────────────────┘
    │
    │ SELECT * FROM inbox_jobs WHERE id=job_id
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Supabase Database                                               │
│ Returns: Job with status and results                           │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Returns JSON response
    ▼
Frontend App
    │ Receives: {status, progress, result, ...}
    │ Displays results to user
```

### Component Interactions

**Request Flow (Classification):**
1. **Frontend → API**: Frontend sends document upload request (`POST /classify-documents-async`)
2. **API → Database**: API creates job record in Supabase
3. **API → Filesystem**: API saves files temporarily
4. **API → Frontend**: API returns job_id immediately

**Request Flow (Analysis):**
1. **Frontend → API**: Frontend sends document upload request (`POST /analyze`)
2. **API → Database**: API processes document synchronously
3. **API → Frontend**: API returns analysis results

**Processing Flow (Classification Jobs):**
1. **Worker → Database**: Worker polls for pending jobs (endpoint_type='classify')
2. **Worker → Filesystem**: Worker reads files
3. **Worker → Text Extraction**: Worker extracts text (native or AWS Textract)
4. **Worker → OpenAI**: Worker calls OpenAI API for inbox routing (INBOX vs ARCHIVE)
5. **Worker → Database**: Worker updates job with routing results
6. **Worker → Filesystem**: Worker cleans up files

**Processing Flow (Analysis Jobs):**
1. **Worker → Database**: Worker polls for pending jobs (endpoint_type='analyze')
2. **Worker → Filesystem**: Worker reads files
3. **Worker → Text Extraction**: Worker extracts text (native or AWS Textract)
4. **Worker → OpenAI**: Worker calls OpenAI API for topic-aware analysis (channel, topic_type, urgency, deadline)
5. **Worker → Database**: Worker updates job with analysis results
6. **Worker → Filesystem**: Worker cleans up files

**Status Flow:**
1. **Frontend → API**: Frontend requests job status
2. **API → Database**: API queries Supabase for job
3. **API → Frontend**: API returns job status and results

### Key Design Principles

1. **Decoupled Architecture**: HTTP requests are decoupled from long-running processing
2. **Stateless Services**: All services are stateless (except temporary file storage)
3. **Database-Backed Queue**: Jobs stored in database (not in-memory)
4. **Immediate Response**: API returns job_id in < 1 second
5. **Durable Storage**: Jobs survive server restarts
6. **Scalable Design**: Can run multiple worker instances
7. **User Isolation**: Jobs filtered by user_id for security

---

## Q1.2: Environments

### Current Environments

#### **Production Environment** ✅
- **Status**: Active and in use
- **Hosting**: 
  - **Main API**: Render (Free Tier)
  - **Worker**: Render (will be deployed - plan TBD)
  - **Database**: Supabase (Production)
- **URL**: https://inboxv3-1.onrender.com
- **Purpose**: Live production system for end users
- **Characteristics**:
  - Free tier limitations (spins down after 15 min inactivity)
  - Cold start ~30 seconds after inactivity
  - No SSH access
  - No scaling options

### Environment Configuration

**Production Environment Variables:**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `OPENAI_API_KEY` - OpenAI API key
- `PYTHON_VERSION=3.11.0` - Python version
- `AWS_ACCESS_KEY_ID` - (Optional) AWS Textract
- `AWS_SECRET_ACCESS_KEY` - (Optional) AWS Textract
- `AWS_REGION` - (Optional) AWS Textract

**Development Environment:**
- Uses `.env` file for local configuration
- Same environment variables as production
- Can run locally with `uvicorn main:app` or `python worker.py`

---

## Q1.3: Current Hosting Platforms

### Platform Inventory

#### 1. **Render** ✅
- **Services Running**:
  - **Inbox Main API** (Web Service) - Active
  - **Inbox Worker** (Background Worker) - Will be deployed
- **Status**: Main API active, Worker pending deployment
- **Plan**: Free Tier (Main API), Worker plan TBD
- **URL**: https://inboxv3-1.onrender.com
- **Region**: Oregon (US West)

#### 2. **Supabase** ✅
- **Services Running**:
  - **PostgreSQL Database** (Managed)
  - **inbox_jobs table** (Job storage)
- **Status**: Active
- **Plan**: Free Tier (or paid, depending on usage)
- **Purpose**: Database for job storage and results

#### 3. **AWS** ⚠️ (Optional)
- **Services Used**:
  - **AWS Textract** (OCR API service)
- **Status**: Optional (service works without it)
- **Usage**: Pay-per-use API calls
- **Purpose**: OCR for scanned documents and images

#### 4. **Railway** ❌
- **Services Running**: None
- **Status**: Not in use
- **Note**: Worker will be deployed on Render instead

####

## Q1.4: Services on Each Platform

### Render Platform

#### **Service 1: Inbox Main API (Web Service)**
- **Service Name**: `inboxv3-1` 
- **Instance ID/Name**: `inboxv3-1.onrender.com`
- **What it does**: 
  - User-facing REST API for document upload and inbox routing
  - Handles HTTP requests from frontend
  - Creates job records in Supabase
  - Returns job status and results
- **Criticality**: **CRITICAL** ⚠️
  - Core service for the entire inbox system
  - Without it, no documents can be uploaded or processed
  - Single point of failure for API access
- **Plan**: Free Tier
- **Limitations**: 
  - Spins down after 15 minutes of inactivity
  - Cold start ~30 seconds
  - No SSH access
  - No scaling options
- **Dependencies**:
  - Supabase (database)
  - OpenAI API (classification)
  - AWS Textract (optional, OCR)

#### **Service 2: Inbox Worker (Background Worker)**
- **Service Name**: `inboxv3-worker` (or similar)
- **Instance ID/Name**: TBD (will be created on Render)
- **What it does**: 
  - Background worker that processes document classification jobs
  - Polls Supabase every 5 seconds for pending jobs
  - Extracts text and calls OpenAI API for classification
  - Updates job results in database
  - Cleans up files after processing
- **Criticality**: **CRITICAL** ⚠️ (when deployed)
  - Required for jobs to be processed
  - Without it, jobs stay in "pending" status forever
- **Plan**: TBD (Free Tier or Starter $7/month)
- **Status**: Code ready, deployment pending on Render
- **Dependencies**:
  - Supabase (database)
  - OpenAI API (classification)
  - AWS Textract (optional, OCR)

### Supabase Platform

#### **Service 1: PostgreSQL Database**
- **Service Name**: Supabase PostgreSQL Database
- **Instance ID**: Supabase project (managed)
- **What it does**: 
  - Stores job records in `inbox_jobs` table
  - Stores job status, progress, and results
  - Provides query interface for job status
  - User ID-based job filtering
- **Criticality**: **CRITICAL** ⚠️
  - All job data stored here
  - Jobs would be lost without it
  - Required for worker to process jobs
- **Plan**: Free Tier (or paid, depending on usage)
- **Dependencies**: None (managed service)

#### **Service 2: inbox_jobs Table**
- **Service Name**: `inbox_jobs` table in Supabase
- **What it does**: 
  - Stores job metadata (id, user_id, status, progress)
  - Stores file metadata (paths, sizes, formats)
  - Stores processing results (routing decisions, analysis)
- **Criticality**: **CRITICAL** ⚠️
  - Core data structure for job queue
  - Required for worker to find and process jobs
- **Schema**: See `supabase_migration.sql`

### AWS Platform

#### **Service 1: AWS Textract (OCR API)**
- **Service Name**: AWS Textract
- **Instance ID**: API service (no instance)
- **What it does**: 
  - OCR (Optical Character Recognition) for scanned documents
  - Text extraction from images (PNG, JPG, JPEG)
  - Multilingual text recognition
  - Fallback when native extraction fails
- **Criticality**: **IMPORTANT** (not critical)
  - Service works without it (for digital PDFs/DOCX)
  - Required only for scanned documents and images
  - Optional dependency (graceful fallback)
- **Plan**: Pay-per-use (API calls)
- **Cost**: Per-page pricing (first 1,000 pages/month free if applicable)
- **Dependencies**: None (external API)

### Railway Platform

#### **Service 1: None**
- **Status**: Not used
- **Note**: Worker will be deployed on Render instead

### Summary Table

| Platform | Service Name | What It Does | Criticality | Status |
|----------|-------------|--------------|-------------|--------|
| **Render** | Inbox Main API | REST API for document upload/routing | **CRITICAL** | ✅ Active |
| **Render** | Inbox Worker | Background job processing | **CRITICAL** | ⏳ Pending (will deploy) |
| **Supabase** | PostgreSQL Database | Job storage and results | **CRITICAL** | ✅ Active |
| **Supabase** | inbox_jobs table | Job queue data structure | **CRITICAL** | ✅ Active |
| **AWS** | Textract (OCR) | OCR for scanned documents | **IMPORTANT** | ⚠️ Optional |

### Criticality Definitions

- **CRITICAL**: System cannot function without this service
- **IMPORTANT**: System works but with reduced functionality
- **EXPERIMENTAL**: Not essential, testing/optional feature

### Service Dependencies

```
Inbox Main API (Render)
    ├── Depends on: Supabase Database (CRITICAL)
    ├── Depends on: OpenAI API (CRITICAL)
    └── Depends on: AWS Textract (IMPORTANT, optional)

Inbox Worker (Render - pending)
    ├── Depends on: Supabase Database (CRITICAL)
    ├── Depends on: OpenAI API (CRITICAL)
    └── Depends on: AWS Textract (IMPORTANT, optional)

Supabase Database
    └── No dependencies (managed service)

AWS Textract
    └── No dependencies (external API)
```

---

## Additional Notes

### Deployment Status

- **Production**: Main API deployed on Render, Worker will be deployed on Render
- **Development**: Local development possible
- **Staging**: Not set up

### Future Considerations

1. **Worker Deployment**: Deploy to Render (Free Tier or Starter $7/month)
2. **Upgrade Services**: Consider Render Starter plan for always-on operation (both API and Worker)
3. **Staging Environment**: Set up staging environment for testing
4. **Monitoring**: Add monitoring/alerting for critical services
5. **Scaling**: Plan for horizontal scaling if needed

### Cost Summary

- **Render**: Free tier (Main API), Worker plan TBD
- **Supabase**: Free tier (or paid based on usage)
- **OpenAI**: Pay-per-use (API calls)
- **AWS Textract**: Pay-per-use (optional, OCR)

---

**Documentation Status**: Complete for current deployment. Questions marked with ❓ need clarification.

