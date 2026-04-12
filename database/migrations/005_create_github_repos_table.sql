-- Create github_repos table
CREATE TABLE IF NOT EXISTS github_repos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversion_job_id UUID NOT NULL REFERENCES conversion_jobs(id) ON DELETE CASCADE,
    repo_name VARCHAR(255) NOT NULL,
    repo_url TEXT NOT NULL,
    pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes only if they don't exist
CREATE INDEX IF NOT EXISTS idx_github_repos_user_id ON github_repos(user_id);
CREATE INDEX IF NOT EXISTS idx_github_repos_conversion_job_id ON github_repos(conversion_job_id);
