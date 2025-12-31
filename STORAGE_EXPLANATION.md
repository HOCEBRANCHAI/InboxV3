# Where Results Are Stored

## Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE DATABASE                        │
│                  (inbox_jobs table)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Column          │  What's Stored                            │
│  ────────────────┼──────────────────────────────────────────│
│  id              │  Job UUID (primary key)                   │
│  status          │  pending → processing → completed/failed │
│  progress        │  0 → 100 (percentage)                    │
│  result          │  ✅ FINAL RESULTS STORED HERE (JSONB)    │
│  error           │  Error message (if failed)               │
│  file_data       │  File metadata (paths, not content)      │
│  total_files     │  Number of files in job                   │
│  processed_files │  Number of files processed                │
│  created_at      │  Job creation timestamp                   │
│  updated_at      │  Last update timestamp                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              FILESYSTEM (Temporary Storage)                  │
│         {tempdir}/inbox_jobs/{job_id}/                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  • Original uploaded files stored here                       │
│  • Files are DELETED after processing completes              │
│  • Only used during processing, not for results              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Complete Flow

### 1. **Job Creation** (`POST /classify-documents-async`)
```
User uploads files
    ↓
Files saved to: {tempdir}/inbox_jobs/{job_id}/
    ↓
Job created in Supabase:
  - status: "pending"
  - file_data: [{"filename": "...", "file_path": "...", ...}]
  - result: NULL
```

### 2. **Worker Processing** (`worker.py`)
```
Worker polls Supabase for pending jobs
    ↓
Worker reads files from disk: {tempdir}/inbox_jobs/{job_id}/
    ↓
Worker processes files (OCR + AI analysis)
    ↓
Worker builds result object:
  {
    "total_files": 5,
    "successful": 4,
    "failed": 1,
    "inbox_count": 3,
    "archive_count": 1,
    "results": [
      {
        "filename": "doc1.pdf",
        "routing": "INBOX",
        "channel": "BANKING_FINANCIAL",
        ...
      },
      ...
    ],
    "processing_time": 45.2
  }
    ↓
Worker updates Supabase:
  - status: "completed"
  - progress: 100
  - result: {above JSON object} ✅ STORED HERE
    ↓
Worker deletes files from disk (cleanup)
```

### 3. **Retrieving Results** (`GET /job/{job_id}`)
```
User calls GET /job/{job_id}
    ↓
API reads from Supabase inbox_jobs table
    ↓
Returns result from database:
  {
    "job_id": "...",
    "status": "completed",
    "progress": 100,
    "result": { ... }  ← Retrieved from Supabase
  }
```

## Result Structure

### For Classification Jobs (`/classify-documents-async`):
```json
{
  "total_files": 5,
  "successful": 4,
  "failed": 1,
  "inbox_count": 3,
  "archive_count": 1,
  "results": [
    {
      "filename": "invoice.pdf",
      "routing": "INBOX",
      "channel": "BANKING_FINANCIAL",
      "topic_type": "invoice",
      "topic_title": "Monthly Invoice",
      "urgency": "medium",
      "deadline": "2024-02-15",
      "authority": "vendor",
      "reasoning": "...",
      "status": "success"
    },
    ...
  ],
  "processing_time": 45.2
}
```

### For Analysis Jobs (`/analyze-multiple-async`):
```json
{
  "total_files": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "filename": "document.pdf",
      "analysis": {
        "summary": "...",
        "key_points": [...],
        "action_items": [...],
        ...
      },
      "status": "success",
      "extracted_text": "First 1000 chars..."
    },
    ...
  ],
  "processing_time": 30.5
}
```

## Key Points

1. **Results are stored in Supabase** (`inbox_jobs.result` column as JSONB)
2. **Files are stored temporarily on disk** (deleted after processing)
3. **Results persist in database** until you delete the job
4. **You can retrieve results anytime** using `GET /job/{job_id}`
5. **Results include all processing details** (routing, analysis, errors, etc.)

## How to Access Results

### Via API:
```bash
curl http://localhost:8000/job/{job_id}
```

### Directly from Supabase:
```sql
SELECT id, status, result 
FROM inbox_jobs 
WHERE id = '{job_id}';
```

### Delete Results:
```bash
curl -X DELETE http://localhost:8000/job/{job_id}
```

## Summary

✅ **Results = Stored in Supabase database** (`inbox_jobs.result` column)  
✅ **Files = Temporary disk storage** (deleted after processing)  
✅ **Results persist** until you delete the job record  
✅ **Access via API** or directly query Supabase

