-- Fix DB constraint to support new job state machine statuses.
-- Error observed:
--   violates check constraint "check_status" when inserting status='created'
--
-- Run this in Supabase SQL editor (or via migration) against the DB that hosts inbox_jobs.

-- 1) Drop old constraint (name from error: check_status)
ALTER TABLE public.inbox_jobs
  DROP CONSTRAINT IF EXISTS check_status;

-- 2) Add updated constraint.
-- Keep 'pending' for backward compatibility with historical rows, but new code uses:
-- created -> ready -> processing -> completed|failed
ALTER TABLE public.inbox_jobs
  ADD CONSTRAINT check_status
  CHECK (status IN ('pending','created','ready','processing','completed','failed'));


