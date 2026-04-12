"""Syntax verification for converted Python files."""
import ast
import os
from pathlib import Path
from typing import Dict, List
from python.utils.logger import logger


class SyntaxVerifier:
    """Verify syntax of converted Python files."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.errors = []
        self.warnings = []

    def verify_all(self) -> Dict:
        """Verify all Python files in converted project."""
        logger.info("Starting post-conversion syntax verification")
        
        python_files = self._find_python_files()
        total_files = len(python_files)
        valid_files = 0
        
        for py_file in python_files:
            if self._verify_file(py_file):
                valid_files += 1
            
        success_rate = (valid_files / total_files * 100) if total_files > 0 else 0
        
        logger.info(f"Syntax verification complete: {valid_files}/{total_files} files valid ({success_rate:.1f}%)")
        
        return {
            'total_files': total_files,
            'valid_files': valid_files,
            'invalid_files': total_files - valid_files,
            'success_rate': round(success_rate, 2),
            'errors': self.errors,
            'warnings': self.warnings,
            'passed': len(self.errors) == 0
        }

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in project."""
        python_files = []
        exclude_dirs = {'__pycache__', '.git', '.venv', 'venv', 'migrations'}
        
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files

    def _verify_file(self, file_path: Path) -> bool:
        """Verify syntax of a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            ast.parse(code)
            return True
        
        except SyntaxError as e:
            error_msg = f"Syntax error in {file_path.name} at line {e.lineno}: {e.msg}"
            self.errors.append({
                'file': str(file_path),
                'line': e.lineno,
                'message': e.msg,
                'type': 'SyntaxError'
            })
            logger.error(error_msg)
            return False
        
        except Exception as e:
            error_msg = f"Error verifying {file_path}: {str(e)}"
            self.errors.append({
                'file': str(file_path),
                'message': str(e),
                'type': type(e).__name__
            })
            logger.error(error_msg)
            return False

    def verify_critical_files(self) -> Dict:
        """Verify critical Flask files."""
        critical_files = [
            'config.py',
            'app.py',
            'wsgi.py',
            '__init__.py',
        ]
        
        critical_path = self.project_path
        results = {}
        
        for filename in critical_files:
            file_path = critical_path / filename
            if file_path.exists():
                results[filename] = self._verify_file(file_path)
            else:
                self.warnings.append({
                    'file': filename,
                    'message': f'Critical file not found: {filename}',
                    'type': 'MissingFile'
                })
                results[filename] = False
        
        return {
            'critical_files': results,
            'all_present_and_valid': all(results.values())
        }
