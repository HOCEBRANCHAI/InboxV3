# Complete Testing Guide - All Endpoints Explained

## 📋 Overview

This API has **2 types of endpoints**:
1. **Sync Endpoints** - Wait for results (may timeout with Cloudflare)
2. **Async Endpoints** - Return immediately, poll for results (recommended)

---

## 🗺️ Endpoint Map

### Health & Info
- `GET /` - Root endpoint (basic info)
- `GET /health` - Health check

### Single File Processing
- `POST /analyze` - Analyze one file (sync)

### Multiple Files - Sync (May Timeout)
- `POST /analyze-multiple` - Analyze multiple files (sync)
- `POST /classify-documents` - Classify multiple files (sync)

### Multiple Files - Async (Recommended) ⭐
- `POST /classify-documents-async` - Submit files, get job_id
- `POST /analyze-multiple-async` - Submit files, get job_id
- `GET /job/{job_id}` - Check status and get results
- `DELETE /job/{job_id}` - Delete job

---

## 🧪 Testing Flow - Step by Step

### Prerequisites

1. **Start the server:**
   ```bash
   uvicorn main:app --reload
   ```
   Server runs at: `http://localhost:8000`

2. **Have test files ready:**
   - `test1.pdf`, `test2.pdf`, etc.
   - Or any supported format (PDF, DOCX, CSV, XLSX, images)

---

## Test 1: Health Check ✅

**Purpose:** Verify server is running

```bash
# Test root endpoint
curl http://localhost:8000/

# Expected response:
{
  "status": "ok",
  "message": "Document Analysis API",
  "timestamp": 1703930400.0
}

# Test health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "ok",
  "timestamp": 1703930400.0
}
```

**✅ Success:** Both return `"status": "ok"`

---

## Test 2: Single File Analysis (Sync) 📄

**Purpose:** Analyze one document

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@test1.pdf"

# Expected response (takes 5-15 seconds):
{
  "filename": "test1.pdf",
  "analysis": {
    "summary": "...",
    "key_details": {...},
    "required_actions": [...],
    "risk_if_ignored": "..."
  },
  "status": "success",
  "extracted_text": "...",
  "processing_time": 8.5
}
```

**✅ Success:** Returns analysis with `"status": "success"`

**⚠️ Note:** This is sync - waits for result. May timeout with Cloudflare if slow.

---

## Test 3: Multiple Files - Sync Endpoints ⚠️

### 3a. Classify Documents (Sync)

**Purpose:** Route and classify multiple files (INBOX vs ARCHIVE)

```bash
curl -X POST http://localhost:8000/classify-documents \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf" \
  -F "files=@test3.pdf"

# Expected response (takes 30-60 seconds for 3 files):
{
  "total_files": 3,
  "successful_routing": 3,
  "failed_routing": 0,
  "inbox_count": 2,
  "archive_count": 1,
  "routing_results": [
    {
      "filename": "test1.pdf",
      "routing": "INBOX",
      "channel": "TAX",
      "topic_type": "VAT",
      "topic_title": "Q1 2024 VAT",
      "urgency": "HIGH",
      "status": "success"
    },
    ...
  ],
  "channel_summary": {...},
  "status": "success",
  "processing_time": 45.2
}
```

**✅ Success:** Returns routing decisions for all files

**⚠️ Warning:** May timeout with Cloudflare if processing > 100 seconds

### 3b. Analyze Multiple (Sync)

**Purpose:** Full analysis of multiple files (routing + analysis)

```bash
curl -X POST http://localhost:8000/analyze-multiple \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf"

# Expected response (takes 20-40 seconds for 2 files):
{
  "total_files": 2,
  "successful": 2,
  "failed": 0,
  "inbox_count": 1,
  "archive_count": 1,
  "results": [
    {
      "filename": "test1.pdf",
      "routing": "INBOX",
      "channel": "TAX",
      "analysis": {...},
      "status": "success"
    },
    ...
  ],
  "processing_time": 32.5
}
```

**✅ Success:** Returns full analysis for all files

**⚠️ Warning:** May timeout with Cloudflare

---

## Test 4: Multiple Files - Async Endpoints ⭐ (RECOMMENDED)

### 4a. Submit Files for Classification (Async)

**Purpose:** Submit files, get job_id immediately

```bash
# Step 1: Submit files
curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf" \
  -F "files=@test3.pdf"

# Expected response (returns in < 1 second!):
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job created. Use /job/{job_id} to check status and get results.",
  "total_files": 3,
  "status_endpoint": "/job/550e8400-e29b-41d4-a716-446655440000",
  "estimated_time_seconds": 30
}
```

**✅ Success:** Job ID returned immediately (no timeout!)

**📝 Save the `job_id` for next step!**

### 4b. Check Job Status

**Purpose:** Get progress and results

```bash
# Step 2: Check status (replace with your job_id)
curl http://localhost:8000/job/550e8400-e29b-41d4-a716-446655440000

# While processing:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "total_files": 3,
  "processed_files": 1,
  "created_at": 1703930400.0,
  "updated_at": 1703930450.0
}

# When complete:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "total_files": 3,
  "processed_files": 3,
  "result": {
    "total_files": 3,
    "successful_routing": 3,
    "inbox_count": 2,
    "archive_count": 1,
    "routing_results": [...],
    "processing_time": 28.5
  }
}

# If failed:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Job processing failed: ..."
}
```

**✅ Success:** Status updates show progress, results available when complete

**💡 Tip:** Poll every 2-3 seconds until `status` is `"completed"` or `"failed"`

### 4c. Submit Files for Analysis (Async)

**Purpose:** Submit files for full analysis (routing + analysis)

```bash
# Step 1: Submit files
curl -X POST http://localhost:8000/analyze-multiple-async \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf"

# Expected response (returns in < 1 second):
{
  "job_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "Job created. Use /job/{job_id} to check status and get results.",
  "total_files": 2,
  "status_endpoint": "/job/660e8400-e29b-41d4-a716-446655440001",
  "estimated_time_seconds": 30
}
```

**✅ Success:** Job ID returned immediately

**Step 2:** Check status using same method as 4b

### 4d. Delete Job (Cleanup)

**Purpose:** Remove completed job from memory

```bash
curl -X DELETE http://localhost:8000/job/550e8400-e29b-41d4-a716-446655440000

# Expected response:
{
  "message": "Job 550e8400-e29b-41d4-a716-446655440000 deleted"
}
```

**✅ Success:** Job removed (optional cleanup step)

---

## 🔄 Complete Testing Flow Example

### Scenario: Process 5 documents

**Option A: Using Sync Endpoint (May Timeout)**
```bash
# Single request, wait for all results
curl -X POST http://localhost:8000/classify-documents \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf" \
  -F "files=@doc4.pdf" \
  -F "files=@doc5.pdf"

# ⚠️ May timeout if takes > 100 seconds
```

**Option B: Using Async Endpoint (Recommended) ⭐**

```bash
# Step 1: Submit files (returns immediately)
RESPONSE=$(curl -X POST http://localhost:8000/classify-documents-async \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf" \
  -F "files=@doc4.pdf" \
  -F "files=@doc5.pdf")

# Extract job_id (you'll need to parse JSON or use jq)
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# Step 2: Poll for status
while true; do
  STATUS=$(curl -s http://localhost:8000/job/$JOB_ID)
  echo "$STATUS" | jq '.'
  
  # Check if complete
  if echo "$STATUS" | jq -e '.status == "completed"' > /dev/null; then
    echo "✅ Job completed!"
    echo "$STATUS" | jq '.result'
    break
  elif echo "$STATUS" | jq -e '.status == "failed"' > /dev/null; then
    echo "❌ Job failed!"
    echo "$STATUS" | jq '.error'
    break
  fi
  
  # Wait 2 seconds before next poll
  sleep 2
done
```

---

## 📊 Endpoint Comparison

| Endpoint | Response Time | Timeout Risk | Use Case |
|-----------|---------------|-------------|----------|
| `POST /analyze` | 5-15 sec | Low | Single file, quick |
| `POST /classify-documents` | 30-180 sec | ⚠️ High | Multiple files, sync |
| `POST /analyze-multiple` | 20-120 sec | ⚠️ High | Multiple files, sync |
| `POST /classify-documents-async` | < 1 sec | ✅ None | Multiple files, async |
| `POST /analyze-multiple-async` | < 1 sec | ✅ None | Multiple files, async |
| `GET /job/{job_id}` | < 1 sec | ✅ None | Check status |

---

## 🧪 Testing Checklist

### Basic Tests
- [ ] Health check works (`GET /health`)
- [ ] Single file analysis works (`POST /analyze`)
- [ ] Multiple files sync works (`POST /classify-documents`)
- [ ] Async job creation works (`POST /classify-documents-async`)
- [ ] Job status polling works (`GET /job/{job_id}`)
- [ ] Results are returned when complete

### Advanced Tests
- [ ] Process 20+ files with async endpoint
- [ ] Verify progress updates during processing
- [ ] Test error handling (invalid files, missing files)
- [ ] Test job cleanup (`DELETE /job/{job_id}`)
- [ ] Test with different file formats (PDF, DOCX, CSV, images)

### Production Tests
- [ ] Test on Render deployment
- [ ] Verify no 504 timeouts with async endpoints
- [ ] Test with Cloudflare proxy enabled/disabled
- [ ] Monitor processing times

---

## 🐛 Common Issues & Solutions

### Issue: 504 Gateway Timeout

**Problem:** Using sync endpoints with Cloudflare

**Solution:** Use async endpoints instead
```bash
# ❌ Don't use (may timeout):
POST /classify-documents

# ✅ Use instead:
POST /classify-documents-async
```

### Issue: Job not found

**Problem:** Job ID doesn't exist or was deleted

**Solution:** 
- Check job_id is correct
- Jobs are in-memory (lost on server restart)
- For production, use Redis (see docs)

### Issue: Status stuck at "processing"

**Problem:** Background task crashed or server restarted

**Solution:**
- Check server logs
- Job status will show "failed" if error occurred
- Restart server and try again

---

## 📝 Quick Reference

### All Endpoints

```bash
# Health
GET  /health
GET  /

# Single File
POST /analyze

# Multiple Files - Sync
POST /analyze-multiple
POST /classify-documents

# Multiple Files - Async (Recommended)
POST /classify-documents-async
POST /analyze-multiple-async
GET  /job/{job_id}
DELETE /job/{job_id}
```

### Recommended Flow

1. **Submit files** → `POST /classify-documents-async`
2. **Get job_id** → Save from response
3. **Poll status** → `GET /job/{job_id}` every 2-3 seconds
4. **Get results** → When `status: "completed"`
5. **Cleanup** → `DELETE /job/{job_id}` (optional)

---

## 🎯 Testing Script Example

Save as `test_api.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "🧪 Testing Document Analysis API"
echo "================================"

# Test 1: Health check
echo -e "\n1. Testing health endpoint..."
curl -s $BASE_URL/health | jq '.'

# Test 2: Single file
echo -e "\n2. Testing single file analysis..."
curl -s -X POST $BASE_URL/analyze -F "file=@test1.pdf" | jq '.status'

# Test 3: Async job
echo -e "\n3. Testing async job creation..."
RESPONSE=$(curl -s -X POST $BASE_URL/classify-documents-async \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf")

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# Test 4: Poll status
echo -e "\n4. Polling job status..."
for i in {1..10}; do
  STATUS=$(curl -s $BASE_URL/job/$JOB_ID)
  PROGRESS=$(echo $STATUS | jq -r '.progress')
  JOB_STATUS=$(echo $STATUS | jq -r '.status')
  
  echo "Progress: $PROGRESS%, Status: $JOB_STATUS"
  
  if [ "$JOB_STATUS" == "completed" ] || [ "$JOB_STATUS" == "failed" ]; then
    echo $STATUS | jq '.'
    break
  fi
  
  sleep 2
done

echo -e "\n✅ Testing complete!"
```

Run with: `bash test_api.sh`

---

## 📚 More Information

- **Implementation Details:** See `ASYNC_JOB_PATTERN_EXPLAINED.md`
- **Deployment:** See `RENDER_DEPLOYMENT.md`
- **Next Steps:** See `NEXT_STEPS.md`

Happy Testing! 🚀

