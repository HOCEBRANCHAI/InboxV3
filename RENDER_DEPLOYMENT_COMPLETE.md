# Complete Render Deployment Guide

## 🚀 Step-by-Step Deployment to Render

This guide covers deploying both the **Web Server** and **Worker Process** to Render.

---

## Prerequisites

1. ✅ **Render Account** - Sign up at https://render.com
2. ✅ **GitHub/GitLab Repository** - Your code must be in a Git repository
3. ✅ **OpenAI API Key** - Get from https://platform.openai.com
4. ✅ **Supabase Account** - Get from https://supabase.com
5. ✅ **AWS Credentials** (Optional) - Only if using Textract OCR

---

## Part 1: Database Setup (Supabase)

### Step 1.1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Fill in:
   - **Name**: `inboxv3` (or your choice)
   - **Database Password**: (save this!)
   - **Region**: Choose closest to you
4. Wait 2-3 minutes for project to be ready

### Step 1.2: Run Database Migration

1. In Supabase dashboard, click **"SQL Editor"**
2. Click **"New query"**
3. Open `supabase_migration.sql` from your project
4. **Copy ALL contents** and paste into SQL Editor
5. Click **"Run"** (or `Ctrl+Enter`)
6. Verify table was created:
   - Go to **"Table Editor"**
   - You should see `inbox_jobs` table

### Step 1.3: Get Supabase Credentials

1. In Supabase dashboard, click **"Settings"** → **"API"**
2. Copy these values:
   - **Project URL** (looks like: `https://xxxxx.supabase.co`)
   - **Service Role Key** (starts with `eyJ...` - keep this secret!)

---

## Part 2: Deploy Web Server to Render

### Step 2.1: Connect Repository

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your Git repository:
   - **GitHub/GitLab**: Authorize Render
   - Select your repository
   - Click **"Connect"**

### Step 2.2: Configure Web Service

**Basic Settings:**
- **Name**: `inboxv3-api` (or your choice)
- **Environment**: `Python 3`
- **Region**: Choose closest to users
- **Branch**: `main` (or your default branch)
- **Root Directory**: (leave empty if root)

**Build & Start:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: 
  ```bash
  gunicorn main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 3600 --keep-alive 300 --max-requests 1000 --max-requests-jitter 50 --worker-connections 1000 --preload --graceful-timeout 30
  ```
- **Health Check Path**: `/health`

### Step 2.3: Set Environment Variables

Click **"Advanced"** → **"Add Environment Variable"** and add:

#### Required Variables:

```bash
# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key-here

# Supabase (REQUIRED for job storage)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key

# Port (auto-set by Render, but good to have)
PORT=8000
```

#### Optional Variables (with defaults):

```bash
# OpenAI
OPENAI_MODEL=gpt-4o

# Server
GUNICORN_WORKERS=4
MAX_FILE_SIZE_MB=100
MAX_TOTAL_SIZE_MB=2000
MAX_FILES_PER_REQUEST=30
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120

# CORS (IMPORTANT for production!)
ALLOWED_ORIGINS=https://yourfrontend.com,https://app.yourfrontend.com
# ⚠️ Do NOT use * in production!

# AWS Textract (only if using OCR)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
```

### Step 2.4: Deploy

1. Click **"Create Web Service"**
2. Render will:
   - Clone your repository
   - Install dependencies
   - Start the server
3. Wait 2-5 minutes for first deployment
4. Check logs for any errors

---

## Part 3: Deploy Worker Process to Render

### Step 3.1: Create Background Worker

1. In Render dashboard, click **"New +"** → **"Background Worker"**
2. Connect same repository:
   - Select your repository
   - Same branch as web service

### Step 3.2: Configure Worker

**Basic Settings:**
- **Name**: `inboxv3-worker` (or your choice)
- **Environment**: `Python 3`
- **Region**: Same as web service
- **Branch**: `main`

**Build & Start:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python worker.py`

### Step 3.3: Set Environment Variables

**Copy ALL environment variables from Web Service:**
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `AWS_ACCESS_KEY_ID` (if using)
- `AWS_SECRET_ACCESS_KEY` (if using)
- `AWS_REGION` (if using)

**Worker-Specific:**
```bash
# Worker polling interval (optional)
WORKER_POLL_INTERVAL_SECONDS=5

# Request timeout (optional)
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
```

### Step 3.4: Deploy Worker

1. Click **"Create Background Worker"**
2. Worker will start polling Supabase for jobs
3. Check logs to verify it's running

---

## Part 4: Verify Deployment

### Step 4.1: Check Web Service

1. Go to your web service in Render dashboard
2. Click on service name
3. Check **"Logs"** tab for any errors
4. Visit: `https://your-service-name.onrender.com/health`
5. Should see: `{"status": "ok", "timestamp": ...}`

### Step 4.2: Check Worker

1. Go to your worker in Render dashboard
2. Check **"Logs"** tab
3. Should see: `Worker Process Starting` and polling messages

### Step 4.3: Test API

```bash
# Health check
curl https://your-service-name.onrender.com/health

# Test async endpoint
curl -X POST https://your-service-name.onrender.com/classify-documents-async \
  -H "X-User-ID: test-user-123" \
  -F "files=@test.pdf"

# Check job status
curl https://your-service-name.onrender.com/job/{job_id} \
  -H "X-User-ID: test-user-123"
```

---

## Part 5: Using render.yaml (Alternative)

If you prefer infrastructure-as-code:

### Step 5.1: Update render.yaml

I'll create an updated `render.yaml` that includes both web service and worker.

### Step 5.2: Deploy via Blueprint

1. Push `render.yaml` to your repository
2. In Render dashboard: **"New +"** → **"Blueprint"**
3. Connect repository
4. Render will detect `render.yaml` and create both services
5. Set secrets in dashboard (OPENAI_API_KEY, SUPABASE_URL, etc.)

---

## Environment Variables Summary

### Required for Web Service:

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `OPENAI_API_KEY` | OpenAI API key | https://platform.openai.com |
| `SUPABASE_URL` | Supabase project URL | Supabase Dashboard → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | Supabase Dashboard → Settings → API |

### Required for Worker:

Same as Web Service (both need Supabase access)

### Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model |
| `GUNICORN_WORKERS` | `4` | Number of web workers |
| `WORKER_POLL_INTERVAL_SECONDS` | `5` | Worker polling interval |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins (set in production!) |

---

## Architecture on Render

```
┌─────────────────────────────────────────┐
│         Render Platform                  │
├─────────────────────────────────────────┤
│                                          │
│  ┌─────────────────┐                    │
│  │  Web Service    │                    │
│  │  (main.py)      │                    │
│  │                 │                    │
│  │  - Receives     │                    │
│  │    requests     │                    │
│  │  - Creates jobs │                    │
│  │  - Returns      │                    │
│  │    job_id       │                    │
│  └────────┬────────┘                    │
│           │                             │
│           │ Writes to                   │
│           ▼                             │
│  ┌─────────────────┐                    │
│  │   Supabase      │                    │
│  │   Database      │                    │
│  │                 │                    │
│  │  - Stores jobs   │                    │
│  │  - Stores        │                    │
│  │    results       │                    │
│  └────────┬────────┘                    │
│           │                             │
│           │ Polls for                   │
│           │ pending jobs                │
│           ▼                             │
│  ┌─────────────────┐                    │
│  │  Background     │                    │
│  │  Worker         │                    │
│  │  (worker.py)    │                    │
│  │                 │                    │
│  │  - Processes    │                    │
│  │    jobs         │                    │
│  │  - Updates      │                    │
│  │    results      │                    │
│  └─────────────────┘                    │
│                                          │
└─────────────────────────────────────────┘
```

---

## Troubleshooting

### Web Service Won't Start

1. **Check logs** in Render dashboard
2. **Verify environment variables** are set:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. **Check build logs** for dependency errors
4. **Verify** `requirements.txt` is correct

### Worker Won't Start

1. **Check logs** - should see "Worker Process Starting"
2. **Verify Supabase credentials** are set
3. **Check** worker can connect to Supabase
4. **Verify** `worker.py` file exists in repository

### Jobs Not Processing

1. **Check worker logs** - is it polling?
2. **Verify Supabase connection** from worker
3. **Check** `inbox_jobs` table exists
4. **Verify** jobs are being created (check Supabase table)

### Database Errors

1. **Run migration** in Supabase SQL Editor
2. **Verify** `user_id` column exists (if using)
3. **Check** Supabase service role key is correct
4. **Verify** table permissions

### CORS Errors

1. **Set `ALLOWED_ORIGINS`** to your frontend domain
2. **Format**: `https://domain1.com,https://domain2.com` (no spaces)
3. **Don't use `*`** in production
4. **Restart** web service after changing

---

## Cost Estimation

### Render Pricing:

- **Free Tier**: 
  - Web service spins down after 15 min inactivity
  - Background workers not available on free tier
- **Starter Plan**: ~$7/month per service
  - Web service: $7/month
  - Background worker: $7/month
  - **Total**: ~$14/month
- **Standard Plan**: ~$25/month per service (better performance)

### Other Costs:

- **OpenAI**: Pay-per-use (check pricing)
- **Supabase**: Free tier available, then ~$25/month
- **AWS Textract**: Pay-per-page (if using)

---

## Security Checklist

- ✅ **Never commit secrets** - Use Render environment variables
- ✅ **Restrict CORS** - Set `ALLOWED_ORIGINS` to specific domains
- ✅ **Use HTTPS** - Render provides automatically
- ✅ **Rate Limiting** - Already configured
- ✅ **File Size Limits** - Configured via env vars
- ✅ **Supabase Service Role Key** - Keep secret, never expose to frontend

---

## Monitoring

1. **Render Dashboard**:
   - View logs for both services
   - Monitor resource usage
   - Set up alerts

2. **Supabase Dashboard**:
   - Monitor database usage
   - Check job table
   - View query performance

3. **Application Logs**:
   - Check Render logs for errors
   - Monitor job processing times
   - Track API usage

---

## Next Steps After Deployment

1. ✅ **Test all endpoints** with your frontend
2. ✅ **Monitor logs** for first few days
3. ✅ **Set up alerts** for service downtime
4. ✅ **Configure CORS** for your frontend domain
5. ✅ **Monitor costs** (OpenAI, AWS, Render)

---

## Quick Reference

### Web Service URL:
```
https://your-service-name.onrender.com
```

### API Endpoints:
- Health: `GET /health`
- Classify: `POST /classify-documents-async`
- Analyze: `POST /analyze-multiple-async`
- Get Job: `GET /job/{job_id}`
- Get All Jobs: `GET /jobs` (requires X-User-ID header)

### Important Files:
- `main.py` - Web server
- `worker.py` - Background worker
- `job_service.py` - Database operations
- `supabase_migration.sql` - Database schema
- `render.yaml` - Infrastructure config
- `Procfile` - Process definitions

---

## Support

- **Render Docs**: https://render.com/docs
- **Render Community**: https://community.render.com
- **Supabase Docs**: https://supabase.com/docs
- **Check logs** in Render dashboard for errors

---

## Summary Checklist

Before deploying:
- [ ] Code pushed to Git repository
- [ ] Supabase project created
- [ ] Database migration run
- [ ] Supabase credentials copied
- [ ] OpenAI API key ready
- [ ] AWS credentials ready (if using Textract)

Deployment:
- [ ] Web service created and configured
- [ ] Environment variables set
- [ ] Web service deployed successfully
- [ ] Background worker created
- [ ] Worker environment variables set
- [ ] Worker deployed successfully

After deployment:
- [ ] Health check passes
- [ ] Worker logs show polling
- [ ] Test API endpoint works
- [ ] Jobs are being processed
- [ ] CORS configured for frontend

**You're all set!** 🚀

