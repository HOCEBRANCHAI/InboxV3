# Postman Testing Guide

## Complete Guide to Test Your API in Postman

**Your API URL:** `https://inboxv3-1.onrender.com`

---

## Setup Postman

### Step 1: Import Collection (Optional)

1. Open Postman
2. Click "Import" button
3. Create a new collection called "InboxV3 API"

---

## Endpoint 1: Health Check

### Request Setup:
- **Method:** `GET`
- **URL:** `https://inboxv3-1.onrender.com/health`

### Headers:
(No headers needed)

### Expected Response:
```json
{
  "status": "ok",
  "timestamp": 1767262236.8721662
}
```

---

## Endpoint 2: Classify Documents (Async)

### Request Setup:
- **Method:** `POST`
- **URL:** `https://inboxv3-1.onrender.com/classify-documents-async`

### Headers:
```
X-User-ID: test-user-123
```

**How to add header in Postman:**
1. Go to "Headers" tab
2. Click "Add Header"
3. Key: `X-User-ID`
4. Value: `test-user-123` (or your user ID)

### Body:
1. Go to "Body" tab
2. Select **"form-data"**
3. Add key: `files`
4. Change type to **"File"** (dropdown on right)
5. Click "Select Files" and choose your PDF/document

**For multiple files:**
- Add another key: `files` (same name)
- Select another file
- Postman will send both files

### Expected Response:
```json
{
  "job_id": "abc-123-def-456",
  "status": "pending",
  "message": "Job created. Use /job/{job_id} to check status and get results.",
  "total_files": 1,
  "status_endpoint": "/job/abc-123-def-456",
  "estimated_time_seconds": 10
}
```

**Save the `job_id`** - you'll need it for the next request!

---

## Endpoint 3: Check Job Status

### Request Setup:
- **Method:** `GET`
- **URL:** `https://inboxv3-1.onrender.com/job/{job_id}`

**Replace `{job_id}` with the job_id from previous response**

Example: `https://inboxv3-1.onrender.com/job/abc-123-def-456`

### Headers:
```
X-User-ID: test-user-123
```

### Expected Response (Pending):
```json
{
  "job_id": "abc-123-def-456",
  "status": "pending",
  "progress": 0,
  "total_files": 1,
  "processed_files": 0,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Expected Response (Completed):
```json
{
  "job_id": "abc-123-def-456",
  "status": "completed",
  "progress": 100,
  "total_files": 1,
  "processed_files": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:20Z",
  "result": {
    "total_files": 1,
    "successful": 1,
    "failed": 0,
    "inbox_count": 1,
    "archive_count": 0,
    "results": [
      {
        "filename": "document.pdf",
        "routing": "INBOX",
        "channel": "BANKING_FINANCIAL",
        "topic_type": "invoice",
        "status": "success"
      }
    ]
  }
}
```

**Note:** If worker is not deployed, status will stay "pending" forever.

---

## Endpoint 4: Analyze Documents (Async)

### Request Setup:
- **Method:** `POST`
- **URL:** `https://inboxv3-1.onrender.com/analyze-multiple-async`

### Headers:
```
X-User-ID: test-user-123
```

### Body:
1. Go to "Body" tab
2. Select **"form-data"**
3. Add key: `files`
4. Change type to **"File"**
5. Select your document(s)

### Expected Response:
```json
{
  "job_id": "xyz-789-ghi-012",
  "status": "pending",
  "total_files": 1,
  "status_endpoint": "/job/xyz-789-ghi-012",
  "estimated_time_seconds": 15
}
```

---

## Endpoint 5: Get All Jobs for User

### Request Setup:
- **Method:** `GET`
- **URL:** `https://inboxv3-1.onrender.com/jobs`

### Query Parameters:
- **status** (optional): `pending`, `processing`, `completed`, or `failed`
- **limit** (optional): Number of jobs to return (default: 100)

**Example URLs:**
- All jobs: `https://inboxv3-1.onrender.com/jobs`
- Completed only: `https://inboxv3-1.onrender.com/jobs?status=completed`
- Limit 10: `https://inboxv3-1.onrender.com/jobs?limit=10`
- Both: `https://inboxv3-1.onrender.com/jobs?status=completed&limit=10`

**How to add query params in Postman:**
1. Go to "Params" tab
2. Add key: `status`, Value: `completed`
3. Add key: `limit`, Value: `10`

### Headers:
```
X-User-ID: test-user-123
```
**⚠️ This header is REQUIRED for this endpoint!**

### Expected Response:
```json
{
  "user_id": "test-user-123",
  "total_jobs": 5,
  "status_filter": "completed",
  "jobs": [
    {
      "id": "abc-123-def-456",
      "user_id": "test-user-123",
      "status": "completed",
      "progress": 100,
      "total_files": 1,
      "endpoint_type": "classify",
      "created_at": "2024-01-15T10:30:00Z",
      "result": {
        "total_files": 1,
        "successful": 1,
        "results": [...]
      }
    },
    ...
  ]
}
```

---

## Endpoint 6: Delete Job

### Request Setup:
- **Method:** `DELETE`
- **URL:** `https://inboxv3-1.onrender.com/job/{job_id}`

**Replace `{job_id}` with actual job ID**

### Headers:
```
X-User-ID: test-user-123
```

### Expected Response:
```json
{
  "message": "Job abc-123-def-456 deleted"
}
```

---

## Visual Step-by-Step: Upload File in Postman

### Step 1: Create Request
1. Click "New" → "HTTP Request"
2. Set method to `POST`
3. Enter URL: `https://inboxv3-1.onrender.com/classify-documents-async`

### Step 2: Add Header
1. Click "Headers" tab
2. Click "Add Header"
3. Key: `X-User-ID`
4. Value: `test-user-123`

### Step 3: Add File
1. Click "Body" tab
2. Select **"form-data"** (not raw, not x-www-form-urlencoded)
3. Hover over the key field → Click dropdown → Select **"File"**
4. Key: `files`
5. Click "Select Files" → Choose your PDF/document
6. For multiple files: Add another row with key `files` and select another file

### Step 4: Send Request
1. Click "Send" button
2. Wait for response
3. Copy the `job_id` from response

### Step 5: Check Status
1. Create new request: `GET https://inboxv3-1.onrender.com/job/{job_id}`
2. Add header: `X-User-ID: test-user-123`
3. Click "Send"
4. Check `status` field in response

---

## Complete Testing Flow

### Test 1: Health Check
```
GET https://inboxv3-1.onrender.com/health
→ Should return: {"status": "ok", ...}
```

### Test 2: Create Classification Job
```
POST https://inboxv3-1.onrender.com/classify-documents-async
Headers: X-User-ID: test-user-123
Body: form-data, files: [upload PDF]
→ Save job_id from response
```

### Test 3: Check Job Status (Immediately)
```
GET https://inboxv3-1.onrender.com/job/{job_id}
Headers: X-User-ID: test-user-123
→ Should return: status: "pending"
```

### Test 4: Check Job Status (After Worker Processes)
```
GET https://inboxv3-1.onrender.com/job/{job_id}
Headers: X-User-ID: test-user-123
→ Should return: status: "completed" with results
```

### Test 5: Get All Jobs
```
GET https://inboxv3-1.onrender.com/jobs?status=completed
Headers: X-User-ID: test-user-123
→ Should return: List of all completed jobs
```

---

## Common Issues & Solutions

### Issue 1: "400 Bad Request - No files provided"
**Solution:** Make sure you selected "form-data" and added files with key `files`

### Issue 2: "400 Bad Request - X-User-ID header is required"
**Solution:** Add `X-User-ID` header in Headers tab

### Issue 3: Job stays "pending" forever
**Solution:** Worker is not deployed. Deploy worker to process jobs.

### Issue 4: "404 Not Found"
**Solution:** Check the URL is correct and job_id exists

### Issue 5: CORS Error
**Solution:** Set `ALLOWED_ORIGINS` environment variable in Render (for browser testing)

---

## Postman Collection JSON (Import This)

```json
{
  "info": {
    "name": "InboxV3 API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "https://inboxv3-1.onrender.com/health",
          "protocol": "https",
          "host": ["inboxv3-1", "onrender", "com"],
          "path": ["health"]
        }
      }
    },
    {
      "name": "Classify Documents (Async)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "X-User-ID",
            "value": "test-user-123",
            "type": "text"
          }
        ],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "files",
              "type": "file",
              "src": []
            }
          ]
        },
        "url": {
          "raw": "https://inboxv3-1.onrender.com/classify-documents-async",
          "protocol": "https",
          "host": ["inboxv3-1", "onrender", "com"],
          "path": ["classify-documents-async"]
        }
      }
    },
    {
      "name": "Get Job Status",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "X-User-ID",
            "value": "test-user-123",
            "type": "text"
          }
        ],
        "url": {
          "raw": "https://inboxv3-1.onrender.com/job/:job_id",
          "protocol": "https",
          "host": ["inboxv3-1", "onrender", "com"],
          "path": ["job", ":job_id"],
          "variable": [
            {
              "key": "job_id",
              "value": "abc-123-def-456"
            }
          ]
        }
      }
    },
    {
      "name": "Get All Jobs",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "X-User-ID",
            "value": "test-user-123",
            "type": "text"
          }
        ],
        "url": {
          "raw": "https://inboxv3-1.onrender.com/jobs?status=completed",
          "protocol": "https",
          "host": ["inboxv3-1", "onrender", "com"],
          "path": ["jobs"],
          "query": [
            {
              "key": "status",
              "value": "completed"
            }
          ]
        }
      }
    }
  ]
}
```

**To import:**
1. Copy the JSON above
2. In Postman: Click "Import" → "Raw text"
3. Paste JSON → Click "Import"

---

## Quick Reference Card

| Endpoint | Method | Headers | Body | Response |
|----------|--------|---------|------|----------|
| `/health` | GET | None | None | Status |
| `/classify-documents-async` | POST | X-User-ID | form-data (files) | job_id |
| `/analyze-multiple-async` | POST | X-User-ID | form-data (files) | job_id |
| `/job/{job_id}` | GET | X-User-ID (opt) | None | Job status |
| `/jobs` | GET | X-User-ID (req) | None | All jobs |
| `/job/{job_id}` | DELETE | X-User-ID (opt) | None | Deleted |

---

## Tips

1. **Save requests** in a Postman collection for easy reuse
2. **Use variables** for `job_id` and `user_id` to avoid retyping
3. **Set collection variables:**
   - `base_url`: `https://inboxv3-1.onrender.com`
   - `user_id`: `test-user-123`
4. **Use environment** for different environments (dev, prod)
5. **Check response time** - first request on free tier may be slow (cold start)

---

## Testing Checklist

- [ ] Health check works
- [ ] Can upload file via form-data
- [ ] X-User-ID header is accepted
- [ ] Job is created (returns job_id)
- [ ] Can check job status
- [ ] Can get all jobs for user
- [ ] Worker processes job (if deployed)
- [ ] Results are returned when completed

---

**Your API is ready to test!** 🚀

Start with the health check, then try uploading a document!

