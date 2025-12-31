# User ID Setup Guide

## Quick Summary

✅ **User ID support is already implemented in the backend!**

Your frontend team just needs to:
1. Add `X-User-ID` header to API requests
2. Use `GET /jobs` endpoint to fetch user's jobs
3. Run the database migration if `user_id` column doesn't exist

---

## Step 1: Database Migration

### If you haven't created the table yet:
Run the **complete** `supabase_migration.sql` file (it now includes `user_id` column).

### If table already exists:
Run `add_user_id_column.sql` to add the `user_id` column:

```sql
-- In Supabase SQL Editor
ALTER TABLE inbox_jobs 
ADD COLUMN IF NOT EXISTS user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id ON inbox_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id_status ON inbox_jobs(user_id, status);
```

---

## Step 2: Frontend Implementation

### Basic Example:

```javascript
// Set user ID (from your UI/authentication)
const userId = "user-123";  // Or get from your auth system

// Submit documents
fetch('/classify-documents-async', {
  method: 'POST',
  headers: {
    'X-User-ID': userId  // ← Add this header
  },
  body: formData
});

// Get all jobs for user
fetch('/jobs', {
  headers: {
    'X-User-ID': userId  // ← Required for this endpoint
  }
});
```

---

## Available Endpoints

| Endpoint | Method | X-User-ID | Purpose |
|----------|--------|-----------|---------|
| `/classify-documents-async` | POST | Optional | Submit files |
| `/analyze-multiple-async` | POST | Optional | Submit files |
| `/job/{job_id}` | GET | Optional | Get single job |
| `/jobs` | GET | **Required** | Get all user jobs ⭐ |
| `/job/{job_id}` | DELETE | Optional | Delete job |

---

## Complete Documentation

See `FRONTEND_API_GUIDE.md` for:
- ✅ Complete API reference
- ✅ JavaScript/React examples
- ✅ Error handling
- ✅ Security considerations
- ✅ Code snippets ready to use

---

## Testing

```bash
# 1. Submit with user ID
curl -X POST http://localhost:8000/classify-documents-async \
  -H "X-User-ID: test-user-123" \
  -F "files=@test.pdf"

# 2. Get all jobs for user
curl -X GET http://localhost:8000/jobs \
  -H "X-User-ID: test-user-123"

# 3. Get specific job
curl -X GET http://localhost:8000/job/{job_id} \
  -H "X-User-ID: test-user-123"
```

---

## What's Already Working

✅ Backend accepts `X-User-ID` header  
✅ Stores `user_id` with each job  
✅ `GET /jobs` endpoint filters by user_id  
✅ `GET /job/{job_id}` verifies ownership  
✅ Security checks prevent cross-user access  

**You just need to:**
1. Run the database migration (if needed)
2. Have frontend send `X-User-ID` header
3. Use `GET /jobs` to fetch user's jobs

---

## User ID Format

Any unique string works:
- `"user-123"`
- `"john@example.com"`
- `"550e8400-e29b-41d4-a716-446655440000"` (UUID)
- Any identifier from your UI

**Recommendation:** Use a consistent format (UUID or your internal user ID).

---

## Next Steps

1. ✅ Run database migration (`add_user_id_column.sql`)
2. ✅ Share `FRONTEND_API_GUIDE.md` with frontend team
3. ✅ Test with `X-User-ID` header
4. ✅ Frontend implements header in all requests

**That's it!** Everything else is already implemented. 🎉

