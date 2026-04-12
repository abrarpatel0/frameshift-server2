-- Migration 016: Add status validation constraint to conversion_jobs table
-- Purpose: Enforce single source of truth for conversion job status values (Fix 19)
-- Valid statuses: pending, analyzing, converting, verifying, completed, validated, failed, cancelled

ALTER TABLE conversion_jobs
DROP CONSTRAINT IF EXISTS chk_valid_status;

ALTER TABLE conversion_jobs
ADD CONSTRAINT chk_valid_status CHECK (
  status IN ('pending', 'analyzing', 'converting', 'verifying', 'completed', 'validated', 'failed', 'cancelled')
);

-- Create index on status for faster filtering during WebSocket subscriptions
CREATE INDEX IF NOT EXISTS idx_conversion_status ON conversion_jobs(status);
