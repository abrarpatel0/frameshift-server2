import json
import sys


class ProgressEmitter:
    """Emit progress updates to Node.js via stdout"""

    @staticmethod
    def emit(job_id, step, progress, message):
        """
        Emit progress update

        Args:
            job_id (str): Conversion job ID
            step (str): Current step name
            progress (int): Progress percentage (0-100)
            message (str): Status message
        """
        output = {
            'type': 'progress',
            'jobId': job_id,
            'step': step,
            'progress': progress,
            'message': message
        }
        print(json.dumps(output), flush=True)

    @staticmethod
    def emit_result(data):
        """
        Emit final result

        Args:
            data (dict): Result data
        """
        output = {
            'type': 'result',
            'data': data
        }
        print(json.dumps(output), flush=True)

    @staticmethod
    def emit_error(job_id, error_message):
        """
        Emit error

        Args:
            job_id (str): Conversion job ID
            error_message (str): Error message
        """
        output = {
            'type': 'error',
            'jobId': job_id,
            'error': error_message
        }
        print(json.dumps(output), flush=True)

    @staticmethod
    def emit_custom(job_id, type_name, data):
        """
        Emit custom message

        Args:
            job_id (str): Conversion job ID
            type_name (str): Message type
            data (any): Data payload
        """
        output = {
            'type': type_name,
            'jobId': job_id,
            'data': data
        }
        print(json.dumps(output), flush=True)


__all__ = ['ProgressEmitter']
