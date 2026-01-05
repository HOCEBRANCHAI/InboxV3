# Supabase Storage Setup Guide

## 🎯 Overview

This guide will help you set up Supabase Storage to store files for the Inbox service. Files will be uploaded to Supabase Storage instead of local filesystem, allowing the web service and worker (on separate Render services) to access the same files.

---

## 📋 Step 1: Run Database Migration

1. **Go to Supabase Dashboard:**
   - https://supabase.com/dashboard
   - Select your project

2. **Go to SQL Editor:**
   - Click "SQL Editor" in the left sidebar

3. **Run the migration:**
   - Open `supabase_storage_migration.sql`
   - Copy the contents
   - Paste into SQL Editor
   - Click "Run"

**What this does:**
- Adds `file_storage_urls` column to `inbox_jobs` table
- Creates index for faster queries
- Maintains backward compatibility with existing `file_data` column

---

## 📋 Step 2: Create Storage Bucket

1. **Go to Storage:**
   - Click "Storage" in the left sidebar
   - Click "New bucket"

2. **Configure bucket:**
   - **Name:** `inbox-files` (must match this exactly, or update code)
   - **Public bucket:** ✅ **Enable** (allows public access to files)
   - **File size limit:** Leave default or set to your max (e.g., 100MB)
   - **Allowed MIME types:** Leave empty (allows all types)

3. **Click "Create bucket"**

**Why public bucket?**
- Files need to be accessible by the worker service
- Public URLs are simpler to use
- If you need private files, use signed URLs (more complex)

---

## 📋 Step 3: Set Up Bucket Policies (Optional but Recommended)

1. **Go to Storage → Policies:**
   - Click on `inbox-files` bucket
   - Click "New policy"

2. **Create Upload Policy:**
   - **Policy name:** `Allow authenticated uploads`
   - **Allowed operation:** `INSERT`
   - **Policy definition:**
     ```sql
     (bucket_id = 'inbox-files'::text)
     ```
   - Click "Review" → "Save policy"

3. **Create Read Policy:**
   - **Policy name:** `Allow public reads`
   - **Allowed operation:** `SELECT`
   - **Policy definition:**
     ```sql
     (bucket_id = 'inbox-files'::text)
     ```
   - Click "Review" → "Save policy"

**Note:** If bucket is public, these policies may not be necessary, but they're good practice.

---

## 📋 Step 4: Verify Environment Variables

**Both web service and worker need:**

```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
```

**Get these from:**
- Supabase Dashboard → Project Settings → API
- Copy "Project URL" → `SUPABASE_URL`
- Copy "service_role" key (secret) → `SUPABASE_SERVICE_ROLE_KEY`

**Important:** Use **service_role** key, not anon key! Service role key has full access to Storage.

---

## 📋 Step 5: Test the Setup

### Test 1: Create a Test Job

1. **Go to your API:**
   - `https://inboxv3-1d4z.onrender.com/docs`

2. **Create a job:**
   - Use `POST /classify-documents-async`
   - Upload a test file
   - Get the `job_id`

### Test 2: Check Supabase Storage

1. **Go to Supabase Dashboard → Storage:**
   - Click on `inbox-files` bucket
   - You should see: `{job_id}/{filename}`
   - Files should be listed there

### Test 3: Check Database

1. **Go to Supabase Dashboard → Table Editor:**
   - Open `inbox_jobs` table
   - Find your job
   - Check `file_storage_urls` column
   - Should contain JSON with file URLs

### Test 4: Check Worker Processing

1. **Go to Render Dashboard:**
   - Check worker logs
   - Should see: "Downloaded file from Supabase Storage"
   - Job should process successfully

---

## 🔍 Troubleshooting

### Issue: "Bucket not found"

**Solution:**
- Verify bucket name is exactly `inbox-files`
- Check bucket exists in Supabase Storage
- Verify bucket is not deleted

### Issue: "Permission denied" when uploading

**Solution:**
- Check you're using `SUPABASE_SERVICE_ROLE_KEY` (not anon key)
- Verify bucket policies allow uploads
- Check bucket is public or policies allow service role

### Issue: "Permission denied" when downloading

**Solution:**
- Check bucket is public OR
- Update policies to allow reads
- Verify `SUPABASE_SERVICE_ROLE_KEY` is set correctly

### Issue: Files not appearing in Storage

**Solution:**
- Check web service logs for upload errors
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are correct
- Check bucket name matches code (`inbox-files`)

### Issue: Worker can't download files

**Solution:**
- Check worker logs for download errors
- Verify storage URLs are correct in database
- Check bucket is accessible (public or proper policies)

---

## 📊 Architecture

**New Flow with Supabase Storage:**

```
1. Client uploads files
   ↓
2. Web Service receives files
   ↓
3. Web Service uploads to Supabase Storage
   - Bucket: inbox-files
   - Path: {job_id}/{filename}
   ↓
4. Web Service stores URLs in database
   - Column: file_storage_urls
   - Format: [{"filename": "...", "storage_url": "https://...", ...}]
   ↓
5. Worker polls database for pending jobs
   ↓
6. Worker reads file_storage_urls from database
   ↓
7. Worker downloads files from Supabase Storage
   ↓
8. Worker processes files
   ↓
9. Worker updates job status
```

**Benefits:**
- ✅ Files accessible from any service
- ✅ No filesystem sharing needed
- ✅ Scalable (multiple workers can access same files)
- ✅ Automatic cleanup possible
- ✅ Works across different Render services

---

## 🧹 Cleanup (Optional)

### Automatic Cleanup

You can set up automatic cleanup of old files:

1. **Go to Supabase Dashboard → Database → Functions:**
   - Create a function to delete old files
   - Schedule with pg_cron (if available)

2. **Or manual cleanup:**
   - Go to Storage → `inbox-files`
   - Delete old job folders manually

### Delete Job Function

The `delete_job` function in `job_service.py` now automatically deletes files from Storage when a job is deleted.

---

## 📋 Checklist

- [ ] Database migration run (`supabase_storage_migration.sql`)
- [ ] Storage bucket created (`inbox-files`)
- [ ] Bucket is public (or policies set)
- [ ] Environment variables set (both services)
- [ ] Test job created
- [ ] Files appear in Storage
- [ ] Worker can download and process files
- [ ] Job completes successfully

---

## 🚀 Next Steps

1. **Deploy updated code:**
   - Push changes to repository
   - Render will auto-deploy

2. **Test with new jobs:**
   - Create test jobs
   - Verify files upload to Storage
   - Verify worker processes them

3. **Monitor:**
   - Check Storage usage
   - Monitor worker logs
   - Verify job processing

---

## 💡 Pro Tips

1. **Bucket naming:** Keep it consistent (`inbox-files`)
2. **File organization:** Files are organized by `{job_id}/{filename}`
3. **Storage limits:** Monitor your Supabase Storage quota
4. **Cleanup:** Set up automatic cleanup for old files
5. **Backup:** Consider backing up important files

---

**Your Supabase Storage setup is complete! Files will now be stored in the cloud and accessible by both web service and worker.** 🎉

