# Worker Updates Table - Complete Flow

## ✅ Yes! Worker Processes AND Updates Table

The worker does **both**:
1. **Processes** the files (OCR + AI analysis)
2. **Updates** the Supabase table with progress and results

---

## Step-by-Step: What Worker Does

### Step 1: Worker Finds Job
```python
# worker.py line 375
pending_jobs = get_pending_jobs(limit=10)  # Query Supabase
```

**Table State:**
```
inbox_jobs table:
  id: abc-123
  status: "pending"  ← Worker found this
  progress: 0
  result: NULL
```

---

### Step 2: Worker Starts Processing
```python
# worker.py line 65
update_job_status(job_id, JobStatus.PROCESSING, progress=0)
```

**Table Updated:**
```
inbox_jobs table:
  id: abc-123
  status: "processing"  ← ✅ UPDATED by worker
  progress: 0
  result: NULL
```

---

### Step 3: Worker Processes Each File
```python
# worker.py line 173
# After each file is processed:
update_job_status(
    job_id, 
    JobStatus.PROCESSING, 
    progress=progress,           # 20%, 40%, 60%...
    processed_files=processed   # 1, 2, 3...
)
```

**Table Updates (Example with 5 files):**
```
After File 1:
  status: "processing"
  progress: 20%        ← ✅ UPDATED
  processed_files: 1 ← ✅ UPDATED

After File 2:
  status: "processing"
  progress: 40%        ← ✅ UPDATED
  processed_files: 2 ← ✅ UPDATED

After File 3:
  status: "processing"
  progress: 60%        ← ✅ UPDATED
  processed_files: 3 ← ✅ UPDATED

... and so on
```

---

### Step 4: Worker Completes Job
```python
# worker.py line 189
update_job_status(
    job_id, 
    JobStatus.COMPLETED, 
    result=final_result,  # All results stored here
    progress=100
)
```

**Table Updated:**
```
inbox_jobs table:
  id: abc-123
  status: "completed"  ← ✅ UPDATED by worker
  progress: 100        ← ✅ UPDATED by worker
  result: {            ← ✅ UPDATED by worker
    "total_files": 5,
    "successful": 4,
    "failed": 1,
    "results": [...]
  }
```

---

## Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE TABLE                           │
│                  (inbox_jobs)                               │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │
                          │ Updates
                          │
┌─────────────────────────────────────────────────────────────┐
│                    WORKER PROCESS                           │
│                                                              │
│  1. Poll Supabase: "Any pending jobs?"                      │
│     └─→ Finds job with status="pending"                     │
│                                                              │
│  2. Update: status="processing" ✅                          │
│                                                              │
│  3. Process File 1                                          │
│     └─→ Update: progress=20%, processed_files=1 ✅         │
│                                                              │
│  4. Process File 2                                          │
│     └─→ Update: progress=40%, processed_files=2 ✅         │
│                                                              │
│  5. Process File 3                                          │
│     └─→ Update: progress=60%, processed_files=3 ✅         │
│                                                              │
│  6. Process File 4                                          │
│     └─→ Update: progress=80%, processed_files=4 ✅         │
│                                                              │
│  7. Process File 5                                          │
│     └─→ Update: progress=100%, processed_files=5 ✅          │
│                                                              │
│  8. Update: status="completed", result={...} ✅             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Locations

### Where Worker Updates Table:

1. **Start Processing** (line 65):
   ```python
   update_job_status(job_id, JobStatus.PROCESSING, progress=0)
   ```

2. **After Each File** (line 173):
   ```python
   update_job_status(job_id, JobStatus.PROCESSING, 
                    progress=progress, 
                    processed_files=processed)
   ```

3. **When Complete** (line 189):
   ```python
   update_job_status(job_id, JobStatus.COMPLETED, 
                    result=final_result, 
                    progress=100)
   ```

4. **If Failed** (line 206):
   ```python
   update_job_status(job_id, JobStatus.FAILED, error=error_msg)
   ```

### What `update_job_status()` Does:

```python
# job_service.py line 113
supabase.table("inbox_jobs").update(update_data).eq("id", job_id).execute()
```

This **directly updates the Supabase table** with:
- Status changes
- Progress percentage
- Processed files count
- Final results (JSON)
- Error messages (if failed)

---

## Summary

✅ **Worker polls** Supabase every 5 seconds to find new jobs

✅ **Worker processes** files (OCR + AI analysis)

✅ **Worker updates** Supabase table:
   - Status: `pending` → `processing` → `completed`
   - Progress: `0%` → `20%` → `40%` → ... → `100%`
   - Results: Stored in `result` column when done

✅ **You can check** progress anytime via `GET /job/{job_id}` which reads from the table

---

## Example: Watch a Job Progress

```bash
# 1. Create job
curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@doc1.pdf" -F "files=@doc2.pdf"

# Response: {"job_id": "abc-123", "status": "pending"}

# 2. Check status (worker is processing)
curl http://localhost:8000/job/abc-123

# Response: {
#   "status": "processing",
#   "progress": 50,        ← Worker updated this
#   "processed_files": 1   ← Worker updated this
# }

# 3. Check again (worker finished)
curl http://localhost:8000/job/abc-123

# Response: {
#   "status": "completed",  ← Worker updated this
#   "progress": 100,        ← Worker updated this
#   "result": {...}         ← Worker stored this
# }
```

**All updates come from the worker process!** 🎯

