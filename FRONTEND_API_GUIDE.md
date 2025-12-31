# Frontend API Guide - User ID Integration

## Overview

The backend supports **user-specific job tracking** using a `user_id` passed in the request header. This allows each user to see only their own jobs and results.

---

## How It Works

1. **Frontend sends `X-User-ID` header** with each request
2. **Backend stores `user_id`** with each job in the database
3. **Frontend can fetch jobs** filtered by `user_id`

---

## API Endpoints

### 1. Submit Documents for Classification

**Endpoint:** `POST /classify-documents-async`

**Headers:**
```
X-User-ID: your-unique-user-id-here
```

**Request:**
```bash
curl -X POST http://localhost:8000/classify-documents-async \
  -H "X-User-ID: user-123" \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf"
```

**Response:**
```json
{
  "job_id": "abc-123-def-456",
  "status": "pending",
  "message": "Job created. Use /job/{job_id} to check status and get results.",
  "total_files": 2,
  "status_endpoint": "/job/abc-123-def-456",
  "estimated_time_seconds": 20
}
```

---

### 2. Submit Documents for Analysis

**Endpoint:** `POST /analyze-multiple-async`

**Headers:**
```
X-User-ID: your-unique-user-id-here
```

**Request:**
```bash
curl -X POST http://localhost:8000/analyze-multiple-async \
  -H "X-User-ID: user-123" \
  -F "files=@document.pdf"
```

**Response:**
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

### 3. Get Job Status (Single Job)

**Endpoint:** `GET /job/{job_id}`

**Headers (Optional but Recommended):**
```
X-User-ID: your-unique-user-id-here
```

**Request:**
```bash
curl -X GET http://localhost:8000/job/abc-123-def-456 \
  -H "X-User-ID: user-123"
```

**Response:**
```json
{
  "job_id": "abc-123-def-456",
  "status": "completed",
  "progress": 100,
  "total_files": 2,
  "processed_files": 2,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:20Z",
  "result": {
    "total_files": 2,
    "successful": 2,
    "failed": 0,
    "inbox_count": 1,
    "archive_count": 1,
    "results": [
      {
        "filename": "document1.pdf",
        "routing": "INBOX",
        "channel": "BANKING_FINANCIAL",
        "status": "success"
      },
      {
        "filename": "document2.pdf",
        "routing": "ARCHIVE",
        "status": "success"
      }
    ]
  }
}
```

**Security Note:** If you provide `X-User-ID` header, the backend verifies the job belongs to that user. If it doesn't match, returns 404.

---

### 4. Get All Jobs for User ⭐ **NEW**

**Endpoint:** `GET /jobs`

**Headers (Required):**
```
X-User-ID: your-unique-user-id-here
```

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `processing`, `completed`, `failed`)
- `limit` (optional): Maximum number of jobs to return (default: 100)

**Request Examples:**

```bash
# Get all jobs for user
curl -X GET "http://localhost:8000/jobs" \
  -H "X-User-ID: user-123"

# Get only completed jobs
curl -X GET "http://localhost:8000/jobs?status=completed" \
  -H "X-User-ID: user-123"

# Get pending jobs (limit 10)
curl -X GET "http://localhost:8000/jobs?status=pending&limit=10" \
  -H "X-User-ID: user-123"
```

**Response:**
```json
{
  "user_id": "user-123",
  "total_jobs": 5,
  "status_filter": null,
  "jobs": [
    {
      "id": "abc-123-def-456",
      "user_id": "user-123",
      "status": "completed",
      "progress": 100,
      "total_files": 2,
      "endpoint_type": "classify",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:31:20Z",
      "result": {
        "total_files": 2,
        "successful": 2,
        "results": [...]
      }
    },
    {
      "id": "xyz-789-ghi-012",
      "user_id": "user-123",
      "status": "processing",
      "progress": 50,
      "total_files": 1,
      "endpoint_type": "analyze",
      "created_at": "2024-01-15T11:00:00Z",
      "updated_at": "2024-01-15T11:01:00Z"
    },
    ...
  ]
}
```

---

### 5. Delete Job

**Endpoint:** `DELETE /job/{job_id}`

**Headers (Optional but Recommended):**
```
X-User-ID: your-unique-user-id-here
```

**Request:**
```bash
curl -X DELETE http://localhost:8000/job/abc-123-def-456 \
  -H "X-User-ID: user-123"
```

**Response:**
```json
{
  "message": "Job abc-123-def-456 deleted"
}
```

---

## Frontend Implementation Examples

### JavaScript/TypeScript (Fetch API)

```javascript
// Submit documents
async function submitDocuments(files, userId) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  
  const response = await fetch('http://localhost:8000/classify-documents-async', {
    method: 'POST',
    headers: {
      'X-User-ID': userId  // Your unique user ID
    },
    body: formData
  });
  
  const data = await response.json();
  return data.job_id;
}

// Get all jobs for user
async function getUserJobs(userId, status = null) {
  const url = new URL('http://localhost:8000/jobs');
  if (status) url.searchParams.set('status', status);
  
  const response = await fetch(url, {
    headers: {
      'X-User-ID': userId
    }
  });
  
  return await response.json();
}

// Get single job status
async function getJobStatus(jobId, userId) {
  const response = await fetch(`http://localhost:8000/job/${jobId}`, {
    headers: {
      'X-User-ID': userId
    }
  });
  
  return await response.json();
}
```

### React Example

```jsx
import { useState, useEffect } from 'react';

function DocumentUploader({ userId }) {
  const [jobs, setJobs] = useState([]);
  
  // Submit documents
  const handleSubmit = async (files) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    const response = await fetch('/classify-documents-async', {
      method: 'POST',
      headers: {
        'X-User-ID': userId
      },
      body: formData
    });
    
    const data = await response.json();
    console.log('Job created:', data.job_id);
    
    // Refresh jobs list
    fetchUserJobs();
  };
  
  // Fetch all jobs for user
  const fetchUserJobs = async () => {
    const response = await fetch(`/jobs?limit=50`, {
      headers: {
        'X-User-ID': userId
      }
    });
    
    const data = await response.json();
    setJobs(data.jobs);
  };
  
  useEffect(() => {
    fetchUserJobs();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchUserJobs, 5000);
    return () => clearInterval(interval);
  }, [userId]);
  
  return (
    <div>
      <input type="file" multiple onChange={(e) => handleSubmit(e.target.files)} />
      <div>
        <h3>Your Jobs ({jobs.length})</h3>
        {jobs.map(job => (
          <div key={job.id}>
            <p>Job: {job.id}</p>
            <p>Status: {job.status}</p>
            <p>Progress: {job.progress}%</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Axios Example

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'X-User-ID': 'user-123'  // Set default user ID
  }
});

// Submit documents
async function submitDocuments(files) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  
  const response = await api.post('/classify-documents-async', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  
  return response.data.job_id;
}

// Get all jobs
async function getUserJobs(status = null) {
  const params = status ? { status } : {};
  const response = await api.get('/jobs', { params });
  return response.data;
}
```

---

## User ID Format

**Important:** The `user_id` can be any string that uniquely identifies your user. Examples:

- ✅ `"user-123"`
- ✅ `"john.doe@example.com"`
- ✅ `"550e8400-e29b-41d4-a716-446655440000"` (UUID)
- ✅ `"session-abc123"`
- ✅ Any unique identifier from your UI/authentication system

**Recommendation:** Use a consistent format across your application (e.g., UUID, email, or your internal user ID).

---

## Security Considerations

1. **User ID Verification:**
   - When you provide `X-User-ID` in `GET /job/{job_id}`, the backend verifies the job belongs to that user
   - If the job belongs to a different user, you'll get a 404 error
   - This prevents users from accessing each other's jobs

2. **Required Header:**
   - `GET /jobs` endpoint **requires** `X-User-ID` header
   - Without it, you'll get a 400 error

3. **Optional Header:**
   - Other endpoints accept `X-User-ID` as optional
   - If not provided, jobs are created without `user_id` (accessible to anyone)

---

## Complete Flow Example

```javascript
// 1. User uploads documents
const jobId = await submitDocuments([file1, file2], 'user-123');
// Returns: "abc-123-def-456"

// 2. Poll for job status
const checkStatus = async () => {
  const job = await getJobStatus('abc-123-def-456', 'user-123');
  console.log(`Status: ${job.status}, Progress: ${job.progress}%`);
  
  if (job.status === 'completed') {
    console.log('Results:', job.result);
  } else if (job.status === 'failed') {
    console.error('Error:', job.error);
  }
};

// 3. Get all user's jobs
const allJobs = await getUserJobs('user-123');
console.log(`User has ${allJobs.total_jobs} jobs`);

// 4. Filter by status
const completedJobs = await getUserJobs('user-123', 'completed');
console.log(`Completed: ${completedJobs.jobs.length}`);
```

---

## Error Handling

```javascript
try {
  const response = await fetch('/jobs', {
    headers: { 'X-User-ID': userId }
  });
  
  if (!response.ok) {
    if (response.status === 400) {
      throw new Error('X-User-ID header is required');
    } else if (response.status === 404) {
      throw new Error('Job not found or access denied');
    }
  }
  
  const data = await response.json();
  return data;
} catch (error) {
  console.error('API Error:', error);
  throw error;
}
```

---

## Summary

✅ **Send `X-User-ID` header** with all requests  
✅ **Use `GET /jobs`** to fetch all jobs for a user  
✅ **Use `GET /job/{job_id}`** to check specific job status  
✅ **User ID can be any unique string** from your UI  
✅ **Backend verifies ownership** when user_id is provided  

---

## Quick Reference

| Endpoint | Method | X-User-ID | Purpose |
|----------|--------|-----------|---------|
| `/classify-documents-async` | POST | Optional | Submit files for classification |
| `/analyze-multiple-async` | POST | Optional | Submit files for analysis |
| `/job/{job_id}` | GET | Optional | Get single job status |
| `/jobs` | GET | **Required** | Get all jobs for user |
| `/job/{job_id}` | DELETE | Optional | Delete a job |

---

**Need Help?** Check the API documentation at `http://localhost:8000/docs` for interactive testing!

