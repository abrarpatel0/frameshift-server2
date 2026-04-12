-- Migration: Add manual_changes JSONB column to reports table
-- This column stores the structured manual changes guide generated after conversion
-- containing critical/important/optional changes, dependency mapping, and testing checklist.

-- Add the column (safe: IF NOT EXISTS is not supported for ADD COLUMN in all PG versions,
-- so we use a DO block to check first)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'reports'
          AND column_name = 'manual_changes'
    ) THEN
        ALTER TABLE reports ADD COLUMN manual_changes JSONB DEFAULT NULL;
        RAISE NOTICE 'Column manual_changes added to reports table';
    ELSE
        RAISE NOTICE 'Column manual_changes already exists on reports table';
    END IF;
END $$;

-- Add a comment describing the column
COMMENT ON COLUMN reports.manual_changes IS 'Structured JSON guide of manual post-conversion changes: {critical: [], important: [], optional: [], dependencies: {}, testing_checklist: [], summary: {}}';
