# Section 3 – Backend Services (APIs, Workers, Document Processing)

## Backend Services Inventory - Inbox Project

### Q3.1: List all backend services we have (Inbox Project Only)

#### 1. **Inbox Main API (User-Facing)** ✅
- **Service Name**: InboxV3 API
- **Purpose**: User-facing REST API for document classification and routing (INBOX vs ARCHIVE)
- **Status**: Deployed and running on Render
- **URL**: https://inboxv3-1.onrender.com

#### 2. **Inbox Document Processing Worker** ✅
- **Service Name**: InboxV3 Worker
- **Purpose**: Background worker that processes document classification/analysis jobs asynchronously
- **Status**: Code ready, deployment pending (needs to be deployed to free platform or Render)

#### 3. **Document Processing / Extraction Service** ✅
- **Service Name**: Text Extraction Service (part of Inbox)
- **Purpose**: OCR and text extraction from various document formats for inbox routing
- **Status**: Integrated into main API and worker
- **Note**: This is a library/utility, not a separate service

---

### Q3.2: For each service, answer:

#### **Service 1: Inbox Main API (User-Facing)**

**Tech Stack:**
- **Language**: Python 3.11
- **Framework**: FastAPI
- **Server**: Gunicorn with Uvicorn workers
- **Database**: Supabase (PostgreSQL)
- **External APIs**: OpenAI API, AWS Textract (optional)

**Hosting:**
- **Platform**: Render
- **URL**: https://inboxv3-1.onrender.com
- **Plan**: **Free Tier** (spins down after 15 minutes of inactivity)
- **Region**: Oregon (US West)
- **Limitations**: 
  - First request after inactivity may be slow (cold start ~30 seconds)
  - Spins down after 15 minutes of inactivity
  - No SSH access
  - No scaling options

**State:**
- **Stateless**: ✅ Yes
  - No in-memory state
  - All state stored in Supabase database
  - Can scale horizontally easily
  - Files stored temporarily on filesystem (cleaned up after processing)

**Key Features:**
- REST API endpoints for document upload and inbox routing
- Document classification (INBOX vs ARCHIVE)
- Document analysis with topic-aware routing
- Async job creation (returns job_id immediately)
- User ID-based job tracking
- Rate limiting (12-25 requests/minute depending on endpoint)
- CORS support
- Health check endpoint

**Inbox-Specific Endpoints:**

**Async Endpoints (Recommended):**
- `POST /classify-documents-async` - Submit documents for inbox classification (INBOX/ARCHIVE routing)
- `GET /job/{job_id}` - Get job status and inbox routing results
- `GET /jobs` - Get all jobs for a user (filter by inbox status)
- `DELETE /job/{job_id}` - Delete a job

**Sync Endpoints (Legacy - May Timeout):**
- `POST /classify-documents` - Synchronous inbox classification (legacy)
- `POST /analyze` - Analyze single document (sync, no routing)

**Utility Endpoints:**
- `GET /health` - Health check

**Inbox Routing Logic:**
- Documents are classified into INBOX or ARCHIVE
- INBOX documents get topic-aware analysis (channel, topic_type, urgency, deadline)
- ARCHIVE documents are stored without analysis
- Routing uses OpenAI GPT-4o with custom prompts (see `prompts.py`)

---

#### **Service 2: Inbox Document Processing Worker**

**Tech Stack:**
- **Language**: Python 3.11
- **Framework**: Standalone Python script with asyncio
- **Database**: Supabase (PostgreSQL)
- **External APIs**: OpenAI API, AWS Textract (optional)

**Hosting:**
- **Platform**: **Render** - Will be deployed on Render
- **Current Status**: Code ready, deployment pending on Render
- **Deployment Plan**: 
  - **Render**: Will deploy as Background Worker service
  - **Plan**: TBD (Free Tier or Starter $7/month)
  - **Note**: Both Main API and Worker will be on Render platform

**State:**
- **Stateless**: ✅ Yes
  - Polls Supabase for pending jobs
  - No local state
  - Can run multiple instances (though not recommended without coordination)

**Key Features:**
- Polls Supabase every 5 seconds for pending inbox jobs
- Processes document classification and routing jobs asynchronously
- Updates job status and inbox routing results in Supabase
- Handles both classification jobs (INBOX/ARCHIVE routing) and analysis jobs
- Automatic file cleanup after processing
- Parallel file processing (5-12 concurrent API calls)

**Inbox Processing Flow:**
1. Polls `inbox_jobs` table for `status='pending'`
2. Marks job as `status='processing'`
3. Reads files from filesystem (stored by web service)
4. Extracts text (using pdfplumber/PyPDF2 or AWS Textract)
5. Calls OpenAI API for inbox classification (INBOX vs ARCHIVE)
6. For INBOX documents: Performs topic-aware analysis (channel, topic_type, urgency, deadline)
7. Updates job with routing results in Supabase
8. Cleans up files from filesystem

---

#### **Service 3: Inbox Document Processing / Extraction Service**

**Tech Stack:**
- **Language**: Python 3.11
- **Libraries**: 
  - `pdfplumber` - PDF text extraction
  - `PyPDF2` - PDF fallback
  - `python-docx` - Word document extraction
  - `pandas` - Excel/CSV extraction
  - `boto3` - AWS Textract integration
  - `Pillow` - Image handling

**Hosting:**
- **Location**: Integrated into Main API and Worker
- **Not a separate service** - Library/utility functions

**State:**
- **Stateless**: ✅ Yes
  - Pure functions
  - No state maintained

**Key Features:**
- Multi-format support: PDF, DOCX, XLSX, CSV, TXT, PNG, JPG, JPEG
- Hybrid extraction approach:
  1. Try native extraction first (pdfplumber, python-docx, etc.)
  2. Fall back to AWS Textract for scanned documents/images
- Handles up to 10MB files for Textract
- Supports password-protected PDFs (via Textract)

**File Paths:**
- `textract_service.py` - Main extraction service
- Used by: `main.py` (lines 293, 397, 572, 1071)
- Used by: `worker.py` (lines 106, 263)

---

## AWS-Specific Backend Usage

### Q3.3: For each AWS-based backend

#### **AWS Textract (OCR Service)**

**Service Type**: AWS API Service (not EC2/ECS/Lambda)

**What it serves:**
- OCR (Optical Character Recognition) for scanned documents
- Text extraction from images (PNG, JPG, JPEG)
- Fallback for PDFs that can't be extracted natively
- Multilingual text extraction

**Why on AWS rather than Railway/PaaS:**
- **Specialized OCR service**: No equivalent in PaaS platforms
- **High accuracy**: AWS Textract provides better OCR than open-source alternatives
- **Multilingual support**: Supports multiple languages out of the box
- **Scalable**: Pay-per-use model, no infrastructure to manage
- **Industry standard**: Reliable and well-supported

**Usage Pattern:**
- Called conditionally (only when native extraction fails or for images)
- Not required for digital PDFs/DOCX files
- Optional dependency (service works without it, but can't process scanned docs)

**Cost Model:**
- Pay-per-page processed
- Only charged when actually used
- Free tier: First 1,000 pages/month (if applicable)

---

### Q3.4: Are any services tightly coupled to AWS?

**Answer: Partially Coupled**

#### **AWS Services Used:**

1. **AWS Textract** (OCR Service)
   - **Purpose**: Document text extraction for scanned documents and images
   - **Coupling Level**: **Optional/Loose** - Service works without it
   - **Code Paths:**
     - `textract_service.py` (lines 22-41, 128-195)
     - Initialized conditionally (only if credentials provided)
     - Used as fallback when native extraction fails

#### **Code Dependencies:**

**File: `textract_service.py`**
- **Function**: `extract_text_from_upload()` (line 43)
- **AWS SDK**: `boto3.client("textract")` (line 29)
- **AWS API Call**: `textract_client.detect_document_text()` (line 140)
- **Error Handling**: `botocore.exceptions.ClientError` (line 157)

**Dependency Chain:**
```
main.py / worker.py
  → textract_service.extract_text_from_upload()
    → boto3.client("textract")
      → AWS Textract API
```

#### **Decoupling Strategy:**

✅ **Already Decoupled:**
- AWS Textract is optional (service works without it)
- Graceful fallback if AWS unavailable
- No hard dependency - checks for credentials before using

**If AWS Textract unavailable:**
- Digital PDFs/DOCX still work (native extraction)
- Scanned PDFs/images will fail (expected behavior)
- Service continues to function for supported formats

---

## Railway Usage

### Q3.5: Which services are currently running on Railway?

**Answer: None currently on Railway**

**Current Deployment:**
- **Inbox Main API**: Render Free Tier (https://inboxv3-1.onrender.com)
- **Inbox Worker**: Not yet deployed (pending deployment decision)

**Railway Consideration:**
- **Status**: Not being used
- **Note**: Worker will be deployed on Render instead (same platform as Main API)
- **Reason**: Keeping all services on one platform (Render) for easier management

**Deployment Decision:**
- **Current Plan**: Deploy worker to Render as Background Worker service
- **Plan**: TBD (Free Tier or Starter $7/month)
- **Benefit**: Both Main API and Worker on same platform (Render)

---

## Scaling & Performance Assumptions

### Q3.6: For Inbox/Document processing, what is the current design?

**Answer: Job/Queue/Worker Pattern** ✅

#### **Current Architecture:**

**Design Pattern**: **Async Job Queue with Database-Backed Storage**

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Request                          │
│  POST /classify-documents-async                          │
│  Files: [doc1.pdf, doc2.pdf, ...]                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Web Service (main.py)                       │
│  - Receives files                                       │
│  - Saves files to filesystem                            │
│  - Creates job record in Supabase                       │
│  - Returns job_id immediately (< 1 second)             │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Writes to
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Supabase Database                           │
│  Table: inbox_jobs                                       │
│  - Stores job metadata                                  │
│  - Stores file paths (not content)                     │
│  - Status: pending → processing → completed             │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Polls every 5 seconds
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Worker Process (worker.py)                  │
│  - Polls for pending jobs                                │
│  - Reads files from filesystem                          │
│  - Extracts text (OCR if needed)                        │
│  - Calls OpenAI API                                     │
│  - Updates job status in Supabase                       │
│  - Cleans up files                                      │
└─────────────────────────────────────────────────────────┘
```

#### **Key Design Decisions:**

1. **NOT Single Synchronous HTTP Request** ❌
   - Original sync endpoints exist but are legacy
   - New async endpoints return immediately

2. **Job/Queue Pattern** ✅
   - Jobs stored in Supabase database (not in-memory)
   - Worker polls database for pending jobs
   - Decouples HTTP request from processing

3. **Why This Design:**
   - **Solves timeout issues**: HTTP returns immediately (< 1 second)
   - **Scalable**: Can run multiple workers
   - **Durable**: Jobs survive server restarts (stored in database)
   - **Observable**: Job status tracked in database
   - **No Cloudflare timeouts**: Immediate response prevents 504 errors

#### **Processing Flow:**

**Synchronous Endpoints (Legacy):**
- `POST /classify-documents` - Processes in HTTP request (can timeout)
- **Status**: Still available but not recommended for production

**Asynchronous Endpoints (Recommended):**
- `POST /classify-documents-async` - Returns job_id immediately
- `GET /job/{job_id}` - Poll for results
- **Status**: Production-ready, handles large batches

---

### Q3.7: For any AWS load balancers or extra EC2 instances

**Answer: None**

#### **Current Infrastructure:**

- **No AWS EC2 instances**
- **No AWS load balancers**
- **No additional AWS infrastructure**

#### **Why No Additional Infrastructure:**

1. **Stateless Design**: 
   - Web service is stateless
   - Can scale horizontally on Render
   - No need for load balancers

2. **Database-Backed Queue**:
   - Uses Supabase (managed PostgreSQL)
   - No need for SQS/SNS
   - No need for Redis/Message Queue

3. **File Storage**:
   - Temporary filesystem storage
   - Files deleted after processing
   - No need for S3

4. **Scaling Strategy**:
   - Render handles scaling automatically
   - Gunicorn workers provide process-level parallelism
   - Worker can be scaled separately

#### **Could This Be Solved by Different Design?**

**Current Design is Optimal** ✅

**Why:**
- ✅ **Job queue in database** - Simple, durable, no extra infrastructure
- ✅ **Stateless services** - Easy to scale
- ✅ **Immediate HTTP response** - No timeout issues
- ✅ **Separate worker** - Can scale independently
- ✅ **No message queue needed** - Database polling is sufficient for current scale

**Alternative Designs Considered (and rejected):**

1. **AWS SQS + Lambda**:
   - ❌ More complex
   - ❌ Vendor lock-in
   - ❌ Current design is simpler and works well

2. **Redis Queue**:
   - ❌ Additional infrastructure
   - ❌ Not needed for current scale
   - ❌ Database polling is sufficient

3. **Synchronous Processing**:
   - ❌ Timeout issues (504 errors)
   - ❌ Poor user experience
   - ❌ Doesn't scale

**Conclusion**: Current design (database-backed job queue) is appropriate and doesn't require additional AWS infrastructure.

---

## Summary

### Services Overview:

| Service | Tech Stack | Hosting | Plan | State | Status |
|---------|-----------|---------|------|-------|--------|
| **Inbox Main API** | Python/FastAPI | Render | Free Tier | Stateless | ✅ Deployed |
| **Inbox Worker** | Python/asyncio | Render | TBD | Stateless | ⏳ Pending (will deploy on Render) |
| **Text Extraction** | Python/boto3 | Integrated | - | Stateless | ✅ Working |

### AWS Usage:

- **AWS Textract**: Optional OCR service (loosely coupled)
- **No EC2/ECS/Lambda**: Not using AWS compute
- **No S3/SQS/SNS**: Using Supabase instead

### Design Pattern:

- ✅ **Async Job Queue** (not synchronous HTTP)
- ✅ **Database-backed** (Supabase, not in-memory)
- ✅ **Stateless services** (easily scalable)
- ✅ **No additional infrastructure needed**

---

## Deployment Status Summary

### Current Deployment:

| Service | Platform | Plan | Status | Notes |
|---------|----------|------|--------|-------|
| **Inbox Main API** | Render | Free Tier | ✅ Deployed | https://inboxv3-1.onrender.com |
| **Inbox Worker** | Render | TBD | ⏳ Pending | Will deploy on Render as Background Worker |

### Deployment Strategy:

**Current Approach:**
- **Main API**: Render Free Tier (working, but spins down after inactivity)
- **Worker**: Will deploy on Render as Background Worker service
  - **Plan**: TBD (Free Tier or Starter $7/month)
  - **Benefit**: Both services on same platform for easier management

**Future Considerations:**
- Upgrade both services to Render Starter ($7/month each) for always-on operation
- Monitor costs and scale based on usage
- Consider Render Standard/Pro plans if needed for higher performance

---

## Additional Questions (Optional)

1. **Performance Metrics**: Any specific performance requirements for inbox processing? (e.g., documents per minute, concurrent users, average processing time per document)

2. **Scaling Plans**: Any plans for horizontal scaling? Multiple worker instances for inbox processing?

3. **Cost Constraints**: Any budget constraints that influenced the inbox architecture decisions?

---

**Documentation is now complete with current deployment information!**

