# Setup Guide - Job-Based Architecture

## 🎯 What We've Done

We've refactored from an **in-memory, web-server-based** approach to a **database-backed, worker-based** architecture.

### ❌ Old Approach (Removed)
- Jobs stored in memory (`jobs = {}`)
- Background tasks in web server (`asyncio.create_task()`)
- Jobs lost on restart
- Single process doing everything

### ✅ New Approach (Current)
- Jobs stored in **Supabase database** (durable)
- **Separate worker process** handles processing
- Jobs survive restarts
- Web server and worker are independent

---

## 🏗️ Architecture Overview

```
┌─────────────┐
│   Client    │ Uploads files
└──────┬──────┘
       │
       │ POST /classify-documents-async
       ▼
┌─────────────────────┐
│   Web Server        │
│   (main.py)         │
│                     │
│   1. Validates files│
│   2. Creates job    │──┐
│      in Supabase    │  │
│   3. Stores files   │  │
│   4. Returns job_id │  │
│      (< 1 second)   │  │
└─────────────────────┘  │
                         │
                         │ Writes to database
                         ▼
              ┌──────────────────┐
              │   Supabase DB    │
              │   inbox_jobs      │
              │   table           │
              │                   │
              │ status: 'pending' │
              └─────────┬──────────┘
                        │
                        │ Worker polls every 5 seconds
                        │ SELECT * WHERE status='pending'
                        ▼
              ┌──────────────────┐
              │  Worker Process  │
              │  (worker.py)     │
              │                   │
              │  1. Gets job      │
              │  2. Processes     │
              │     files         │
              │  3. Updates DB    │
              │     status        │
              └──────────────────┘
```

---

## 📋 What You Need to Do

### Step 1: Set Up Supabase Database (5 minutes)

1. **Go to Supabase Dashboard**
   - https://supabase.com/dashboard
   - Create a new project (or use existing)

2. **Run the Migration**
   - Go to SQL Editor in Supabase
   - Copy contents of `supabase_migration.sql`
   - Paste and run it
   - This creates the `inbox_jobs` table

3. **Get Your Credentials**
   - Go to Project Settings → API
   - Copy:
     - **Project URL** (e.g., `https://xxxxx.supabase.co`)
     - **Service Role Key** (secret key, not anon key)

### Step 2: Update Environment Variables

Add these to your `.env` file and Render environment:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Existing variables (keep these)
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o
# ... other existing vars
```

### Step 3: Deploy Web Server (Same as Before)

**On Render:**
1. Your existing web service runs `main.py`
2. It will automatically use Supabase when you add the env vars
3. No code changes needed - just add environment variables

**Command:** (already in your Procfile)
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker ...
```

### Step 4: Deploy Worker Process (NEW!)

**On Render:**
1. Create a **NEW service** (not web service)
2. Type: **Background Worker** or **Shell Script**
3. Command: `python worker.py`
4. Add same environment variables (especially Supabase keys)

**Or use Railway:**
- Create a new service
- Command: `python worker.py`
- Add environment variables

**Or run locally:**
```bash
python worker.py
```

---

## 🔄 How It Works (Step by Step)

### 1. Client Uploads Files

```bash
POST /classify-documents-async
Files: [file1.pdf, file2.pdf]
```

### 2. Web Server Creates Job

```python
# In main.py
job_id = create_job(endpoint_type="classify", total_files=2)
store_file_data(job_id, file_data)
return {"job_id": job_id, "status": "pending"}
```

**What happens:**
- Job inserted into Supabase `inbox_jobs` table
- File data stored in database
- Returns job_id immediately (< 1 second)

### 3. Worker Picks Up Job

```python
# In worker.py (runs continuously)
while True:
    pending_jobs = get_pending_jobs()  # SELECT from Supabase
    for job in pending_jobs:
        await process_classify_job(job)  # Process files
    await asyncio.sleep(5)  # Poll every 5 seconds
```

**What happens:**
- Worker queries Supabase for `status='pending'` jobs
- Gets job and file data
- Processes files (OCR + OpenAI)
- Updates job status in database

### 4. Client Checks Status

```bash
GET /job/{job_id}
```

**What happens:**
- Web server queries Supabase for job
- Returns current status, progress, results

---

## 📁 File Structure

```
.
├── main.py                    # Web server (FastAPI)
├── worker.py                  # Worker process (NEW)
├── job_service.py             # Supabase operations (NEW)
├── supabase_migration.sql     # Database schema (NEW)
├── openai_service.py          # OpenAI API
├── textract_service.py         # Text extraction
├── prompts.py                 # AI prompts
├── requirements.txt           # Dependencies (updated)
└── ARCHITECTURE.md            # Architecture docs (NEW)
```

---

## 🚀 Quick Start Checklist

- [ ] **Step 1:** Create Supabase project
- [ ] **Step 2:** Run `supabase_migration.sql` in Supabase SQL editor
- [ ] **Step 3:** Get Supabase URL and Service Role Key
- [ ] **Step 4:** Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to environment variables
- [ ] **Step 5:** Deploy web server (existing service, just add env vars)
- [ ] **Step 6:** Deploy worker process (new service, runs `python worker.py`)
- [ ] **Step 7:** Test by uploading files to `/classify-documents-async`
- [ ] **Step 8:** Check job status at `/job/{job_id}`

---

## 🧪 Testing

### 1. Test Web Server

```bash
# Health check
curl https://your-api.onrender.com/health

# Create job
curl -X POST https://your-api.onrender.com/classify-documents-async \
  -F "files=@test.pdf"
```

**Expected:** Returns `job_id` immediately

### 2. Test Worker

**Check logs:**
- Worker should show: "Worker Process Starting"
- Should show: "Found X pending job(s)"
- Should show: "Processing job {job_id}"

### 3. Test Job Status

```bash
# Check status (use job_id from step 1)
curl https://your-api.onrender.com/job/{job_id}
```

**Expected:** Shows progress, then results when complete

---

## 🔍 Monitoring

### Check Supabase Dashboard

1. Go to Table Editor → `inbox_jobs`
2. See all jobs:
   - `status`: pending, processing, completed, failed
   - `progress`: 0-100
   - `result`: JSON with results (when complete)

### Check Worker Logs

- Render/Railway dashboard shows worker logs
- Look for:
  - "Found X pending job(s)"
  - "Processing job..."
  - "Job completed successfully"

---

## ⚙️ Configuration

### Worker Poll Interval

Set in environment variable:
```bash
WORKER_POLL_INTERVAL_SECONDS=5  # Default: 5 seconds
```

### Supabase Connection

If Supabase is not configured:
- Web server will fail when creating jobs
- Worker will log warnings but continue (no jobs to process)

---

## 🐛 Troubleshooting

### Issue: "Supabase not configured"

**Solution:** Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to environment variables

### Issue: Worker not processing jobs

**Check:**
1. Is worker running? (check logs)
2. Are jobs in database? (check Supabase dashboard)
3. Are jobs status='pending'? (worker only processes pending)

### Issue: Jobs stuck in 'pending'

**Check:**
1. Is worker process running?
2. Check worker logs for errors
3. Verify Supabase connection in worker

### Issue: "Table inbox_jobs does not exist"

**Solution:** Run `supabase_migration.sql` in Supabase SQL editor

---

## 📊 Key Differences

| Aspect | Before | After |
|--------|--------|-------|
| **Storage** | Memory | Supabase database |
| **Processing** | Web server | Separate worker |
| **Durability** | Lost on restart | Survives restarts |
| **Scalability** | Single instance | Multiple workers possible |
| **Observability** | Logs only | Database + logs |

---

## ✅ Success Criteria

You'll know it's working when:

1. ✅ Web server returns `job_id` immediately
2. ✅ Jobs appear in Supabase `inbox_jobs` table
3. ✅ Worker logs show "Processing job..."
4. ✅ Job status updates from 'pending' → 'processing' → 'completed'
5. ✅ Results available via `/job/{job_id}` endpoint

---

## 🎯 Summary

**The Approach:**
1. **Web Server** = Fast, stateless, creates jobs
2. **Database** = Durable storage, survives restarts
3. **Worker** = Long-running, processes jobs, updates database

**What You Do:**
1. Set up Supabase (5 min)
2. Add environment variables
3. Deploy web server (existing)
4. Deploy worker (new service)

**Result:**
- Robust, scalable, observable job system
- No more in-memory storage
- Proper separation of concerns

---

## 📚 Additional Resources

- **Architecture Details:** See `ARCHITECTURE.md`
- **Database Schema:** See `supabase_migration.sql`
- **Code:** See `job_service.py` and `worker.py`

Need help? Check the troubleshooting section or review the architecture docs!

