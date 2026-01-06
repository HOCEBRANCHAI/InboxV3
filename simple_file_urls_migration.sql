-- Simple File URLs Migration
-- Add a simple TEXT[] column for easy worker access
-- This is a backup/simpler format alongside file_storage_urls

-- Add simple file_urls column (array of URLs)
ALTER TABLE inbox_jobs 
ADD COLUMN IF NOT EXISTS file_urls TEXT[];

-- Populate from existing file_storage_urls data
UPDATE inbox_jobs
SET file_urls = (
    SELECT array_agg(
        CASE 
            WHEN jsonb_typeof(value->'storage_url') = 'string' 
            THEN value->>'storage_url'
            ELSE NULL
        END
    )
    FROM jsonb_array_elements(file_storage_urls)
)
WHERE file_storage_urls IS NOT NULL 
  AND file_urls IS NULL;

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_file_urls 
ON inbox_jobs USING gin (file_urls);

