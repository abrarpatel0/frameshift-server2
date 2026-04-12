"""
Framework Detection Module
Detects web framework type before conversion
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional
from ..utils.file_handler import FileHandler
from ..utils.logger import logger


class FrameworkDetector:
    """Detect web framework used in a project"""

    FRAMEWORK_INDICATORS = {
        'django': {
            'files': ['manage.py', 'settings.py', 'wsgi.py'],
            'imports': ['django', 'from django', 'import django'],
            'patterns': [r'INSTALLED_APPS\s*=', r'MIDDLEWARE\s*=', r'DATABASES\s*='],
            'confidence_threshold': 2
        },
        'flask': {
            'files': ['app.py', 'wsgi.py', 'run.py'],
            'imports': ['flask', 'from flask', 'import flask', 'Flask(__name__)'],
            'patterns': [r'@app\.route', r'Flask\(__name__\)', r'flask\.Flask'],
            'confidence_threshold': 2
        },
        'fastapi': {
            'files': ['main.py'],
            'imports': ['fastapi', 'from fastapi', 'import fastapi'],
            'patterns': [r'@app\.(get|post|put|delete)', r'FastAPI\(', r'from fastapi import'],
            'confidence_threshold': 2
        },
        'express': {
            'files': ['package.json', 'server.js', 'app.js'],
            'imports': ['express', 'require(\'express\')', 'require("express")'],
            'patterns': [r'express\(\)', r'app\.(get|post|put|delete)', r'"express":'],
            'confidence_threshold': 2
        }
    }

    def __init__(self, project_path: str):
        """
        Initialize framework detector

        Args:
            project_path: Path to project directory
        """
        self.project_path = Path(project_path)
        self.detected_framework = None
        self.confidence_score = 0
        self.evidence = []

    def detect(self) -> Dict:
        """
        Detect framework used in project

        Returns:
            Dictionary with detection results:
            {
                'framework': 'django' | 'flask' | 'fastapi' | 'express' | 'unknown',
                'confidence': 0.0-1.0,
                'evidence': [list of evidence found],
                'is_supported': bool,
                'version': str | None
            }
        """
        logger.info(f"Detecting framework in: {self.project_path}")

        scores = {}
        evidence_by_framework = {}

        for framework, indicators in self.FRAMEWORK_INDICATORS.items():
            score, evidence = self._check_framework(framework, indicators)
            scores[framework] = score
            evidence_by_framework[framework] = evidence

        # Determine detected framework
        max_score = max(scores.values())

        if max_score == 0:
            framework = 'unknown'
            confidence = 0.0
            evidence = []
        else:
            framework = max(scores, key=scores.get)
            threshold = self.FRAMEWORK_INDICATORS[framework]['confidence_threshold']
            confidence = min(max_score / (threshold * 2), 1.0)  # Normalize to 0-1
            evidence = evidence_by_framework[framework]

        # Detect version if possible
        version = self._detect_version(framework)

        # Check if framework is supported for conversion
        supported_frameworks = ['django']  # Currently only Django -> Flask
        is_supported = framework in supported_frameworks

        result = {
            'framework': framework,
            'confidence': round(confidence, 2),
            'evidence': evidence,
            'is_supported': is_supported,
            'version': version,
            'all_scores': scores
        }

        logger.info(f"Detected framework: {framework} (confidence: {confidence:.2f})")

        return result

    def _check_framework(self, framework: str, indicators: Dict) -> tuple:
        """
        Check if project matches framework indicators

        Args:
            framework: Framework name
            indicators: Framework indicators dict

        Returns:
            Tuple of (score, evidence_list)
        """
        score = 0
        evidence = []

        # Check for indicator files
        for filename in indicators['files']:
            found_files = FileHandler.find_files(str(self.project_path), filename)
            if found_files:
                score += 1
                evidence.append(f"Found file: {filename}")
                logger.debug(f"{framework}: Found {filename}")

        # Check for imports in Python/JS files
        file_patterns = ['*.py'] if framework in ['django', 'flask', 'fastapi'] else ['*.js', '*.ts']

        for pattern in file_patterns:
            files = list(self.project_path.rglob(pattern))[:20]  # Sample first 20 files

            for file_path in files:
                if self._is_excluded_path(str(file_path)):
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')

                    # Check imports
                    for import_pattern in indicators['imports']:
                        if import_pattern in content:
                            score += 0.5
                            evidence.append(f"Found import: {import_pattern} in {file_path.name}")
                            logger.debug(f"{framework}: Found import in {file_path.name}")
                            break  # One match per file is enough

                    # Check regex patterns
                    for regex_pattern in indicators['patterns']:
                        if re.search(regex_pattern, content):
                            score += 0.5
                            evidence.append(f"Found pattern: {regex_pattern} in {file_path.name}")
                            logger.debug(f"{framework}: Found pattern in {file_path.name}")
                            break  # One match per file is enough

                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")
                    continue

        return score, evidence[:5]  # Return top 5 evidence items

    def _detect_version(self, framework: str) -> Optional[str]:
        """
        Detect framework version

        Args:
            framework: Detected framework name

        Returns:
            Version string or None
        """
        if framework == 'unknown':
            return None

        # Check requirements.txt for Python frameworks
        if framework in ['django', 'flask', 'fastapi']:
            req_files = FileHandler.find_files(str(self.project_path), 'requirements.txt')

            for req_file in req_files:
                try:
                    content = Path(req_file).read_text(encoding='utf-8')

                    # Look for framework version
                    patterns = [
                        rf'{framework}==([0-9.]+)',
                        rf'{framework}>=([0-9.]+)',
                        rf'{framework}\[.*\]==([0-9.]+)'
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            return match.group(1)

                except Exception as e:
                    logger.debug(f"Error reading requirements.txt: {e}")

        # Check package.json for Node frameworks
        if framework in ['express']:
            package_files = FileHandler.find_files(str(self.project_path), 'package.json')

            for package_file in package_files:
                try:
                    import json
                    content = Path(package_file).read_text(encoding='utf-8')
                    package_data = json.loads(content)

                    dependencies = package_data.get('dependencies', {})
                    if framework in dependencies:
                        return dependencies[framework].lstrip('^~')

                except Exception as e:
                    logger.debug(f"Error reading package.json: {e}")

        return None

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from analysis"""
        excluded = [
            '__pycache__',
            'node_modules',
            '.git',
            'venv',
            'env',
            '.venv',
            'dist',
            'build',
            '.pytest_cache',
            '.mypy_cache'
        ]

        return any(excluded_dir in path for excluded_dir in excluded)


__all__ = ['FrameworkDetector']
