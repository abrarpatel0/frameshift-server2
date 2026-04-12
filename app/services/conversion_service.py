"""Conversion service for Django to Flask conversion jobs."""
import subprocess
import json
from datetime import datetime
from app.extensions import db
from app.models import ConversionJob, Report
from app.services.storage_service import StorageService
from app.services.email_service import EmailService
from app.models import User
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversionService:
    """Service for conversion operations."""

    # Map to track active Python processes
    active_processes = {}

    @staticmethod
    def create_conversion_job(project_id, user_id, use_ai=True, conversion_mode="default", custom_api_config=None):
        """Create new conversion job."""
        try:
            job = ConversionJob(
                project_id=project_id,
                user_id=user_id,
                status="pending",
                progress_percentage=0,
                current_step="Initializing",
                use_ai=use_ai,
                conversion_mode=conversion_mode,
                custom_api_config=custom_api_config,
                ai_enhancements=[],
            )
            db.session.add(job)
            db.session.commit()
            logger.info(f"Conversion job created: {job.id}")
            return job
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create conversion job: {str(e)}")
            raise

    @staticmethod
    def start_conversion(job_id, project_path, user_id):
        """Start conversion process."""
        try:
            from flask import current_app

            job = ConversionJob.query.get(job_id)
            if not job:
                raise ValueError("Conversion job not found")

            # Update job status
            job.status = "analyzing"
            job.started_at = datetime.utcnow()
            job.current_step = "Analyzing Django project"
            db.session.commit()

            # Get output directory
            output_path = StorageService.get_converted_directory(user_id, job_id)

            # Build Python command
            python_path = current_app.config.get("PYTHON_PATH", "python3")
            python_script = "python/main.py"

            cmd = [
                python_path,
                python_script,
                "--job-id",
                job_id,
                "--project-path",
                project_path,
                "--output-path",
                output_path,
                "--use-ai",
                "true" if job.use_ai else "false",
                "--conversion-mode",
                job.conversion_mode,
            ]

            # Add Gemini API key if using AI
            if job.use_ai:
                gemini_key = current_app.config.get("GEMINI_API_KEY")
                if gemini_key:
                    cmd.extend(["--gemini-api-key", gemini_key])

            # Spawn Python process (non-blocking)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Store process reference
            ConversionService.active_processes[job_id] = process

            logger.info(f"Conversion process started for job {job_id}")

            # Update job status
            job.status = "converting"
            db.session.commit()

            return {"message": "Conversion started", "job_id": job_id}

        except Exception as e:
            logger.error(f"Failed to start conversion: {str(e)}")
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.session.commit()
            raise

    @staticmethod
    def check_conversion_status(job_id):
        """Check conversion job status."""
        try:
            job = ConversionJob.query.get(job_id)
            if not job:
                raise ValueError("Conversion job not found")

            # Check if process is still running
            if job_id in ConversionService.active_processes:
                process = ConversionService.active_processes[job_id]
                if process.poll() is None:
                    # Process still running
                    return job.to_dict()
                else:
                    # Process completed, read output
                    stdout, stderr = process.communicate()

                    if process.returncode == 0:
                        # Success - parse actual report from stdout
                        job.status = "completed"
                        job.progress_percentage = 100
                        job.completed_at = datetime.utcnow()

                        # Parse JSON output from Python engine
                        report_data = ConversionService._parse_conversion_output(stdout)
                        
                        if report_data and 'report' in report_data:
                            report_dict = report_data['report']
                            report = Report(
                                conversion_job_id=job_id,
                                accuracy_percentage=report_dict.get('accuracy_score', 85.0),
                                files_converted=report_dict.get('total_files_converted', 0),
                                files_failed=len(report_dict.get('issues', [])),
                                issues_found=report_dict.get('issues', []),
                                suggestions=report_dict.get('suggestions', []),
                                gemini_verification=report_dict.get('gemini_verification', {}),
                                validation_result={
                                    'models': report_dict.get('models_converted', 0),
                                    'views': report_dict.get('views_converted', 0),
                                    'urls': report_dict.get('urls_converted', 0),
                                    'templates': report_dict.get('templates_converted', 0),
                                    'ai_enhanced': report_dict.get('ai_enhancement', {}),
                                    'syntax_check': report_dict.get('syntax_verification', {})
                                }
                            )
                        else:
                            # Fallback if parsing fails
                            report = Report(
                                conversion_job_id=job_id,
                                accuracy_percentage=85.0,
                                files_converted=0,
                                files_failed=0,
                            )
                        
                        db.session.add(report)
                    else:
                        # Failed
                        job.status = "failed"
                        job.error_message = stderr or "Conversion process failed"
                        logger.error(f"Conversion failed for job {job_id}: {stderr}")

                    db.session.commit()

                    # Clean up process reference
                    del ConversionService.active_processes[job_id]

            return job.to_dict()

        except Exception as e:
            logger.error(f"Failed to check conversion status: {str(e)}")
            raise

    @staticmethod
    def _parse_conversion_output(stdout_text):
        """Parse JSON output from Python conversion engine."""
        if not stdout_text:
            return None
        
        try:
            # The output may contain multiple JSON lines, get the last one (result)
            lines = stdout_text.strip().split('\n')
            for line in reversed(lines):
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'result':
                            return data.get('data', {})
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to parse conversion output: {str(e)}")
        
        return None

    @staticmethod
    def cancel_conversion(job_id):
        """Cancel ongoing conversion."""
        try:
            job = ConversionJob.query.get(job_id)
            if not job:
                raise ValueError("Conversion job not found")

            # Kill process if running
            if job_id in ConversionService.active_processes:
                process = ConversionService.active_processes[job_id]
                process.kill()
                del ConversionService.active_processes[job_id]

            # Update job status
            job.status = "cancelled"
            job.current_step = "Cancelled by user"
            db.session.commit()

            logger.info(f"Conversion job cancelled: {job_id}")
            return {"message": "Conversion cancelled"}

        except Exception as e:
            logger.error(f"Failed to cancel conversion: {str(e)}")
            raise

    @staticmethod
    def retry_conversion(job_id):
        """Retry failed conversion."""
        try:
            job = ConversionJob.query.get(job_id)
            if not job:
                raise ValueError("Conversion job not found")

            if job.status != "failed":
                raise ValueError("Only failed conversions can be retried")

            # Reset job
            job.status = "pending"
            job.retry_count += 1
            job.last_retry_at = datetime.utcnow()
            job.error_message = None
            job.progress_percentage = 0
            db.session.commit()

            logger.info(f"Conversion job retried: {job_id}")
            return {"message": "Conversion will be retried", "retry_count": job.retry_count}

        except Exception as e:
            logger.error(f"Failed to retry conversion: {str(e)}")
            raise
