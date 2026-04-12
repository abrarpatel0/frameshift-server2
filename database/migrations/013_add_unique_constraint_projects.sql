-- Migration: Add unique constraint to projects table to prevent duplicate active project names per user
-- Date: 2026-03-17

-- First, ensure we don't have existing duplicates that would break the constraint
-- (In a real scenario, we might need to deduplicate, but here we assume generateUniqueActiveName was intended to prevent this)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'unique_user_project_name'
    ) THEN
        ALTER TABLE projects
        ADD CONSTRAINT unique_user_project_name UNIQUE (user_id, name);
    END IF;
END
$$;

COMMENT ON CONSTRAINT unique_user_project_name ON projects IS 'Ensures project names are unique per user';
