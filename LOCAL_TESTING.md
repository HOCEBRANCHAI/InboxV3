# Local Testing Guide

## Prerequisites Check

Before testing, make sure you have:

- [x] Supabase project created
- [x] Table `inbox_jobs` created (via SQL migration)
- [x] Supabase credentials in `.env` file
- [x] All dependencies installed (`pip install -r requirements.txt`)

---

## Step 1: Verify Environment Variables

Check your `.env` file has:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=your-openai-key
```

**Test connection:**
```bash
python -c "from job_service import supabase; print('Supabase connected!' if supabase else 'Supabase not configured')"
```

---

## Step 2: Test Web Server

### Start the Server

```bash
uvicorn main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Test Health Endpoint

In another terminal:
```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status": "ok", "timestamp": 1703930400.0}
```

### Test Job Creation

```bash
curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@test.pdf"
```

**Expected:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job created. Use /job/{job_id} to check status and get results.",
  "total_files": 1,
  "status_endpoint": "/job/550e8400-e29b-41d4-a716-446655440000"
}
```

**Check Supabase:**
- Go to Supabase Dashboard → Table Editor → `inbox_jobs`
- You should see a new row with `status: 'pending'`

---

## Step 3: Test Worker Process

### Start Worker (in separate terminal)

```bash
python worker.py
```

**Expected output:**
```
INFO: ================================================================================
INFO: Worker Process Starting
INFO: Process ID: 12345
INFO: ================================================================================
INFO: Found 1 pending job(s)
INFO: Processing job 550e8400-e29b-41d4-a716-446655440000
```

### Watch Worker Process Jobs

The worker will:
1. Poll Supabase every 5 seconds
2. Find pending jobs
3. Process files
4. Update job status in database

**Check Supabase again:**
- Status should change: `pending` → `processing` → `completed`
- `progress` should update: 0 → 50 → 100
- `result` field should have results when complete

---

## Step 4: Test Full Flow

### Terminal 1: Start Web Server
```bash
uvicorn main:app --reload --port 8000
```

### Terminal 2: Start Worker
```bash
python worker.py
```

### Terminal 3: Test End-to-End

**1. Submit files:**
```bash
curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf"
```

**Save the `job_id` from response**

**2. Check job status:**
```bash
curl http://localhost:8000/job/{job_id}
```

**3. Wait 10-30 seconds, check again:**
```bash
curl http://localhost:8000/job/{job_id}
```

**Expected progression:**
- First check: `"status": "pending"`
- Second check: `"status": "processing", "progress": 50`
- Third check: `"status": "completed", "result": {...}`

---

## Step 5: Verify in Supabase Dashboard

1. Go to Supabase Dashboard
2. Table Editor → `inbox_jobs`
3. You should see:
   - Job records
   - Status updates
   - Progress updates
   - Results in JSON format

---

## Troubleshooting

### Issue: "Supabase not configured"

**Check:**
1. `.env` file exists in project root
2. `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set
3. Restart server/worker after adding env vars

### Issue: "Table inbox_jobs does not exist"

**Solution:**
1. Go to Supabase SQL Editor
2. Run `supabase_migration.sql` again

### Issue: Worker not finding jobs

**Check:**
1. Is worker running? (check terminal output)
2. Are jobs in database? (check Supabase dashboard)
3. Are jobs `status='pending'`? (worker only processes pending)

### Issue: Jobs stuck in 'pending'

**Check:**
1. Is worker process running?
2. Check worker logs for errors
3. Verify Supabase connection in worker

### Issue: Import errors

**Solution:**
```bash
pip install -r requirements.txt
```

---

## Quick Test Script

Save as `test_local.py`:

```python
import requests
import time
import json

BASE_URL = "http://localhost:8000"

print("🧪 Testing Local Setup")
print("=" * 50)

# 1. Health check
print("\n1. Testing health endpoint...")
response = requests.get(f"{BASE_URL}/health")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")

# 2. Create job (you'll need a test file)
print("\n2. Testing job creation...")
# Uncomment when you have a test file:
# with open("test.pdf", "rb") as f:
#     files = {"files": f}
#     response = requests.post(f"{BASE_URL}/classify-documents-async", files=files)
#     job_data = response.json()
#     job_id = job_data["job_id"]
#     print(f"   Job ID: {job_id}")

# 3. Check job status
# print("\n3. Checking job status...")
# for i in range(5):
#     response = requests.get(f"{BASE_URL}/job/{job_id}")
#     status = response.json()
#     print(f"   Check {i+1}: Status={status['status']}, Progress={status.get('progress', 0)}%")
#     if status['status'] in ['completed', 'failed']:
#         break
#     time.sleep(3)

print("\n✅ Testing complete!")
```

Run: `python test_local.py`

---

## Success Indicators

You'll know it's working when:

✅ Web server starts without errors  
✅ Health endpoint returns `{"status": "ok"}`  
✅ Job creation returns `job_id` immediately  
✅ Job appears in Supabase `inbox_jobs` table  
✅ Worker logs show "Found X pending job(s)"  
✅ Worker logs show "Processing job..."  
✅ Job status updates in Supabase  
✅ Results available via `/job/{job_id}` endpoint  

---

## Next Steps After Local Testing

Once local testing works:

1. ✅ Commit all changes to GitHub
2. ✅ Deploy web server to Render (add Supabase env vars)
3. ✅ Deploy worker to Render (new service, same env vars)
4. ✅ Test in production

Good luck with testing! 🚀

