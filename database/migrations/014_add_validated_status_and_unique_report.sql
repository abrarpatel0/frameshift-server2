ALTER TABLE conversion_jobs
DROP CONSTRAINT IF EXISTS conversion_jobs_status_check;

ALTER TABLE conversion_jobs
ADD CONSTRAINT conversion_jobs_status_check
CHECK (status IN ('pending', 'analyzing', 'converting', 'verifying', 'completed', 'validated', 'failed'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_conversion_job_id_unique
ON reports(conversion_job_id);
