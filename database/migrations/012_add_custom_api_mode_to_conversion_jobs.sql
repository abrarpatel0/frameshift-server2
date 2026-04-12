-- Migration: Add custom API mode support for conversion jobs
-- Date: 2026-03-11
-- Description: Adds conversion mode and custom API configuration storage

ALTER TABLE conversion_jobs
ADD COLUMN IF NOT EXISTS conversion_mode VARCHAR(20) NOT NULL DEFAULT 'default';

ALTER TABLE conversion_jobs
ADD COLUMN IF NOT EXISTS custom_api_config JSONB;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_conversion_jobs_conversion_mode'
  ) THEN
    ALTER TABLE conversion_jobs
    ADD CONSTRAINT chk_conversion_jobs_conversion_mode
    CHECK (conversion_mode IN ('default', 'custom'));
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_conversion_jobs_conversion_mode
ON conversion_jobs(conversion_mode);

COMMENT ON COLUMN conversion_jobs.conversion_mode IS 'Conversion mode selected by user: default or custom';
COMMENT ON COLUMN conversion_jobs.custom_api_config IS 'JSON configuration for user-provided AI API (API key is encrypted)';
