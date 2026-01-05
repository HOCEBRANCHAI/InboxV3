-- Migration: Add support for Supabase Storage file URLs
-- This migration adds a column to store file URLs from Supabase Storage
-- Run this in Supabase SQL Editor

-- Add column for file storage URLs (if not exists)
ALTER TABLE inbox_jobs 
ADD COLUMN IF NOT EXISTS file_storage_urls JSONB;

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_inbox_jobs_file_storage_urls 
ON inbox_jobs USING gin (file_storage_urls);

-- Note: The existing file_data column will still be used for backward compatibility
-- New jobs will use file_storage_urls, old jobs will continue using file_data

