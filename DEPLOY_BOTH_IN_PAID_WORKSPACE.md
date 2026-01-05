# Deploy Both Services in Paid Render Workspace

## 🎯 Overview

Deploy both **web service** and **worker** in a **paid Render workspace** for production reliability.

**Benefits of Paid Plan:**
- ✅ **Always running** (no spinning down after inactivity)
- ✅ **Better performance** (more CPU/memory)
- ✅ **Faster response times**
- ✅ **More reliable** (better uptime)
- ✅ **Better for production**

---

## 💰 Pricing Options

### Recommended Setup

**Option 1: Starter Plan (Recommended)**
- **Web Service:** Free tier (OK for API)
- **Worker:** Starter ($7/month) - **Always running, processes jobs**
- **Total:** ~$7/month

**Option 2: Both Paid (Best Performance)**
- **Web Service:** Starter ($7/month)
- **Worker:** Starter ($7/month)
- **Total:** ~$14/month

**Option 3: Standard Plan (High Traffic)**
- **Web Service:** Standard ($25/month)
- **Worker:** Standard ($25/month)
- **Total:** ~$50/month

---

## 📋 Step-by-Step Deployment

### Step 1: Create/Select Paid Workspace

1. **Go to:** https://dashboard.render.com
2. **Check current workspace:**
   - Look at top-left corner for workspace name
   - If you have a paid workspace, use it
   - If not, you can upgrade later (services can be moved)

3. **Note:** Services in the same workspace share:
   - Environment variables (can be synced)
   - Billing
   - Access control

### Step 2: Deploy Web Service

#### 2.1 Create Web Service

1. **Click "New +"** → **"Web Service"**
2. **Connect repository:**
   - Select: `HOCEBRANCHAI / InboxV3`
   - Click **"Connect"**

#### 2.2 Configure Web Service

**Basic Settings:**
- **Name:** `inboxv3-api` (or your preferred name)
- **Environment:** `Python 3`
- **Region:** `Oregon (US West)` or `Virginia (US East)`
- **Branch:** `main`
- **Root Directory:** (leave empty)

**Build & Start:**
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
  ```

**Instance Type:**
- **Free** (for testing) or **Starter ($7/month)** (for production)

#### 2.3 Set Environment Variables

Click **"Add Environment Variable"** and add:

**Required:**
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
OPENAI_API_KEY=sk-your-openai-api-key
PYTHON_VERSION=3.11.0
```

**Optional (but recommended):**
```bash
ALLOWED_ORIGINS=https://your-frontend-domain.com
MAX_FILE_SIZE_MB=100
MAX_TOTAL_SIZE_MB=2000
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
OPENAI_MODEL=gpt-4o
```

#### 2.4 Deploy Web Service

1. Click **"Create Web Service"**
2. Wait for build (3-5 minutes)
3. **Save the URL:** `https://inboxv3-api.onrender.com` (or your service name)

---

### Step 3: Deploy Background Worker

#### 3.1 Create Background Worker

1. **Click "New +"** → **"Background Worker"** ⚠️ **NOT Web Service!**
2. **Connect repository:**
   - Select: `HOCEBRANCHAI / InboxV3`
   - Click **"Connect"**

#### 3.2 Configure Background Worker

**Basic Settings:**
- **Name:** `inboxv3-worker`
- **Environment:** `Python 3`
- **Region:** **Same as web service** (e.g., `Oregon (US West)`)
- **Branch:** `main`
- **Root Directory:** (leave empty)

**Build & Start:**
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  python worker.py
  ```
  ⚠️ **NO extra spaces!** Just `python worker.py`

**Instance Type:**
- **Starter ($7/month)** - **Recommended for production**
  - Always running
  - Processes jobs continuously
  - No spinning down

#### 3.3 Set Environment Variables

**CRITICAL:** Use **EXACT SAME** values as web service!

Click **"Add Environment Variable"** and add:

**Required (MUST MATCH WEB SERVICE):**
```bash
SUPABASE_URL=https://xxxxx.supabase.co  ← SAME AS WEB SERVICE
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-key  ← SAME AS WEB SERVICE
OPENAI_API_KEY=sk-your-openai-api-key  ← SAME AS WEB SERVICE
PYTHON_VERSION=3.11.0  ← SAME AS WEB SERVICE
```

**Optional (but recommended):**
```bash
WORKER_POLL_INTERVAL_SECONDS=5
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
OPENAI_MODEL=gpt-4o
```

**Pro Tip:** Copy-paste from web service to ensure they match exactly!

#### 3.4 Deploy Background Worker

1. Click **"Create Background Worker"**
2. Wait for build (3-5 minutes)
3. **Check logs immediately**

---

### Step 4: Verify Deployment

#### 4.1 Check Web Service

1. **Open:** `https://inboxv3-api.onrender.com/docs`
2. **Test:** `GET /health` → Should return `{"status": "ok"}`
3. **Check logs:** Should see "Application startup complete"

#### 4.2 Check Background Worker

1. **Go to worker dashboard** → **Logs** tab
2. **Look for:**
   ```
   ✅ "Worker Process Starting"
   ✅ "Supabase client initialized successfully"
   ✅ "Found 0 pending job(s)"
   ```

3. **Should NOT see:**
   ```
   ❌ "No open ports detected"
   ❌ "Port scan timeout"
   ```

#### 4.3 Verify Both in Same Workspace

1. **Check workspace name** (top-left corner)
2. **Both services should be in the same workspace**
3. **Both should show the same workspace name**

---

## 🧪 Test End-to-End

### Step 1: Create Test Job

1. **Go to:** `https://inboxv3-api.onrender.com/docs`
2. **Use:** `POST /classify-documents-async`
3. **Upload a test file**
4. **Get the `job_id`** from response

### Step 2: Watch Worker Logs

1. **Go to worker dashboard** → **Logs** tab
2. **You should see:**
   ```
   INFO:__main__:Found 1 pending job(s)
   INFO:__main__:Processing job {job_id}
   INFO:__main__:Job {job_id} completed successfully
   ```

### Step 3: Check Job Status

```bash
GET https://inboxv3-api.onrender.com/job/{job_id}
```

**Expected:**
```json
{
  "job_id": "...",
  "status": "completed",
  "progress": 100,
  "result": {
    "total_files": 1,
    "successful": 1,
    "results": [...]
  }
}
```

---

## 📋 Deployment Checklist

### Web Service
- [ ] Service type: **Web Service**
- [ ] Start Command: `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
- [ ] Instance Type: Free or Starter ($7/month)
- [ ] Environment variables set
- [ ] Health check works: `/health` returns OK
- [ ] Swagger UI accessible: `/docs`

### Background Worker
- [ ] Service type: **Background Worker** (NOT Web Service!)
- [ ] Start Command: `python worker.py` (no extra spaces)
- [ ] Instance Type: **Starter ($7/month)** (recommended)
- [ ] Environment variables **match web service exactly**
- [ ] Logs show "Worker Process Starting"
- [ ] Logs show "Supabase client initialized successfully"
- [ ] No port errors in logs

### Both Services
- [ ] Both in **same workspace**
- [ ] Both in **same region**
- [ ] `SUPABASE_URL` matches exactly
- [ ] `SUPABASE_SERVICE_ROLE_KEY` matches exactly
- [ ] `OPENAI_API_KEY` matches exactly
- [ ] `PYTHON_VERSION=3.11.0` for both

---

## 💰 Cost Summary

### Recommended Setup (Starter Plan)

| Service | Plan | Cost |
|---------|------|------|
| Web Service | Free | $0/month |
| Worker | Starter | $7/month |
| **Total** | | **$7/month** |

### High Performance Setup

| Service | Plan | Cost |
|---------|------|------|
| Web Service | Starter | $7/month |
| Worker | Starter | $7/month |
| **Total** | | **$14/month** |

### Enterprise Setup

| Service | Plan | Cost |
|---------|------|------|
| Web Service | Standard | $25/month |
| Worker | Standard | $25/month |
| **Total** | | **$50/month** |

---

## 🔍 Troubleshooting

### Worker Not Processing Jobs?

1. **Check service type:** Must be "Background Worker"
2. **Check workspace:** Both services in same workspace?
3. **Check environment variables:** Do they match exactly?
4. **Check logs:** Any errors?

### Jobs Stuck in "Pending"?

1. **Check worker is running:** Look at worker logs
2. **Check Supabase connection:** Logs should show "Supabase client initialized"
3. **Check file paths:** Files should be on Render's filesystem

### Web Service Not Responding?

1. **Check health endpoint:** `/health`
2. **Check logs:** Any startup errors?
3. **Check instance type:** Free tier spins down after inactivity

---

## 🎯 Best Practices

1. **Same workspace:** Both services in same workspace
2. **Same region:** Better performance, lower latency
3. **Matching env vars:** Copy-paste to ensure exact match
4. **Paid worker:** Starter plan ensures always running
5. **Monitor logs:** Check both services regularly
6. **Test regularly:** Create test jobs to verify everything works

---

## 🚀 Next Steps

1. ✅ Deploy web service (Free or Starter)
2. ✅ Deploy background worker (Starter recommended)
3. ✅ Verify both in same workspace
4. ✅ Test with a new job
5. ✅ Monitor logs for both services
6. ✅ Set up monitoring/alerts (optional)

---

## 📚 Reference

- **Complete Redeployment Guide:** `COMPLETE_REDEPLOYMENT_GUIDE.md`
- **Worker Deployment Type Fix:** `FIX_WORKER_DEPLOYMENT_TYPE.md`
- **Workspace Issue Fix:** `WORKER_WORKSPACE_ISSUE_FIX.md`

---

**You're all set! Both services in a paid workspace will give you reliable, production-ready infrastructure.** 🎉

