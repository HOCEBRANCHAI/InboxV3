# Run Worker Locally While Web Service is on Render

## Setup

### Step 1: Install Dependencies Locally

```bash
pip install -r requirements.txt
```

### Step 2: Set Environment Variables

Create or update your `.env` file with:

```bash
# Supabase (REQUIRED)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key

# OpenAI (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key

# Optional
WORKER_POLL_INTERVAL_SECONDS=5
REQUEST_TIMEOUT_SECONDS=1800
PER_FILE_TIMEOUT_SECONDS=120
OPENAI_MODEL=gpt-4o

# AWS (if using Textract)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
```

### Step 3: Run Worker

```bash
python worker.py
```

The worker will:
- Connect to Supabase
- Poll for pending jobs
- Process jobs created by your Render web service
- Update results in Supabase

### Step 4: Keep It Running

- Keep the terminal open
- Worker will run continuously
- Press `Ctrl+C` to stop

---

## Architecture

```
┌─────────────────────────────────────────┐
│         Render (Free Tier)               │
│  ┌─────────────────┐                    │
│  │  Web Service    │                    │
│  │  (main.py)      │                    │
│  │  - Receives     │                    │
│  │    requests     │                    │
│  │  - Creates jobs │                    │
│  └────────┬────────┘                    │
└───────────┼──────────────────────────────┘
            │
            │ Writes to
            ▼
┌─────────────────────────────────────────┐
│         Supabase Database                │
│  ┌─────────────────┐                    │
│  │  inbox_jobs     │                    │
│  │  table          │                    │
│  └────────┬────────┘                    │
└───────────┼──────────────────────────────┘
            │
            │ Polls for jobs
            ▼
┌─────────────────────────────────────────┐
│      Your Local Machine                  │
│  ┌─────────────────┐                    │
│  │  Worker        │                    │
│  │  (worker.py)   │                    │
│  │  - Processes   │                    │
│  │    jobs        │                    │
│  │  - Updates     │                    │
│  │    results     │                    │
│  └─────────────────┘                    │
└─────────────────────────────────────────┘
```

---

## Pros & Cons

### Pros:
- ✅ **Free** - No cost for worker
- ✅ **Good for testing** - Test locally before deploying
- ✅ **Full control** - Easy to debug and monitor

### Cons:
- ❌ **Must keep computer on** - Worker stops if computer sleeps
- ❌ **Not scalable** - Only one worker instance
- ❌ **Not production-ready** - For development/testing only

---

## Production Recommendation

For production, use **Render Starter Plan ($7/month)** for the worker:
- Always running
- Automatic restarts
- Better reliability
- Can scale if needed

---

## Quick Start

1. **Copy `.env` file** (you already have it)
2. **Run**: `python worker.py`
3. **Keep terminal open**
4. **Test** by creating a job via Render web service

That's it! Your local worker will process jobs from Render web service. 🚀

