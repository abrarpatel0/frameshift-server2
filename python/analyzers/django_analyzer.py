import os
import ast
from pathlib import Path
from typing import Dict, List, Optional
from ..utils.file_handler import FileHandler
from ..utils.logger import logger


class DjangoAnalyzer:
    """Analyze Django project structure and components"""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.excluded_dirs = {
            '.git', '__pycache__', 'node_modules', '.next',
            'venv', '.venv', 'env', '.idea', '.vscode'
        }
        self.structure = {
            'apps': [],
            'models': [],
            'views': [],
            'urls': [],
            'templates': [],
            'static_files': [],
            'settings': None,
            'manage_py': None,
            'requirements': None,
            'django_version': None
        }

    def analyze(self) -> Dict:
        """
        Analyze Django project and return structure information

        Returns:
            Dictionary containing project structure
        """
        logger.info(f"Analyzing Django project at: {self.project_path}")

        # Find manage.py (indicates Django project root)
        self.structure['manage_py'] = self._find_manage_py()

        # Find settings.py
        self.structure['settings'] = self._find_settings()

        # Detect Django version
        self.structure['django_version'] = self._detect_django_version()

        # Find Django apps
        self.structure['apps'] = self._find_apps()

        # Find models
        self.structure['models'] = self._find_models()

        # Find views
        self.structure['views'] = self._find_views()

        # Find URL configurations
        self.structure['urls'] = self._find_urls()

        # Find templates
        self.structure['templates'] = self._find_templates()

        # Find static files
        self.structure['static_files'] = self._find_static_files()

        # Find requirements.txt
        self.structure['requirements'] = self._find_requirements()

        logger.info(f"Analysis complete. Found {len(self.structure['apps'])} apps")

        return self.structure

    def _find_manage_py(self) -> Optional[str]:
        """Find manage.py file"""
        manage_files = FileHandler.find_files(str(self.project_path), 'manage.py')
        if manage_files:
            logger.info(f"Found manage.py: {manage_files[0]}")
            return str(manage_files[0])
        return None

    def _find_settings(self) -> Optional[Dict]:
        """Find and parse settings.py"""
        settings_files = FileHandler.find_files(str(self.project_path), 'settings.py')

        for settings_file in settings_files:
            # Skip __pycache__ and other non-relevant files
            if '__pycache__' in str(settings_file):
                continue

            logger.info(f"Found settings.py: {settings_file}")

            try:
                content = FileHandler.read_file(str(settings_file))
                return {
                    'path': str(settings_file),
                    'content': content,
                    'installed_apps': self._extract_installed_apps(content),
                    'databases': self._extract_databases(content)
                }
            except Exception as e:
                logger.error(f"Failed to read settings.py: {e}")

        return None

    def _extract_installed_apps(self, settings_content: str) -> List[str]:
        """Extract INSTALLED_APPS from settings"""
        try:
            tree = ast.parse(settings_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'INSTALLED_APPS':
                            if isinstance(node.value, ast.List):
                                apps = []
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        apps.append(elt.value)
                                return apps
        except Exception as e:
            logger.error(f"Failed to extract INSTALLED_APPS: {e}")

        return []

    def _extract_databases(self, settings_content: str) -> Dict:
        """Extract DATABASES configuration from settings"""
        # Simplified extraction - can be enhanced
        if 'sqlite3' in settings_content:
            return {'default': 'sqlite3'}
        elif 'postgresql' in settings_content:
            return {'default': 'postgresql'}
        elif 'mysql' in settings_content:
            return {'default': 'mysql'}
        return {}

    def _detect_django_version(self) -> Optional[str]:
        """Detect Django version from requirements or imports"""
        # Try to find version in requirements.txt
        requirements = self._find_requirements()
        if requirements:
            content = FileHandler.read_file(requirements)
            for line in content.split('\n'):
                if 'django' in line.lower() and '==' in line:
                    version = line.split('==')[1].strip()
                    logger.info(f"Detected Django version: {version}")
                    return version

        return None

    def _find_apps(self) -> List[Dict]:
        """Find Django apps in project"""
        apps = []

        # Look for directories containing apps.py or models.py
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs and not d.startswith('.')]

            if 'apps.py' in files or 'models.py' in files:
                item = Path(root)
                app_info = {
                    'name': item.name,
                    'path': str(item),
                    'has_models': 'models.py' in files,
                    'has_views': 'views.py' in files,
                    'has_urls': 'urls.py' in files,
                    'has_admin': 'admin.py' in files,
                    'has_tests': 'tests.py' in files
                }
                apps.append(app_info)
                logger.debug(f"Found app: {item.name}")

        return apps

    def _find_models(self) -> List[str]:
        """Find all models.py files"""
        model_files = FileHandler.find_files(str(self.project_path), 'models.py')
        # Filter out __pycache__
        model_files = [str(f) for f in model_files if '__pycache__' not in str(f)]
        logger.info(f"Found {len(model_files)} model files")
        return model_files

    def _find_views(self) -> List[str]:
        """Find all views.py files"""
        view_files = FileHandler.find_files(str(self.project_path), 'views.py')
        view_files = [str(f) for f in view_files if '__pycache__' not in str(f)]
        logger.info(f"Found {len(view_files)} view files")
        return view_files

    def _find_urls(self) -> List[str]:
        """Find all urls.py files"""
        url_files = FileHandler.find_files(str(self.project_path), 'urls.py')
        url_files = [str(f) for f in url_files if '__pycache__' not in str(f)]
        logger.info(f"Found {len(url_files)} URL configuration files")
        return url_files

    def _find_templates(self) -> List[str]:
        """Find all template files"""
        template_extensions = ['*.html', '*.txt']
        templates = []

        for ext in template_extensions:
            found = FileHandler.find_files(str(self.project_path), ext)
            templates.extend([str(f) for f in found])

        logger.info(f"Found {len(templates)} template files")
        return templates

    def _find_static_files(self) -> List[str]:
        """Find static files"""
        static_extensions = ['*.css', '*.js', '*.png', '*.jpg', '*.svg']
        static_files = []

        for ext in static_extensions:
            found = FileHandler.find_files(str(self.project_path), ext)
            static_files.extend([str(f) for f in found])

        logger.info(f"Found {len(static_files)} static files")
        return static_files

    def _find_requirements(self) -> Optional[str]:
        """Find requirements.txt"""
        req_files = FileHandler.find_files(str(self.project_path), 'requirements.txt')
        if req_files:
            return str(req_files[0])
        return None


__all__ = ['DjangoAnalyzer']
