-- Supabase Migration: Create inbox_jobs table
-- Run this in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS inbox_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID,
    batch_id UUID,
    user_id TEXT,  -- User identifier from frontend (passed in X-User-ID header)
    endpoint_type TEXT NOT NULL DEFAULT 'classify',
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    result JSONB,
    error TEXT,
    file_data JSONB,  -- Stores file metadata and base64 encoded content
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_status ON inbox_jobs(status);
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_created_at ON inbox_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_batch_id ON inbox_jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id ON inbox_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_user_id_status ON inbox_jobs(user_id, status);

-- Add check constraint for status
ALTER TABLE inbox_jobs 
ADD CONSTRAINT check_status 
CHECK (status IN ('pending', 'processing', 'completed', 'failed'));

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_inbox_jobs_updated_at 
    BEFORE UPDATE ON inbox_jobs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE inbox_jobs IS 'Stores job records for async document processing';
COMMENT ON COLUMN inbox_jobs.status IS 'Job status: pending, processing, completed, failed';
COMMENT ON COLUMN inbox_jobs.endpoint_type IS 'Type of processing: classify or analyze';
COMMENT ON COLUMN inbox_jobs.user_id IS 'User identifier from frontend (passed in X-User-ID header)';
COMMENT ON COLUMN inbox_jobs.file_data IS 'JSON array of file metadata and base64 encoded content';

