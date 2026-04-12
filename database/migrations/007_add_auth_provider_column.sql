-- Migration: Add auth_provider column to users table
-- Purpose: Track how user signed up (email vs GitHub OAuth)
-- Date: 2025-12-28

-- Add auth_provider column only if it doesn't exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) DEFAULT 'email';

-- Update existing users who have github_id to set auth_provider = 'github'
-- Only update if auth_provider is still 'email' (to make this idempotent)
UPDATE users
SET auth_provider = 'github'
WHERE github_id IS NOT NULL AND auth_provider = 'email';

-- Add index for faster queries only if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);

-- Add comment (COMMENT IF NOT EXISTS doesn't exist, but this is safe to run multiple times)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_description
        WHERE objoid = 'users'::regclass
        AND objsubid = (
            SELECT ordinal_position
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'auth_provider'
        )
    ) THEN
        EXECUTE 'COMMENT ON COLUMN users.auth_provider IS ''How the user signed up: email or github''';
    END IF;
END $$;
