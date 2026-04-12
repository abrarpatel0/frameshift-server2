"""
Project Analyzer — Complexity Scoring & Feature Detection
Analyzes Django project files to determine conversion complexity,
detect Django-specific features that need manual post-conversion changes,
and categorize files for smart AI usage decisions.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


# ── Django features that require manual post-conversion attention ──
DJANGO_MIDDLEWARE_PATTERNS = [
    'MiddlewareMixin', 'BaseMiddleware', 'process_request',
    'process_response', 'process_view', 'process_exception',
    'process_template_response',
]

DJANGO_SIGNAL_PATTERNS = [
    'pre_save', 'post_save', 'pre_delete', 'post_delete',
    'pre_init', 'post_init', 'm2m_changed',
    'request_started', 'request_finished', 'got_request_exception',
    '@receiver', 'Signal()', 'django.dispatch',
]

DJANGO_TEMPLATE_TAG_PATTERNS = [
    'register = template.Library()', '@register.filter',
    '@register.simple_tag', '@register.inclusion_tag',
    '@register.tag', 'template.Library',
]

DJANGO_ADMIN_PATTERNS = [
    'admin.site.register', 'ModelAdmin', 'TabularInline',
    'StackedInline', 'admin.register',
]

DJANGO_CELERY_PATTERNS = [
    '@shared_task', '@app.task', 'celery_app',
    'from celery import', 'CELERY_',
]

DJANGO_REST_PATTERNS = [
    'rest_framework', 'APIView', 'ViewSet',
    'ModelViewSet', 'Serializer', 'ModelSerializer',
    'api_view', 'Response', 'permission_classes',
]

DJANGO_AUTH_PATTERNS = [
    'AbstractUser', 'AbstractBaseUser', 'PermissionsMixin',
    'CustomUserManager', 'UserCreationForm', 'AuthenticationForm',
    'login_required', '@permission_required', 'has_perm',
    'django.contrib.auth',
]

DJANGO_CACHE_PATTERNS = [
    'cache.get', 'cache.set', 'cache_page',
    '@cache_page', 'CACHES', 'django.core.cache',
]

# ── Third-party package mapping: Django → Flask equivalents ──
PACKAGE_MAPPING = {
    'django': 'Flask',
    'djangorestframework': 'Flask-RESTful / flask-smorest',
    'django-rest-framework': 'Flask-RESTful / flask-smorest',
    'django-filter': 'flask-filter / marshmallow',
    'django-cors-headers': 'Flask-CORS',
    'django-debug-toolbar': 'Flask-DebugToolbar',
    'django-allauth': 'Flask-Login + Flask-OAuthlib',
    'django-celery-beat': 'celery (works with both)',
    'django-celery-results': 'celery (works with both)',
    'celery': 'celery (works with both)',
    'django-redis': 'Flask-Caching[redis]',
    'django-storages': 'flask-reuploaded / boto3',
    'django-crispy-forms': 'Flask-WTF + Bootstrap-Flask',
    'django-extensions': 'Flask-Script (legacy) / Click CLI',
    'django-environ': 'python-dotenv',
    'django-model-utils': 'SQLAlchemy-Utils',
    'django-guardian': 'Flask-Principal',
    'django-mptt': 'sqlalchemy-mptt',
    'django-polymorphic': 'SQLAlchemy polymorphic',
    'django-import-export': 'flask-excel / openpyxl',
    'djangoql': 'N/A (custom implementation)',
    'django-channels': 'Flask-SocketIO',
    'django-haystack': 'Flask-WhooshAlchemy / Elasticsearch',
    'whitenoise': 'whitenoise (works with both)',
    'gunicorn': 'gunicorn (works with both)',
    'psycopg2': 'psycopg2 (works with both)',
    'psycopg2-binary': 'psycopg2-binary (works with both)',
    'Pillow': 'Pillow (works with both)',
    'boto3': 'boto3 (works with both)',
    'requests': 'requests (works with both)',
}


class ProjectAnalyzer:
    """
    Analyzes a Django project for complexity scoring, feature detection,
    and file categorization for optimized conversion.
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.excluded_dirs = {
            '.git', '__pycache__', 'node_modules', '.next',
            'venv', '.venv', 'env', '.idea', '.vscode', 'migrations',
        }

    def analyze(self) -> Dict[str, Any]:
        """
        Full project analysis: complexity scoring, feature detection,
        file categorization, and third-party package mapping.
        """
        logger.info(f"Running project analysis on: {self.project_path}")

        python_files = self._collect_python_files()
        template_files = self._collect_template_files()
        static_files = self._collect_static_files()

        # Score and categorize each file
        file_analyses = []
        for f in python_files:
            analysis = self._analyze_file(f)
            file_analyses.append(analysis)

        # Detect project-level features
        features = self._detect_project_features(file_analyses)

        # Detect third-party packages
        packages = self._detect_third_party_packages()

        # Categorize files by complexity
        categories = self._categorize_files(file_analyses)

        result = {
            'total_python_files': len(python_files),
            'total_template_files': len(template_files),
            'total_static_files': len(static_files),
            'file_analyses': file_analyses,
            'features': features,
            'third_party_packages': packages,
            'categories': categories,
            'overall_complexity': self._calculate_overall_complexity(file_analyses),
        }

        logger.info(
            f"Project analysis complete: {len(python_files)} Python files, "
            f"complexity={result['overall_complexity']:.1f}, "
            f"simple={len(categories['simple'])}, "
            f"medium={len(categories['medium'])}, "
            f"complex={len(categories['complex'])}"
        )

        return result

    # ── File Collection ──

    def _collect_python_files(self) -> List[Path]:
        files = []
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs and not d.startswith('.')]
            for fname in filenames:
                if fname.endswith('.py') and not fname.startswith('__'):
                    files.append(Path(root) / fname)
        return files

    def _collect_template_files(self) -> List[Path]:
        files = []
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for fname in filenames:
                if fname.endswith(('.html', '.txt', '.jinja', '.jinja2')):
                    files.append(Path(root) / fname)
        return files

    def _collect_static_files(self) -> List[Path]:
        files = []
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for fname in filenames:
                if fname.endswith(('.css', '.js', '.png', '.jpg', '.svg', '.gif', '.ico', '.woff', '.woff2')):
                    files.append(Path(root) / fname)
        return files

    # ── Per-File Analysis ──

    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single Python file for complexity and feature detection."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            logger.warning(f"Cannot read {file_path}: {e}")
            return {
                'path': str(file_path),
                'relative_path': str(file_path.relative_to(self.project_path)),
                'filename': file_path.name,
                'complexity_score': 50,
                'category': 'medium',
                'loc': 0,
                'features': [],
                'needs_ai': True,
                'error': str(e),
            }

        loc = len([l for l in content.split('\n') if l.strip() and not l.strip().startswith('#')])

        # AST-based complexity
        ast_complexity = self._calculate_ast_complexity(content)

        # Feature detection
        features = self._detect_file_features(content, file_path)

        # Compute composite complexity score (0-100)
        complexity = self._compute_complexity_score(loc, ast_complexity, features, file_path)

        # Determine category
        if complexity < 30:
            category = 'simple'
        elif complexity < 70:
            category = 'medium'
        else:
            category = 'complex'

        # Determine if AI is needed
        needs_ai = self._should_use_ai(complexity, features, loc, file_path)

        return {
            'path': str(file_path),
            'relative_path': str(file_path.relative_to(self.project_path)),
            'filename': file_path.name,
            'complexity_score': round(complexity, 1),
            'category': category,
            'loc': loc,
            'ast_complexity': ast_complexity,
            'features': features,
            'needs_ai': needs_ai,
        }

    def _calculate_ast_complexity(self, content: str) -> Dict[str, int]:
        """Calculate AST-based complexity metrics."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {'classes': 0, 'functions': 0, 'imports': 0, 'depth': 0, 'decorators': 0}

        classes = 0
        functions = 0
        imports = 0
        max_depth = 0
        decorators = 0

        def walk_depth(node, depth=0):
            nonlocal classes, functions, imports, max_depth, decorators
            max_depth = max(max_depth, depth)

            if isinstance(node, ast.ClassDef):
                classes += 1
                decorators += len(node.decorator_list)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
                decorators += len(node.decorator_list)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports += 1

            for child in ast.iter_child_nodes(node):
                walk_depth(child, depth + 1)

        walk_depth(tree)

        return {
            'classes': classes,
            'functions': functions,
            'imports': imports,
            'depth': max_depth,
            'decorators': decorators,
        }

    def _detect_file_features(self, content: str, file_path: Path) -> List[str]:
        """Detect Django-specific features used in a file."""
        features = []

        for pattern in DJANGO_MIDDLEWARE_PATTERNS:
            if pattern in content:
                features.append('custom_middleware')
                break

        for pattern in DJANGO_SIGNAL_PATTERNS:
            if pattern in content:
                features.append('django_signals')
                break

        for pattern in DJANGO_TEMPLATE_TAG_PATTERNS:
            if pattern in content:
                features.append('custom_template_tags')
                break

        for pattern in DJANGO_ADMIN_PATTERNS:
            if pattern in content:
                features.append('django_admin')
                break

        for pattern in DJANGO_CELERY_PATTERNS:
            if pattern in content:
                features.append('celery_tasks')
                break

        for pattern in DJANGO_REST_PATTERNS:
            if pattern in content:
                features.append('rest_framework')
                break

        for pattern in DJANGO_AUTH_PATTERNS:
            if pattern in content:
                features.append('custom_auth')
                break

        for pattern in DJANGO_CACHE_PATTERNS:
            if pattern in content:
                features.append('caching')
                break

        # Class-based views
        cbv_patterns = [
            'ListView', 'DetailView', 'CreateView', 'UpdateView',
            'DeleteView', 'FormView', 'TemplateView', 'RedirectView',
            'View', 'GenericAPIView',
        ]
        for pattern in cbv_patterns:
            if pattern in content:
                features.append('class_based_views')
                break

        # Management commands
        if 'BaseCommand' in content or 'management/commands' in str(file_path):
            features.append('management_commands')

        # Custom context processors
        if 'context_processor' in str(file_path) or 'def context' in content:
            features.append('context_processors')

        # Django forms with complex validation
        if 'clean_' in content and 'forms' in str(file_path):
            features.append('complex_form_validation')

        # File/Image fields
        if 'FileField' in content or 'ImageField' in content:
            features.append('file_uploads')

        return list(set(features))

    def _compute_complexity_score(
        self,
        loc: int,
        ast_complexity: Dict[str, int],
        features: List[str],
        file_path: Path,
    ) -> float:
        """Compute a 0-100 complexity score for a file."""
        score = 0.0

        # Lines of code contribution (0-30 points)
        if loc <= 20:
            score += 5
        elif loc <= 50:
            score += 10
        elif loc <= 100:
            score += 18
        elif loc <= 200:
            score += 25
        else:
            score += 30

        # AST complexity (0-30 points)
        score += min(ast_complexity['classes'] * 4, 12)
        score += min(ast_complexity['functions'] * 2, 10)
        score += min(ast_complexity['depth'] * 1, 8)

        # Feature complexity (0-40 points)
        complex_features = {
            'custom_middleware': 10,
            'django_signals': 8,
            'custom_template_tags': 7,
            'rest_framework': 8,
            'custom_auth': 9,
            'celery_tasks': 7,
            'class_based_views': 6,
            'management_commands': 5,
            'complex_form_validation': 6,
            'file_uploads': 4,
            'context_processors': 5,
            'caching': 5,
            'django_admin': 3,
        }

        feature_score = sum(complex_features.get(f, 2) for f in features)
        score += min(feature_score, 40)

        return min(score, 100.0)

    def _should_use_ai(
        self,
        complexity: float,
        features: List[str],
        loc: int,
        file_path: Path,
    ) -> bool:
        """Determine if a file needs AI-powered conversion."""
        # Always skip AI for certain file types
        filename = file_path.name
        if filename in ('__init__.py', 'apps.py', 'tests.py', 'manage.py', 'wsgi.py', 'asgi.py'):
            return False
        if filename == 'admin.py' and 'custom_auth' not in features:
            return False
        if filename == 'settings.py':
            return False

        # Skip AI for very simple files
        if complexity < 25 and loc < 50:
            return False

        # Use AI for complex files
        if complexity >= 70:
            return True

        # Use AI for files with complex features
        ai_required_features = {
            'custom_middleware', 'django_signals', 'rest_framework',
            'custom_auth', 'celery_tasks', 'class_based_views',
            'management_commands',
        }
        if any(f in ai_required_features for f in features):
            return True

        # Use AI for large files
        if loc > 200:
            return True

        # Default: medium files use pattern matching, not AI
        return False

    # ── Project-Level Analysis ──

    def _detect_project_features(self, file_analyses: List[Dict]) -> Dict[str, Any]:
        """Aggregate features detected across all files."""
        all_features = set()
        for fa in file_analyses:
            all_features.update(fa.get('features', []))

        return {
            'has_custom_middleware': 'custom_middleware' in all_features,
            'has_django_signals': 'django_signals' in all_features,
            'has_custom_template_tags': 'custom_template_tags' in all_features,
            'has_django_admin': 'django_admin' in all_features,
            'has_celery_tasks': 'celery_tasks' in all_features,
            'has_rest_framework': 'rest_framework' in all_features,
            'has_custom_auth': 'custom_auth' in all_features,
            'has_caching': 'caching' in all_features,
            'has_class_based_views': 'class_based_views' in all_features,
            'has_management_commands': 'management_commands' in all_features,
            'has_context_processors': 'context_processors' in all_features,
            'has_file_uploads': 'file_uploads' in all_features,
            'all_features': sorted(all_features),
        }

    def _detect_third_party_packages(self) -> Dict[str, Any]:
        """Detect third-party packages from requirements.txt and map to Flask equivalents."""
        req_files = FileHandler.find_files(str(self.project_path), 'requirements.txt')
        packages_found = {}

        for req_file in req_files:
            try:
                content = FileHandler.read_file(str(req_file))
                for line in content.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue

                    # Parse package name (handle ==, >=, <=, ~=, etc.)
                    pkg_name = re.split(r'[=<>~!]', line)[0].strip().lower()
                    version = line[len(pkg_name):].strip() if pkg_name else ''

                    flask_equivalent = PACKAGE_MAPPING.get(pkg_name)
                    if flask_equivalent:
                        packages_found[pkg_name] = {
                            'django_package': line.strip(),
                            'flask_equivalent': flask_equivalent,
                            'version': version,
                            'needs_replacement': not flask_equivalent.endswith('(works with both)'),
                        }
                    elif pkg_name and pkg_name != 'django':
                        # Unknown package — keep as-is, might work with Flask
                        packages_found[pkg_name] = {
                            'django_package': line.strip(),
                            'flask_equivalent': f'{pkg_name} (review compatibility)',
                            'version': version,
                            'needs_replacement': False,
                        }
            except Exception as e:
                logger.warning(f"Cannot read requirements file {req_file}: {e}")

        return packages_found

    # ── File Categorization ──

    def _categorize_files(self, file_analyses: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize files into simple/medium/complex for parallel processing."""
        categories = {'simple': [], 'medium': [], 'complex': []}
        for fa in file_analyses:
            cat = fa.get('category', 'medium')
            categories[cat].append(fa)
        return categories

    def _calculate_overall_complexity(self, file_analyses: List[Dict]) -> float:
        """Calculate weighted average complexity for the entire project."""
        if not file_analyses:
            return 0.0
        total = sum(fa.get('complexity_score', 50) for fa in file_analyses)
        return total / len(file_analyses)


__all__ = ['ProjectAnalyzer']
