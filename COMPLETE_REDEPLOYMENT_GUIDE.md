# Complete Redeployment Guide - Web Service + Worker

This guide will help you redeploy **both** the web service and worker service on Render from scratch.

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- ✅ **Render account** (free tier is fine)
- ✅ **GitHub repository** with your code pushed
- ✅ **Supabase credentials**:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- ✅ **OpenAI API key**: `OPENAI_API_KEY`
- ✅ **Database migration** completed (if not done, see `supabase_migration.sql`)

---

## 🚀 Step 1: Delete Existing Services (Fresh Start)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. **Delete the existing worker service**:
   - Click on your worker service
   - Go to **Settings** → Scroll down → Click **"Delete Background Worker"**
   - Confirm deletion
3. **Delete the existing web service** (optional, but recommended for clean start):
   - Click on your web service
   - Go to **Settings** → Scroll down → Click **"Delete Web Service"**
   - Confirm deletion

> **Note**: You can keep the web service if it's working. Only delete if you want a completely fresh start.

---

## 🚀 Step 2: Deploy Web Service

### 2.1 Create New Web Service

1. In Render Dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub repository:
   - Select **"HOCEBRANCHAI / InboxV3"**
   - Branch: **`main`**
3. Configure the service:
   - **Name**: `inboxv3-api` (or any name you prefer)
   - **Region**: `Virginia (US East)` (or your preferred region)
   - **Branch**: `main`
   - **Root Directory**: Leave empty (unless your code is in a subdirectory)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: 
     ```
     gunicorn main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 3600 --keep-alive 300 --max-requests 1000 --max-requests-jitter 50 --worker-connections 1000 --preload --graceful-timeout 30
     ```
   - **Instance Type**: `Starter` (free tier)

### 2.2 Set Environment Variables (Web Service)

Click **"Environment"** tab and add these variables:

**Required:**
```
PYTHON_VERSION=3.11.0
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Optional (but recommended):**
```
GUNICORN_WORKERS=4
MAX_FILE_SIZE_MB=100
MAX_TOTAL_SIZE_MB=2000
MAX_FILES_PER_REQUEST=30
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
OPENAI_MODEL=gpt-4o
ALLOWED_ORIGINS=https://your-frontend-domain.com
```

**Optional (if using AWS Textract):**
```
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
```

### 2.3 Deploy Web Service

1. Click **"Create Web Service"**
2. Wait for build to complete (3-5 minutes)
3. Check logs for: `Your service is live 🎉`
4. Test the health endpoint:
   ```
   https://your-service-name.onrender.com/health
   ```

---

## 🚀 Step 3: Deploy Worker Service

### 3.1 Create New Background Worker

1. In Render Dashboard, click **"New +"** → **"Background Worker"**
2. Connect your GitHub repository:
   - Select **"HOCEBRANCHAI / InboxV3"**
   - Branch: **`main`**
3. Configure the service:
   - **Name**: `inboxv3-worker` (or any name you prefer)
   - **Region**: `Virginia (US East)` (same as web service)
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python worker.py` ⚠️ **NO EXTRA SPACES!**
   - **Instance Type**: `Starter` (free tier)

### 3.2 Set Environment Variables (Worker)

Click **"Environment"** tab and add these variables:

**Required (same as web service):**
```
PYTHON_VERSION=3.11.0
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Optional (but recommended):**
```
WORKER_POLL_INTERVAL_SECONDS=5
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
OPENAI_MODEL=gpt-4o
```

**Optional (if using AWS Textract):**
```
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
```

### 3.3 Deploy Worker Service

1. Click **"Create Background Worker"**
2. Wait for build to complete (3-5 minutes)
3. **IMPORTANT**: Check the logs immediately after deployment

---

## ✅ Step 4: Verify Deployment

### 4.1 Check Web Service

1. Open: `https://your-service-name.onrender.com/docs`
2. Test `/health` endpoint → Should return `{"status": "healthy"}`
3. Check logs → Should see: `Application startup complete`

### 4.2 Check Worker Service

1. Go to **Worker Service** → **Logs** tab
2. Look for these messages:
   ```
   ================================================================================
   Worker Process Starting
   Process ID: [some number]
   ================================================================================
   Supabase client initialized successfully
   Found 0 pending job(s)
   ```
3. If you see errors, see **Troubleshooting** section below

### 4.3 Test End-to-End

1. **Create a test job** (using Swagger UI or curl):
   ```bash
   curl -X POST https://your-service-name.onrender.com/classify-documents-async \
     -H "X-User-ID: test-user-123" \
     -F "files=@test.pdf"
   ```
   Response should include: `{"job_id": "..."}`

2. **Check worker logs** (within 5 seconds):
   - Should see: `Found 1 pending job(s)`
   - Should see: `Processing job [job_id]...`
   - Should see: `Job [job_id] completed successfully`

3. **Check job status**:
   ```bash
   curl https://your-service-name.onrender.com/job/[job_id]
   ```
   Should return job status and results

---

## 🔧 Troubleshooting

### Issue 1: Worker Build Fails with Pandas Error

**Error**: `error: too few arguments to function '_PyLong_AsByteArray'`

**Solution**:
1. Verify `runtime.txt` exists with: `python-3.11.0`
2. Verify `requirements.txt` has: `pandas>=2.2.0` (not `==2.1.4`)
3. Verify environment variable: `PYTHON_VERSION=3.11.0`
4. Redeploy

### Issue 2: Worker Shows "Your service is live" but No Logs

**Possible causes**:
- Worker is crashing silently
- Missing environment variables
- Supabase connection issue

**Solution**:
1. Check **Logs** tab → Scroll to bottom
2. Look for error messages
3. Verify all required environment variables are set
4. Check Supabase credentials are correct

### Issue 3: Worker Not Processing Jobs

**Symptoms**:
- Worker logs show: `Found 0 pending job(s)` (but jobs exist)
- Jobs stuck in `pending` status

**Solution**:
1. **Check Supabase connection**:
   - Worker logs should show: `Supabase client initialized successfully`
   - If not, check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`

2. **Check job status in Supabase**:
   - Go to Supabase Dashboard → Table Editor → `inbox_jobs`
   - Verify jobs have `status = 'pending'`
   - Verify `user_id` matches (if filtering by user)

3. **Check worker logs**:
   - Look for any error messages
   - Check if worker is polling: `Found X pending job(s)`

4. **Create a test job**:
   - Use Swagger UI or curl to create a job
   - Immediately check worker logs (within 5 seconds)
   - Should see: `Found 1 pending job(s)`

### Issue 4: "Supabase credentials not found"

**Solution**:
1. Go to **Worker Service** → **Environment** tab
2. Verify these are set:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. Make sure there are **no extra spaces** in the values
4. Click **"Save Changes"** and redeploy

### Issue 5: Worker Crashes Immediately

**Solution**:
1. Check **Logs** tab for error messages
2. Common issues:
   - Missing Python dependencies → Check `requirements.txt`
   - Import errors → Check `worker.py` imports
   - Environment variable issues → Check all required vars are set

---

## 📝 Quick Reference: Environment Variables

### Web Service Required:
```
PYTHON_VERSION=3.11.0
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
```

### Worker Service Required:
```
PYTHON_VERSION=3.11.0
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
```

### Both Services (Same Values):
- `SUPABASE_URL` → Same Supabase project
- `SUPABASE_SERVICE_ROLE_KEY` → Same service role key
- `OPENAI_API_KEY` → Same OpenAI key

---

## 🎯 Success Criteria

Your deployment is successful when:

✅ **Web Service**:
- Health endpoint returns `{"status": "healthy"}`
- Swagger UI loads at `/docs`
- Can create jobs via API

✅ **Worker Service**:
- Logs show: `Worker Process Starting`
- Logs show: `Supabase client initialized successfully`
- Logs show: `Found X pending job(s)` (even if 0)
- Processes jobs within 5-10 seconds of creation

---

## 📞 Next Steps

1. **Monitor logs** for both services
2. **Test with real files** to ensure end-to-end flow works
3. **Set up notifications** in Render (optional) to get alerts on failures
4. **Consider upgrading** to paid tier if you need:
   - No cold starts
   - Better performance
   - More resources

---

## 🔗 Related Documentation

- `RENDER_DEPLOYMENT_COMPLETE.md` - Detailed deployment guide
- `FRONTEND_API_GUIDE.md` - API usage for frontend developers
- `WORKER_TROUBLESHOOTING_GUIDE.md` - Advanced troubleshooting

---

**Last Updated**: 2026-01-02


