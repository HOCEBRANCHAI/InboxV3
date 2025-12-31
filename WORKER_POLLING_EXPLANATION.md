# Worker Polling & Update Mechanism

## How It Works

### 1. **Worker Polls for NEW Jobs Every 5 Seconds**

```python
# worker.py line 370
poll_interval = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5"))  # Default: 5 seconds

while True:
    # Check Supabase for pending jobs
    pending_jobs = get_pending_jobs(limit=10)
    
    if pending_jobs:
        # Process jobs found
        ...
    else:
        # No jobs found, wait 5 seconds before checking again
        await asyncio.sleep(poll_interval)
```

**What this means:**
- Worker checks Supabase every **5 seconds** to see if there are **NEW pending jobs**
- If no jobs found → waits 5 seconds → checks again
- If jobs found → starts processing immediately

---

### 2. **During Processing: Updates Happen After EACH File**

When the worker finds a job and starts processing, it updates the table **much more frequently**:

```python
# worker.py line 170-173
for i, result in enumerate(routing_results):
    # ... process file ...
    
    # Update progress AFTER EACH FILE
    processed = len(results)
    progress = int((processed / total_files) * 100)
    update_job_status(job_id, JobStatus.PROCESSING, progress=progress, processed_files=processed)
```

**What this means:**
- Updates happen **after each file is processed** (not every 5 seconds)
- If you have 10 files, you'll see 10 progress updates
- Progress: 10% → 20% → 30% → ... → 100%

---

## Complete Timeline Example

Let's say you submit 5 files at `12:00:00`:

```
12:00:00 - Job created in Supabase
           status: "pending"
           progress: 0

12:00:05 - Worker polls Supabase (first check after 5 seconds)
           ✅ Finds pending job
           Starts processing
           Updates: status="processing", progress=0

12:00:06 - File 1 processed
           Updates: progress=20%, processed_files=1

12:00:07 - File 2 processed
           Updates: progress=40%, processed_files=2

12:00:08 - File 3 processed
           Updates: progress=60%, processed_files=3

12:00:09 - File 4 processed
           Updates: progress=80%, processed_files=4

12:00:10 - File 5 processed
           Updates: progress=100%, processed_files=5
           Updates: status="completed", result={...}

12:00:10 - Worker finishes, goes back to polling
           Next poll: 12:00:15 (5 seconds later)
```

---

## Key Points

### ✅ What Happens Every 5 Seconds:
- **Checking for NEW pending jobs** (polling Supabase)

### ✅ What Happens During Processing:
- **Progress updates after EACH file** (real-time updates)
- **Final result update** when all files done

### ✅ Update Frequency:
- **Polling interval**: 5 seconds (configurable via `WORKER_POLL_INTERVAL_SECONDS`)
- **Progress updates**: After each file (could be every 1-2 seconds if files process quickly)

---

## Configuration

You can change the polling interval:

```bash
# In .env file or environment variable
WORKER_POLL_INTERVAL_SECONDS=3  # Poll every 3 seconds instead of 5
```

**Recommendations:**
- **Too fast** (1 second): Wastes database queries, higher load
- **Too slow** (30 seconds): Jobs wait longer before processing starts
- **Default (5 seconds)**: Good balance

---

## Visual Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Worker Loop                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Every 5 seconds:                                        │
│  ┌─────────────────────────────────────┐                │
│  │ 1. Query Supabase:                  │                │
│  │    SELECT * FROM inbox_jobs         │                │
│  │    WHERE status = 'pending'         │                │
│  └─────────────────────────────────────┘                │
│           │                                              │
│           ├─ No jobs? → Wait 5 seconds → Repeat         │
│           │                                              │
│           └─ Jobs found? → Process immediately          │
│                            │                             │
│                            ▼                             │
│              ┌─────────────────────────┐                  │
│              │  Process Job            │                  │
│              │                         │                  │
│              │  For each file:         │                  │
│              │  - Extract text          │                  │
│              │  - Call OpenAI API      │                  │
│              │  - Update progress ✅   │                  │
│              │                         │                  │
│              │  After all files:       │                  │
│              │  - Update: completed ✅  │                  │
│              │  - Store result ✅       │                  │
│              └─────────────────────────┘                  │
│                            │                             │
│                            └─→ Back to polling           │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Summary

**Your understanding is partially correct:**

✅ **Worker checks for NEW jobs every 5 seconds** (polling)

✅ **But updates happen DURING processing** (after each file, not every 5 seconds)

**So:**
- **Polling frequency**: Every 5 seconds (to find new jobs)
- **Update frequency**: After each file (real-time progress)

This gives you:
- Fast job pickup (max 5 second delay)
- Real-time progress updates (see progress as files complete)
- Efficient polling (not too frequent, not too slow)

