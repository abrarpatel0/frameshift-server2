"""
Manual Changes Generator — Post-Conversion Analysis Engine
Generates an intelligent, priority-based checklist of manual changes
users need to make after Django→Flask conversion.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from ..utils.logger import logger


# ── Change Templates ──

CRITICAL_CHANGES = {
    'database_config': {
        'title': 'Configure database connection',
        'description': 'Flask uses SQLALCHEMY_DATABASE_URI instead of Django DATABASES dict.',
        'file': 'config.py',
        'django_code': "DATABASES = {\n    'default': {\n        'ENGINE': 'django.db.backends.postgresql',\n        'NAME': 'mydb',\n    }\n}",
        'flask_code': "SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/mydb'\nSQLALCHEMY_TRACK_MODIFICATIONS = False",
        'reason': 'Flask-SQLAlchemy uses a single URI string instead of a dict.',
        'install_cmd': 'pip install Flask-SQLAlchemy psycopg2-binary',
    },
    'secret_key': {
        'title': 'Set Flask SECRET_KEY',
        'description': 'Generate a new secret key for your Flask application.',
        'file': 'config.py',
        'django_code': "SECRET_KEY = 'django-insecure-...'",
        'flask_code': "import secrets\nSECRET_KEY = secrets.token_hex(32)",
        'reason': 'Flask needs a secret key for sessions and CSRF protection.',
    },
    'install_dependencies': {
        'title': 'Install Flask dependencies',
        'description': 'Install all required Flask packages.',
        'file': 'requirements.txt',
        'flask_code': "pip install Flask Flask-SQLAlchemy Flask-Login Flask-WTF Flask-Migrate",
        'reason': 'Flask ecosystem uses separate packages for features Django bundles.',
    },
    'app_initialization': {
        'title': 'Verify Flask app initialization',
        'description': 'Ensure app.py properly initializes Flask, db, and login_manager.',
        'file': 'app.py',
        'django_code': "# Django auto-configures from settings.py",
        'flask_code': "from flask import Flask\nfrom flask_sqlalchemy import SQLAlchemy\nfrom flask_login import LoginManager\n\napp = Flask(__name__)\napp.config.from_object('config')\ndb = SQLAlchemy(app)\nlogin_manager = LoginManager(app)",
        'reason': 'Flask requires explicit initialization of extensions.',
    },
}

MIDDLEWARE_CHANGE = {
    'title': 'Convert custom middleware to Flask',
    'description': 'Django middleware must be converted to Flask before_request/after_request hooks or decorators.',
    'django_code': "class MyMiddleware(MiddlewareMixin):\n    def process_request(self, request):\n        # ...\n    def process_response(self, request, response):\n        # ...",
    'flask_code': "@app.before_request\ndef my_before_request():\n    # equivalent of process_request\n    pass\n\n@app.after_request\ndef my_after_request(response):\n    # equivalent of process_response\n    return response",
    'reason': 'Flask uses decorator-based request hooks instead of middleware classes.',
}

SIGNALS_CHANGE = {
    'title': 'Convert Django signals to Flask-Blinker signals',
    'description': 'Django signals (pre_save, post_save, etc.) need to be converted to Blinker signals or SQLAlchemy events.',
    'django_code': "from django.db.models.signals import post_save\nfrom django.dispatch import receiver\n\n@receiver(post_save, sender=MyModel)\ndef my_handler(sender, instance, **kwargs):\n    pass",
    'flask_code': "from sqlalchemy import event\n\n@event.listens_for(MyModel, 'after_insert')\ndef my_handler(mapper, connection, target):\n    pass\n\n# Or use Blinker:\nfrom blinker import signal\nmy_signal = signal('my-signal')",
    'reason': 'Flask/SQLAlchemy uses SQLAlchemy events or Blinker signals instead of Django signals.',
    'install_cmd': 'pip install blinker',
}

TEMPLATE_TAGS_CHANGE = {
    'title': 'Convert custom template tags to Jinja2 extensions',
    'description': 'Custom Django template tags and filters must become Jinja2 filters/extensions.',
    'django_code': "@register.filter\ndef my_filter(value):\n    return value.upper()\n\n@register.simple_tag\ndef my_tag(*args):\n    return '...'",
    'flask_code': "# Register as Jinja2 filter in app.py:\n@app.template_filter('my_filter')\ndef my_filter(value):\n    return value.upper()\n\n# Or add to Jinja2 globals:\napp.jinja_env.globals['my_tag'] = my_tag_function",
    'reason': 'Jinja2 (Flask\'s template engine) uses different extension mechanisms.',
}

REST_FRAMEWORK_CHANGE = {
    'title': 'Migrate Django REST Framework to Flask-RESTful',
    'description': 'DRF serializers, viewsets, and routers need to be rewritten for Flask-RESTful or flask-smorest.',
    'django_code': "class MySerializer(serializers.ModelSerializer):\n    class Meta:\n        model = MyModel\n        fields = '__all__'\n\nclass MyViewSet(viewsets.ModelViewSet):\n    serializer_class = MySerializer",
    'flask_code': "from flask_restful import Resource, Api\nfrom marshmallow import Schema, fields\n\nclass MySchema(Schema):\n    id = fields.Int()\n    name = fields.Str()\n\nclass MyResource(Resource):\n    def get(self, id):\n        item = MyModel.query.get_or_404(id)\n        return MySchema().dump(item)",
    'reason': 'DRF concepts (serializers, viewsets, routers) don\'t exist in Flask.',
    'install_cmd': 'pip install Flask-RESTful marshmallow',
}

CELERY_CHANGE = {
    'title': 'Update Celery configuration for Flask',
    'description': 'Celery works with both Django and Flask, but configuration format differs.',
    'django_code': "# settings.py\nCELERY_BROKER_URL = 'redis://localhost:6379/0'\n\n# celery.py\nfrom celery import Celery\napp = Celery('myproject')\napp.config_from_object('django.conf:settings', namespace='CELERY')",
    'flask_code': "# config.py\nCELERY_BROKER_URL = 'redis://localhost:6379/0'\n\n# celery_worker.py\nfrom celery import Celery\n\ndef make_celery(app):\n    celery = Celery(app.import_name)\n    celery.conf.update(app.config)\n    return celery",
    'reason': 'Celery initialization pattern is different for Flask applications.',
}

AUTH_CHANGE = {
    'title': 'Set up Flask-Login authentication',
    'description': 'Django\'s built-in auth must be replaced with Flask-Login.',
    'django_code': "from django.contrib.auth.decorators import login_required\nfrom django.contrib.auth import authenticate, login, logout",
    'flask_code': "from flask_login import LoginManager, login_required, login_user, logout_user, current_user\n\nlogin_manager = LoginManager()\nlogin_manager.init_app(app)\nlogin_manager.login_view = 'auth.login'\n\n@login_manager.user_loader\ndef load_user(user_id):\n    return User.query.get(int(user_id))",
    'reason': 'Flask uses Flask-Login instead of Django\'s built-in auth system.',
    'install_cmd': 'pip install Flask-Login',
}

CSRF_CHANGE = {
    'title': 'Configure CSRF protection',
    'description': 'Django has automatic CSRF; Flask needs Flask-WTF.',
    'django_code': "# Django: automatic via middleware\n{% csrf_token %}",
    'flask_code': "from flask_wtf.csrf import CSRFProtect\ncsrf = CSRFProtect(app)\n\n# In templates:\n{{ form.hidden_tag() }}\n# Or for AJAX:\n<meta name=\"csrf-token\" content=\"{{ csrf_token() }}\">",
    'reason': 'Flask requires explicit CSRF protection via Flask-WTF.',
    'install_cmd': 'pip install Flask-WTF',
}

STATIC_FILES_CHANGE = {
    'title': 'Configure static file serving',
    'description': 'Update static file references in templates.',
    'django_code': "{% load static %}\n<link href=\"{% static 'css/style.css' %}\" rel=\"stylesheet\">",
    'flask_code': "<link href=\"{{ url_for('static', filename='css/style.css') }}\" rel=\"stylesheet\">",
    'reason': 'Flask uses url_for() instead of Django\'s {% static %} tag.',
}

MIGRATIONS_CHANGE = {
    'title': 'Set up Flask-Migrate for database migrations',
    'description': 'Replace Django\'s built-in migrations with Flask-Migrate (Alembic).',
    'django_code': "python manage.py makemigrations\npython manage.py migrate",
    'flask_code': "# Initialize:\nflask db init\n\n# Create migration:\nflask db migrate -m 'Initial migration'\n\n# Apply:\nflask db upgrade",
    'reason': 'Flask uses Alembic (via Flask-Migrate) instead of Django\'s migration system.',
    'install_cmd': 'pip install Flask-Migrate',
}


class ManualChangesGenerator:
    """
    Generates a structured manual changes guide after Django→Flask conversion.
    Analyzes what couldn't be auto-converted and provides actionable instructions.
    """

    def __init__(self, django_path: str, flask_path: str, project_analysis: Dict = None):
        self.django_path = Path(django_path)
        self.flask_path = Path(flask_path)
        self.project_analysis = project_analysis or {}

    def generate(self) -> Dict[str, Any]:
        """
        Generate the complete manual changes guide.
        Returns structured JSON with critical/important/optional changes.
        """
        logger.info("Generating manual changes guide...")

        features = self.project_analysis.get('features', {})
        packages = self.project_analysis.get('third_party_packages', {})

        critical = self._generate_critical_changes(features)
        important = self._generate_important_changes(features, packages)
        optional = self._generate_optional_changes(features, packages)
        dependencies = self._generate_dependency_map(packages)
        testing = self._generate_testing_checklist(features)

        result = {
            'critical': critical,
            'important': important,
            'optional': optional,
            'dependencies': dependencies,
            'testing_checklist': testing,
            'summary': {
                'total_changes': len(critical) + len(important) + len(optional),
                'critical_count': len(critical),
                'important_count': len(important),
                'optional_count': len(optional),
                'estimated_time_minutes': self._estimate_time(critical, important, optional),
            },
        }

        logger.info(
            f"Manual changes guide generated: "
            f"{len(critical)} critical, {len(important)} important, "
            f"{len(optional)} optional changes"
        )

        return result

    def _generate_critical_changes(self, features: Dict) -> List[Dict]:
        """Generate critical changes (app won't start without these)."""
        changes = []

        # Always needed
        changes.append({
            'id': 'database_config',
            **CRITICAL_CHANGES['database_config'],
            'priority': 'critical',
            'completed': False,
        })

        changes.append({
            'id': 'secret_key',
            **CRITICAL_CHANGES['secret_key'],
            'priority': 'critical',
            'completed': False,
        })

        changes.append({
            'id': 'install_dependencies',
            **CRITICAL_CHANGES['install_dependencies'],
            'priority': 'critical',
            'completed': False,
        })

        changes.append({
            'id': 'app_initialization',
            **CRITICAL_CHANGES['app_initialization'],
            'priority': 'critical',
            'completed': False,
        })

        # Custom middleware is critical if detected
        if features.get('has_custom_middleware'):
            middleware_files = self._find_files_with_feature('custom_middleware')
            changes.append({
                'id': 'custom_middleware',
                **MIDDLEWARE_CHANGE,
                'priority': 'critical',
                'files': middleware_files,
                'completed': False,
            })

        # CSRF protection is critical
        changes.append({
            'id': 'csrf_protection',
            **CSRF_CHANGE,
            'priority': 'critical',
            'completed': False,
        })

        return changes

    def _generate_important_changes(self, features: Dict, packages: Dict) -> List[Dict]:
        """Generate important changes (features will break without these)."""
        changes = []

        if features.get('has_django_signals'):
            signal_files = self._find_files_with_feature('django_signals')
            changes.append({
                'id': 'django_signals',
                **SIGNALS_CHANGE,
                'priority': 'important',
                'files': signal_files,
                'completed': False,
            })

        if features.get('has_custom_template_tags'):
            tag_files = self._find_files_with_feature('custom_template_tags')
            changes.append({
                'id': 'custom_template_tags',
                **TEMPLATE_TAGS_CHANGE,
                'priority': 'important',
                'files': tag_files,
                'completed': False,
            })

        if features.get('has_rest_framework'):
            rest_files = self._find_files_with_feature('rest_framework')
            changes.append({
                'id': 'rest_framework',
                **REST_FRAMEWORK_CHANGE,
                'priority': 'important',
                'files': rest_files,
                'completed': False,
            })

        if features.get('has_custom_auth'):
            auth_files = self._find_files_with_feature('custom_auth')
            changes.append({
                'id': 'authentication',
                **AUTH_CHANGE,
                'priority': 'important',
                'files': auth_files,
                'completed': False,
            })

        if features.get('has_celery_tasks'):
            celery_files = self._find_files_with_feature('celery_tasks')
            changes.append({
                'id': 'celery_tasks',
                **CELERY_CHANGE,
                'priority': 'important',
                'files': celery_files,
                'completed': False,
            })

        # Static files always need attention
        changes.append({
            'id': 'static_files',
            **STATIC_FILES_CHANGE,
            'priority': 'important',
            'completed': False,
        })

        # Packages that need replacement
        for pkg_name, pkg_info in packages.items():
            if pkg_info.get('needs_replacement'):
                changes.append({
                    'id': f'package_{pkg_name}',
                    'title': f'Replace {pkg_name} with Flask equivalent',
                    'description': f'Django package `{pkg_info["django_package"]}` needs to be replaced.',
                    'file': 'requirements.txt',
                    'django_code': f'# requirements.txt\n{pkg_info["django_package"]}',
                    'flask_code': f'# requirements.txt\n# Replace with: {pkg_info["flask_equivalent"]}',
                    'reason': f'{pkg_name} is Django-specific. Use {pkg_info["flask_equivalent"]} for Flask.',
                    'priority': 'important',
                    'completed': False,
                })

        return changes

    def _generate_optional_changes(self, features: Dict, packages: Dict) -> List[Dict]:
        """Generate optional improvements."""
        changes = []

        # Database migrations
        changes.append({
            'id': 'flask_migrate',
            **MIGRATIONS_CHANGE,
            'priority': 'optional',
            'completed': False,
        })

        # Flask-Admin if Django admin was used
        if features.get('has_django_admin'):
            changes.append({
                'id': 'flask_admin',
                'title': 'Set up Flask-Admin for admin interface',
                'description': 'Replace Django admin with Flask-Admin for model management.',
                'file': 'admin.py',
                'django_code': "from django.contrib import admin\nadmin.site.register(MyModel)",
                'flask_code': "from flask_admin import Admin\nfrom flask_admin.contrib.sqla import ModelView\n\nadmin = Admin(app, name='MyApp Admin')\nadmin.add_view(ModelView(MyModel, db.session))",
                'reason': 'Flask-Admin provides similar functionality to Django admin.',
                'install_cmd': 'pip install Flask-Admin',
                'priority': 'optional',
                'completed': False,
            })

        # Flask-Caching
        if features.get('has_caching'):
            changes.append({
                'id': 'flask_caching',
                'title': 'Set up Flask-Caching',
                'description': 'Replace Django cache framework with Flask-Caching.',
                'file': 'config.py',
                'django_code': "CACHES = {\n    'default': {\n        'BACKEND': 'django.core.cache.backends.redis.RedisCache',\n        'LOCATION': 'redis://localhost:6379',\n    }\n}",
                'flask_code': "from flask_caching import Cache\ncache = Cache(app, config={'CACHE_TYPE': 'redis', 'CACHE_REDIS_URL': 'redis://localhost:6379/0'})",
                'reason': 'Flask uses Flask-Caching instead of Django\'s cache framework.',
                'install_cmd': 'pip install Flask-Caching',
                'priority': 'optional',
                'completed': False,
            })

        # Error handling
        changes.append({
            'id': 'error_handlers',
            'title': 'Add Flask error handlers',
            'description': 'Django has built-in error views; Flask needs explicit error handlers.',
            'file': 'app.py',
            'django_code': "# Django: handler404, handler500 in urls.py",
            'flask_code': "@app.errorhandler(404)\ndef not_found(e):\n    return render_template('404.html'), 404\n\n@app.errorhandler(500)\ndef server_error(e):\n    return render_template('500.html'), 500",
            'reason': 'Flask needs explicit error handlers for HTTP error pages.',
            'priority': 'optional',
            'completed': False,
        })

        # Logging configuration
        changes.append({
            'id': 'logging_config',
            'title': 'Configure Flask logging',
            'description': 'Set up proper logging for your Flask application.',
            'file': 'app.py',
            'django_code': "# Django: LOGGING dict in settings.py",
            'flask_code': "import logging\nfrom logging.handlers import RotatingFileHandler\n\nif not app.debug:\n    handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)\n    handler.setLevel(logging.INFO)\n    app.logger.addHandler(handler)",
            'reason': 'Flask logging is configured differently from Django\'s LOGGING dict.',
            'priority': 'optional',
            'completed': False,
        })

        # Environment variables
        changes.append({
            'id': 'env_variables',
            'title': 'Set up environment variables',
            'description': 'Configure .env file and python-dotenv for Flask.',
            'file': '.env',
            'flask_code': "FLASK_APP=app.py\nFLASK_ENV=development\nSECRET_KEY=your-secret-key\nDATABASE_URL=postgresql://...\n\n# In app.py:\nfrom dotenv import load_dotenv\nload_dotenv()",
            'reason': 'Flask uses python-dotenv for environment variable management.',
            'install_cmd': 'pip install python-dotenv',
            'priority': 'optional',
            'completed': False,
        })

        return changes

    def _generate_dependency_map(self, packages: Dict) -> Dict[str, Any]:
        """Generate Flask requirements.txt with package equivalents."""
        flask_requirements = [
            'Flask>=3.0',
            'Flask-SQLAlchemy>=3.1',
            'Flask-Login>=0.6',
            'Flask-WTF>=1.2',
            'Flask-Migrate>=4.0',
        ]

        for pkg_name, pkg_info in packages.items():
            equiv = pkg_info.get('flask_equivalent', '')
            if equiv and not equiv.endswith('(works with both)'):
                # Extract just the package name from the description
                flask_pkg = equiv.split('/')[0].strip()
                if flask_pkg and flask_pkg != 'N/A':
                    flask_requirements.append(flask_pkg)
            elif equiv.endswith('(works with both)'):
                # Keep the original package
                flask_requirements.append(pkg_info['django_package'])

        return {
            'flask_requirements': sorted(set(flask_requirements)),
            'package_mapping': packages,
        }

    def _generate_testing_checklist(self, features: Dict) -> List[Dict]:
        """Generate testing checklist."""
        checklist = [
            {
                'id': 'test_db',
                'title': 'Test database connections',
                'description': 'Verify database connectivity and model operations.',
                'command': 'flask shell\n>>> from app import db\n>>> db.create_all()',
                'completed': False,
            },
            {
                'id': 'test_routes',
                'title': 'Test all API endpoints / routes',
                'description': 'Verify each route returns expected responses.',
                'command': 'flask routes  # List all registered routes',
                'completed': False,
            },
            {
                'id': 'test_templates',
                'title': 'Test template rendering',
                'description': 'Check all pages render without Jinja2 errors.',
                'completed': False,
            },
            {
                'id': 'test_static',
                'title': 'Test static file serving',
                'description': 'Verify CSS, JS, and images load correctly.',
                'completed': False,
            },
        ]

        if features.get('has_custom_auth'):
            checklist.append({
                'id': 'test_auth',
                'title': 'Test authentication flow',
                'description': 'Verify login, logout, registration, and password reset.',
                'completed': False,
            })

        if features.get('has_rest_framework'):
            checklist.append({
                'id': 'test_api',
                'title': 'Test REST API endpoints',
                'description': 'Verify API serialization, authentication, and responses.',
                'completed': False,
            })

        if features.get('has_celery_tasks'):
            checklist.append({
                'id': 'test_celery',
                'title': 'Test Celery task execution',
                'description': 'Verify async tasks run correctly with Flask context.',
                'completed': False,
            })

        if features.get('has_file_uploads'):
            checklist.append({
                'id': 'test_uploads',
                'title': 'Test file upload functionality',
                'description': 'Verify file upload, storage, and retrieval.',
                'completed': False,
            })

        return checklist

    def _find_files_with_feature(self, feature: str) -> List[str]:
        """Find files that contain a specific feature."""
        file_analyses = self.project_analysis.get('file_analyses', [])
        result = []
        for fa in file_analyses:
            if feature in fa.get('features', []):
                result.append(fa.get('relative_path', fa.get('filename', 'unknown')))
        return result

    def _estimate_time(
        self,
        critical: List[Dict],
        important: List[Dict],
        optional: List[Dict],
    ) -> int:
        """Estimate time in minutes to complete all manual changes."""
        # Rough estimates: critical=3min each, important=5min, optional=2min
        return len(critical) * 3 + len(important) * 5 + len(optional) * 2


__all__ = ['ManualChangesGenerator']
