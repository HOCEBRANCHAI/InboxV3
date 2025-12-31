-- ============================================================
-- URGENT: Add user_id column to existing inbox_jobs table
-- ============================================================
-- Run this in your Supabase SQL Editor RIGHT NOW
-- This will fix the error: "Could not find the 'user_id' column"
-- ============================================================

-- Step 1: Add the user_id column
ALTER TABLE inbox_jobs 
ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Step 2: Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id ON inbox_jobs(user_id);

-- Step 3: Create composite index for user_id + status (common query pattern)
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id_status ON inbox_jobs(user_id, status);

-- Step 4: Add comment
COMMENT ON COLUMN inbox_jobs.user_id IS 'User identifier from frontend (passed in X-User-ID header)';

-- ============================================================
-- VERIFICATION: Check if column was added
-- ============================================================
-- Run this to verify:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'inbox_jobs' AND column_name = 'user_id';
-- ============================================================

