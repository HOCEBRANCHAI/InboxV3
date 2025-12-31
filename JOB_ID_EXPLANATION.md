# Job ID Explanation: One Request = One Job ID

## ✅ Yes! One Request = One Job ID

**Key Point:** Each API request creates **ONE job ID**, but that job can process **multiple files**.

---

## How It Works

### Example 1: Single File Request

```bash
POST /classify-documents-async
Files: [invoice.pdf]
```

**Result:**
- ✅ Creates **1 job ID** (e.g., `abc-123`)
- ✅ Job contains **1 file**
- ✅ `total_files: 1`

---

### Example 2: Multiple Files in One Request

```bash
POST /classify-documents-async
Files: [invoice.pdf, receipt.pdf, statement.pdf]
```

**Result:**
- ✅ Creates **1 job ID** (e.g., `def-456`)
- ✅ Job contains **3 files**
- ✅ `total_files: 3`
- ✅ All 3 files processed together in the same job

---

## Visual Flow

```
┌─────────────────────────────────────────────────────────┐
│              ONE HTTP REQUEST                           │
│  POST /classify-documents-async                        │
│  Files: [file1.pdf, file2.pdf, file3.pdf]              │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│         Creates ONE Job in Supabase                      │
│                                                          │
│  Job ID: abc-123-def-456                                │
│  ├─ total_files: 3                                       │
│  ├─ file_data: [                                        │
│  │    {filename: "file1.pdf", file_path: "..."},       │
│  │    {filename: "file2.pdf", file_path: "..."},      │
│  │    {filename: "file3.pdf", file_path: "..."}        │
│  │  ]                                                    │
│  └─ status: "pending"                                   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│         Worker Processes ONE Job                         │
│                                                          │
│  Job ID: abc-123-def-456                                │
│  ├─ Processes file1.pdf → Updates progress: 33%        │
│  ├─ Processes file2.pdf → Updates progress: 66%        │
│  ├─ Processes file3.pdf → Updates progress: 100%       │
│  └─ Updates: status="completed", result={...}           │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│         ONE Result for All Files                         │
│                                                          │
│  GET /job/abc-123-def-456                               │
│  Returns:                                                │
│  {                                                       │
│    "job_id": "abc-123-def-456",                         │
│    "status": "completed",                               │
│    "total_files": 3,                                     │
│    "result": {                                           │
│      "results": [                                        │
│        {filename: "file1.pdf", routing: "INBOX", ...},  │
│        {filename: "file2.pdf", routing: "ARCHIVE", ...},│
│        {filename: "file3.pdf", routing: "INBOX", ...}   │
│      ]                                                   │
│    }                                                     │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Code Evidence

### In `main.py` (line 742):

```python
@app.post("/classify-documents-async")
async def classify_documents_async(request: Request, files: List[UploadFile] = File(...)):
    # ... validation ...
    
    # Creates ONE job for ALL files in the request
    job_id = create_job(endpoint_type="classify", total_files=len(files))
    
    # All files saved under this ONE job_id
    for file in files:
        # Save each file to: {tempdir}/inbox_jobs/{job_id}/{filename}
        ...
    
    # Store all file metadata under this ONE job_id
    store_file_data(job_id, file_data)
    
    return {
        "job_id": job_id,  # ONE job ID
        "total_files": len(files)  # But can have multiple files
    }
```

### In `job_service.py` (line 42):

```python
def create_job(endpoint_type: str = "classify", total_files: int = 0) -> str:
    """
    Create a new job in Supabase and return its ID.
    
    Args:
        total_files: Number of files in this job  ← Can be 1 or many
    
    Returns:
        job_id (UUID string)  ← ONE job ID
    """
    # Creates ONE job record in Supabase
    response = supabase.table("inbox_jobs").insert(job_data).execute()
    job_id = response.data[0]["id"]  # ONE unique ID
    return job_id
```

---

## Examples

### Example 1: 5 Files in One Request

```bash
curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf" \
  -F "files=@doc4.pdf" \
  -F "files=@doc5.pdf"
```

**Response:**
```json
{
  "job_id": "abc-123-def-456",  ← ONE job ID
  "status": "pending",
  "total_files": 5,              ← But 5 files
  "status_endpoint": "/job/abc-123-def-456"
}
```

**Later, check status:**
```bash
GET /job/abc-123-def-456
```

**Returns:**
```json
{
  "job_id": "abc-123-def-456",
  "status": "completed",
  "total_files": 5,
  "processed_files": 5,
  "result": {
    "results": [
      {"filename": "doc1.pdf", ...},
      {"filename": "doc2.pdf", ...},
      {"filename": "doc3.pdf", ...},
      {"filename": "doc4.pdf", ...},
      {"filename": "doc5.pdf", ...}
    ]
  }
}
```

---

### Example 2: Multiple Requests = Multiple Job IDs

```bash
# Request 1
POST /classify-documents-async
Files: [file1.pdf, file2.pdf]
→ Job ID: job-001

# Request 2
POST /classify-documents-async
Files: [file3.pdf]
→ Job ID: job-002

# Request 3
POST /classify-documents-async
Files: [file4.pdf, file5.pdf, file6.pdf]
→ Job ID: job-003
```

**Result:**
- ✅ 3 requests = 3 job IDs
- ✅ Each job processes its own files independently
- ✅ Check each job separately: `/job/job-001`, `/job/job-002`, `/job/job-003`

---

## Summary

| Scenario | Job IDs Created | Files per Job |
|----------|----------------|---------------|
| 1 request with 1 file | **1 job ID** | 1 file |
| 1 request with 5 files | **1 job ID** | 5 files |
| 3 requests with 2 files each | **3 job IDs** | 2 files each |

**Key Points:**
- ✅ **One HTTP request** = **One job ID**
- ✅ **One job ID** can process **multiple files**
- ✅ **Multiple requests** = **Multiple job IDs**
- ✅ Each job is tracked independently in Supabase
- ✅ Results for all files in a job are returned together

---

## Why This Design?

**Benefits:**
1. **Simpler API** - One request, one job ID to track
2. **Batch Processing** - Process related files together
3. **Efficient** - Worker processes all files in one job together
4. **Easy Tracking** - One job ID to check status for all files

**Trade-off:**
- If you want separate tracking for each file, make separate requests

---

## Database Structure

In Supabase `inbox_jobs` table:

```sql
id: abc-123-def-456          ← ONE job ID
total_files: 5               ← But 5 files
file_data: [                 ← All files stored here
  {filename: "file1.pdf", ...},
  {filename: "file2.pdf", ...},
  {filename: "file3.pdf", ...},
  {filename: "file4.pdf", ...},
  {filename: "file5.pdf", ...}
]
result: {                    ← Results for all files
  "results": [
    {filename: "file1.pdf", ...},
    {filename: "file2.pdf", ...},
    ...
  ]
}
```

---

## Conclusion

✅ **Your understanding is correct!**

- **One request** = **One job ID**
- That job can contain **multiple files**
- All files in the request are processed together
- Results are returned together for that job

If you need separate job IDs for each file, make separate API requests! 🎯

