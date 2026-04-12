-- Migration 015: Add notification_status column to conversion_jobs table
-- Purpose: Track email notification delivery status for conversion completions

-- Add column if it doesn't exist
ALTER TABLE conversion_jobs
ADD COLUMN IF NOT EXISTS notification_status VARCHAR(50) DEFAULT 'pending';

-- Add constraint for valid notification statuses
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE constraint_name = 'chk_notification_status' AND table_name = 'conversion_jobs'
  ) THEN
    ALTER TABLE conversion_jobs
    ADD CONSTRAINT chk_notification_status
    CHECK (notification_status IN ('pending', 'sent', 'failed'));
  END IF;
END
$$;

-- Create index for easier monitoring of failed notifications
CREATE INDEX IF NOT EXISTS idx_notification_status 
ON conversion_jobs(notification_status);

-- Backfill any existing completed jobs to 'sent' (assume notifications were sent in previous version)
UPDATE conversion_jobs
SET notification_status = 'sent'
WHERE status IN ('completed', 'validated') AND notification_status = 'pending';
