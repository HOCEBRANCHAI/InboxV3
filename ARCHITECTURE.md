# Job-Based Architecture - Correct Implementation

## Overview

**HTTP is not suitable for long-running document processing**, so we decouple requests from execution using a job-based architecture with Supabase storage and a separate worker process.

This architecture separates concerns:
- **Web Server**: Handles HTTP requests, creates jobs, returns immediately
- **Worker Process**: Polls database, processes jobs, updates status
- **Database (Supabase)**: Stores jobs durably, survives restarts

---

## Architecture Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ POST /classify-documents-async
       │ (files)
       ▼
┌─────────────────────┐
│   Web Server        │
│   (FastAPI)         │
│                     │
│   1. Create job     │──┐
│      in Supabase    │  │
│   2. Store files    │  │
│   3. Return job_id  │  │
│      immediately    │  │
└─────────────────────┘  │
                         │
                         │ Writes to
                         ▼
              ┌──────────────────┐
              │   Supabase DB     │
              │   inbox_jobs      │
              │   table           │
              └─────────┬──────────┘
                        │
                        │ Worker polls
                        │ for pending jobs
                        ▼
              ┌──────────────────┐
              │  Worker Process  │
              │  (worker.py)     │
              │                   │
              │  1. Poll DB       │
              │  2. Process files │
              │  3. Update status │
              └──────────────────┘
```

---

## Components

### 1. Web Server (`main.py`)

**Responsibilities:**
- Handle HTTP requests
- Validate files
- Create job records in Supabase
- Store file data
- Return job_id immediately

**Does NOT:**
- Process files
- Run background tasks
- Store jobs in memory

**Key Code:**
```python
@app.post("/classify-documents-async")
async def classify_documents_async(request: Request, files: List[UploadFile]):
    # Read and encode files
    file_data = [encode_file(file) for file in files]
    
    # Create job in Supabase (not memory!)
    job_id = create_job(endpoint_type="classify", total_files=len(files))
    
    # Store file data in Supabase
    store_file_data(job_id, file_data)
    
    # Return immediately - worker will process
    return {"job_id": job_id, "status": "pending"}
```

### 2. Worker Process (`worker.py`)

**Responsibilities:**
- Poll Supabase for pending jobs
- Process files (OCR + LLM)
- Update job status in database
- Handle errors gracefully

**Runs as:**
- Separate process (not in web server)
- Separate Railway/Render service
- Can scale independently

**Key Code:**
```python
async def worker_loop():
    while True:
        # Poll for pending jobs
        pending_jobs = get_pending_jobs(limit=10)
        
        # Process jobs
        for job in pending_jobs:
            await process_classify_job(job)
        
        await asyncio.sleep(5)  # Poll interval
```

### 3. Database Service (`job_service.py`)

**Responsibilities:**
- Supabase client initialization
- Job CRUD operations
- File data storage/retrieval

**Key Functions:**
- `create_job()` - Insert job into Supabase
- `update_job_status()` - Update job progress/status
- `get_job()` - Retrieve job by ID
- `get_pending_jobs()` - Get jobs for worker to process
- `store_file_data()` - Store file metadata and content

### 4. Supabase Table (`inbox_jobs`)

**Schema:**
```sql
CREATE TABLE inbox_jobs (
    id UUID PRIMARY KEY,
    document_id UUID,
    batch_id UUID,
    endpoint_type TEXT,  -- 'classify' or 'analyze'
    status TEXT,         -- 'pending', 'processing', 'completed', 'failed'
    progress INTEGER,
    total_files INTEGER,
    processed_files INTEGER,
    result JSONB,
    error TEXT,
    file_data JSONB,    -- File metadata + base64 content
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

---

## Data Flow

### 1. Job Creation (HTTP Request)

```
Client → Web Server → Supabase
  │         │            │
  │         │            └─> INSERT INTO inbox_jobs
  │         │                 (status='pending')
  │         │
  │         └─> Return job_id
  │
  └─< {job_id, status: "pending"}
```

**Time:** < 1 second

### 2. Job Processing (Worker)

```
Worker → Supabase → Process Files → Supabase
  │         │            │            │
  │         │            │            └─> UPDATE status='processing'
  │         │            │
  │         └─< SELECT * FROM inbox_jobs
  │            WHERE status='pending'
  │
  └─> Loop: Poll every 5 seconds
```

**Time:** Variable (depends on file count/complexity)

### 3. Status Check (HTTP Request)

```
Client → Web Server → Supabase
  │         │            │
  │         │            └─> SELECT * FROM inbox_jobs
  │         │                 WHERE id=job_id
  │         │
  │         └─> Return job status
  │
  └─< {status, progress, result}
```

**Time:** < 1 second

---

## Key Differences from Previous Implementation

| Aspect | ❌ Previous (Wrong) | ✅ Current (Correct) |
|--------|-------------------|---------------------|
| **Storage** | In-memory dict | Supabase table |
| **Job Creation** | `jobs[job_id] = {...}` | `INSERT INTO inbox_jobs` |
| **Processing** | `asyncio.create_task()` | Separate worker process |
| **Durability** | Lost on restart | Survives restarts |
| **Scalability** | Single instance | Multiple workers possible |
| **Framing** | "Cloudflare timeout fix" | "Correct architecture" |

---

## Deployment

### Web Server (Render/Railway)

**Service:** `web`
**Command:** `gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker`
**Environment Variables:**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`
- (other existing vars)

### Worker Process (Render/Railway)

**Service:** `worker` (separate service)
**Command:** `python worker.py`
**Environment Variables:**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`
- `WORKER_POLL_INTERVAL_SECONDS=5`
- (other existing vars)

---

## Benefits

✅ **Durable** - Jobs survive server restarts  
✅ **Scalable** - Can run multiple workers  
✅ **Observable** - Jobs visible in database  
✅ **Correct** - Proper separation of concerns  
✅ **Portable** - Not tied to single process  
✅ **Architecturally Sound** - HTTP for requests, workers for processing  

---

## Setup Instructions

1. **Create Supabase Table:**
   - Run `supabase_migration.sql` in Supabase SQL editor

2. **Set Environment Variables:**
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

3. **Deploy Web Server:**
   - Deploy `main.py` as web service

4. **Deploy Worker:**
   - Deploy `worker.py` as separate worker service

5. **Test:**
   - Submit files via `/classify-documents-async`
   - Check job status via `/job/{job_id}`
   - Verify worker processes jobs

---

## Summary

This architecture correctly separates:
- **HTTP layer** (web server) - Fast, stateless, returns immediately
- **Processing layer** (worker) - Long-running, stateful, updates database
- **Storage layer** (Supabase) - Durable, queryable, observable

This is the **correct** way to handle long-running operations in a web API.

