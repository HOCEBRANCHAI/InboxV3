# Debug: file_storage_urls Column Exists But Worker Can't Find Data

## 🔴 Problem

- ✅ Column `file_storage_urls` exists in database
- ✅ Files uploaded to Supabase Storage
- ❌ Worker still can't find file data: "No file data found for job"

## 🔍 Diagnostic Steps

### Step 1: Check Database Directly

**Go to Supabase Dashboard → Table Editor:**

1. Find job: `9a238f58-b448-448d-b3c0-20044d6bf368`
2. Check `file_storage_urls` column
3. **What does it show?**
   - NULL/empty?
   - JSON string?
   - JSON object?

**Expected format:**
```json
[
  {
    "filename": "20250707_203447.jpg",
    "storage_url": "https://jdftjmzcvdnxfgxcgthg.supabase.co/storage/v1/object/public/inbox-files/...",
    "suffix": ".jpg",
    "size": 12345
  }
]
```

### Step 2: Check Web Service Logs

**Go to Render Dashboard → Web Service → Logs:**

Look for:
```
✅ "Uploaded file {filename} to Supabase Storage: {url}"
✅ "Stored file storage URLs for job {job_id} ({n} files)"
❌ "Error storing file storage URLs for job {job_id}: ..."
❌ "Failed to upload {filename} to Supabase Storage, falling back to local storage"
```

### Step 3: Check Worker Logs

**Go to Render Dashboard → Worker → Logs:**

Look for:
```
✅ "Retrieved file storage URLs for job {job_id} ({n} files)"
❌ "No file data found for job {job_id}"
❌ "Error getting file data for job {job_id}: ..."
```

**New logs (after fix):**
```
DEBUG: Job {job_id} columns: [...]
DEBUG: file_storage_urls value: ...
DEBUG: file_data value: ...
```

### Step 4: Test with SQL Query

**Run in Supabase SQL Editor:**

```sql
SELECT 
    id,
    file_storage_urls,
    file_data,
    pg_typeof(file_storage_urls) as storage_urls_type,
    pg_typeof(file_data) as file_data_type
FROM inbox_jobs
WHERE id = '9a238f58-b448-448d-b3c0-20044d6bf368';
```

**What to check:**
- Is `file_storage_urls` NULL or has data?
- What type is it? (Should be `jsonb`)
- Is the JSON valid?

---

## 🐛 Common Issues

### Issue 1: Data is NULL

**Symptom:** `file_storage_urls` column is NULL

**Cause:** `store_file_storage_urls()` failed silently

**Fix:**
- Check web service logs for errors
- Verify `SUPABASE_SERVICE_ROLE_KEY` is correct
- Check if there was an exception during storage

### Issue 2: Data is Empty Array `[]`

**Symptom:** `file_storage_urls` is `[]`

**Cause:** All file uploads failed, empty list stored

**Fix:**
- Check why uploads failed
- Check Storage bucket permissions
- Verify bucket name is correct

### Issue 3: JSON Parsing Error

**Symptom:** Data exists but can't be parsed

**Cause:** Invalid JSON format

**Fix:**
- Check JSON syntax in database
- Verify data was stored correctly
- Check for encoding issues

### Issue 4: Supabase Returns Different Format

**Symptom:** Data exists but worker can't read it

**Cause:** Supabase JSONB might return as dict/list, not string

**Fix:**
- Updated code now handles both formats
- Check worker logs for type information

---

## ✅ Quick Fix: Check Current Job

**Run this SQL to see what's in the database:**

```sql
SELECT 
    id,
    status,
    file_storage_urls,
    file_data,
    LENGTH(file_storage_urls::text) as storage_urls_length,
    LENGTH(file_data::text) as file_data_length
FROM inbox_jobs
WHERE id = '9a238f58-b448-448d-b3c0-20044d6bf368';
```

**Share the results:**
- What does `file_storage_urls` show?
- Is it NULL, empty, or has data?
- What does `file_data` show?

---

## 🔧 Updated Code

I've updated `get_file_data()` with:
- ✅ Better error handling
- ✅ Debug logging
- ✅ Handles both string and object formats
- ✅ Better error messages

**After deploying, check worker logs for:**
```
DEBUG: Job {job_id} columns: [...]
DEBUG: file_storage_urls value: ...
```

This will show exactly what the worker sees.

---

## 📋 Next Steps

1. **Check database** - What's in `file_storage_urls` column?
2. **Check web service logs** - Did storage succeed?
3. **Check worker logs** - What error does it show?
4. **Deploy updated code** - Better logging will help
5. **Create new test job** - After code update

---

**Please check the database and share what you see in the `file_storage_urls` column for job `9a238f58-b448-448d-b3c0-20044d6bf368`!** 🔍

