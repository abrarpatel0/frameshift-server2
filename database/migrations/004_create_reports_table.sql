-- Create reports table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversion_job_id UUID NOT NULL REFERENCES conversion_jobs(id) ON DELETE CASCADE,
    accuracy_score DECIMAL(5,2) CHECK (accuracy_score >= 0 AND accuracy_score <= 100),
    total_files_converted INTEGER DEFAULT 0,
    models_converted INTEGER DEFAULT 0,
    views_converted INTEGER DEFAULT 0,
    urls_converted INTEGER DEFAULT 0,
    forms_converted INTEGER DEFAULT 0,
    templates_converted INTEGER DEFAULT 0,
    issues JSONB,
    warnings JSONB,
    suggestions JSONB,
    gemini_verification JSONB,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes only if they don't exist
CREATE INDEX IF NOT EXISTS idx_reports_conversion_job_id ON reports(conversion_job_id);
CREATE INDEX IF NOT EXISTS idx_reports_accuracy_score ON reports(accuracy_score);
