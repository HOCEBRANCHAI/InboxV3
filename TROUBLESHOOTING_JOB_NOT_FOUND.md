# Troubleshooting: Job Not Found Error

## Error Message
```json
{
    "error": "Not Found",
    "detail": "The requested path 'job/2eac20cc-db27-46fe-b2c3-159091999417' was not found on this server."
}
```

## Common Causes & Solutions

### Cause 1: User ID Mismatch ⚠️ **MOST COMMON**

**Problem:** Job was created with one `X-User-ID`, but you're querying with a different one.

**Example:**
- Created job with: `X-User-ID: user-123`
- Querying with: `X-User-ID: user-456` (different!)
- Result: Job not found (security feature)

**Solution:**
1. **Use the SAME `X-User-ID`** that you used when creating the job
2. **Or don't send `X-User-ID` header** when querying (if job was created without it)

---

### Cause 2: Job Created Without User ID

**Problem:** Job was created without `X-User-ID` header, but you're querying with one.

**Solution:**
- **Don't send `X-User-ID` header** when querying
- Or create job WITH `X-User-ID` header

---

### Cause 3: Job Doesn't Exist in Database

**Problem:** Job creation failed silently, or job was deleted.

**Check:**
1. Verify job was created successfully (check the response from POST request)
2. Check Supabase dashboard → `inbox_jobs` table
3. Look for the job_id in the database

**Solution:**
- Create a new job
- Make sure job creation response shows `"status": "pending"`

---

### Cause 4: Supabase Connection Issue

**Problem:** Backend can't connect to Supabase.

**Check:**
1. Verify `SUPABASE_URL` is set in Render environment variables
2. Verify `SUPABASE_SERVICE_ROLE_KEY` is set correctly
3. Check Render logs for Supabase connection errors

**Solution:**
- Fix environment variables in Render dashboard
- Restart the service

---

## How to Fix in Postman

### Option 1: Use Same User ID

**When creating job:**
```
POST /classify-documents-async
Headers: X-User-ID: test-user-123
```

**When checking status:**
```
GET /job/{job_id}
Headers: X-User-ID: test-user-123  ← SAME user ID!
```

### Option 2: Don't Use User ID

**When creating job:**
```
POST /classify-documents-async
Headers: (no X-User-ID header)
```

**When checking status:**
```
GET /job/{job_id}
Headers: (no X-User-ID header)
```

---

## Testing Steps

### Step 1: Create Job (Save the Response)

**Request:**
```
POST https://inboxv3-1.onrender.com/classify-documents-async
Headers: X-User-ID: test-user-123
Body: form-data, files: [your-file.pdf]
```

**Response:**
```json
{
  "job_id": "2eac20cc-db27-46fe-b2c3-159091999417",
  "status": "pending"
}
```

**✅ Save the `job_id` and `X-User-ID` value!**

### Step 2: Check Job Status (Use SAME User ID)

**Request:**
```
GET https://inboxv3-1.onrender.com/job/2eac20cc-db27-46fe-b2c3-159091999417
Headers: X-User-ID: test-user-123  ← MUST MATCH!
```

**Expected:**
```json
{
  "job_id": "2eac20cc-db27-46fe-b2c3-159091999417",
  "status": "pending",
  "progress": 0
}
```

---

## Quick Fix Checklist

- [ ] **Created job with `X-User-ID: test-user-123`?**
  - Then query with **SAME** `X-User-ID: test-user-123`
  
- [ ] **Created job WITHOUT `X-User-ID` header?**
  - Then query **WITHOUT** `X-User-ID` header
  
- [ ] **Check job exists in Supabase:**
  - Go to Supabase dashboard
  - Check `inbox_jobs` table
  - Search for your job_id
  
- [ ] **Verify environment variables:**
  - `SUPABASE_URL` is set
  - `SUPABASE_SERVICE_ROLE_KEY` is set

---

## Example: Correct Flow

### 1. Create Job
```bash
POST /classify-documents-async
Headers:
  X-User-ID: my-user-123
Body:
  files: document.pdf

Response:
{
  "job_id": "abc-123",
  "status": "pending"
}
```

### 2. Check Status (CORRECT)
```bash
GET /job/abc-123
Headers:
  X-User-ID: my-user-123  ← SAME as creation!

Response:
{
  "job_id": "abc-123",
  "status": "pending"
}
```

### 3. Check Status (WRONG - Different User ID)
```bash
GET /job/abc-123
Headers:
  X-User-ID: different-user  ← DIFFERENT!

Response:
{
  "error": "Not Found",
  "detail": "Job abc-123 not found or doesn't belong to user"
}
```

---

## Solution: Always Use Same User ID

**Best Practice:**
1. **Pick one user ID** for testing (e.g., `test-user-123`)
2. **Always use it** in both create and query requests
3. **Save it** as a Postman variable for easy reuse

**In Postman:**
1. Create collection variable: `user_id = test-user-123`
2. Use `{{user_id}}` in all requests
3. This ensures consistency

---

## Alternative: Check All Jobs

If you're not sure which user_id was used:

```
GET https://inboxv3-1.onrender.com/jobs
Headers: X-User-ID: test-user-123
```

This will show ALL jobs for that user, including their job_ids.

---

## Summary

**The issue:** User ID mismatch between job creation and query.

**The fix:** Use the **SAME** `X-User-ID` header value when:
- Creating the job
- Checking job status
- Getting all jobs

**Quick test:**
1. Create job with `X-User-ID: test-123`
2. Check status with `X-User-ID: test-123` (same value)
3. Should work! ✅

