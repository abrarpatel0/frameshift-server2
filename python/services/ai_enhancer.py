"""
AI-Powered Conversion Enhancer using Google Gemini
Fixes critical issues that regex-based converters miss
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import concurrent.futures
from ..utils.logger import logger  # type: ignore
from ..providers import OpenAIProvider, GeminiProvider, ClaudeProvider, CustomProvider  # type: ignore


class AIEnhancer:
    """
    Uses Google Gemini to enhance converted Flask code
    Focuses on fixing specific high-impact issues
    """

    def __init__(self, api_key: str, provider: str = 'gemini', model: Optional[str] = None, endpoint: Optional[str] = None):
        self.api_key = api_key
        self.provider_name = (provider or 'gemini').strip().lower()
        self.model_name = model
        self.endpoint = endpoint
        self.enhancements_applied: List[str] = []
        self.provider: Any = None
        self.enabled = bool(api_key)

        if not self.enabled:
            logger.warning("AI Enhancer disabled (missing API key)")
            return

        try:
            self.provider = self._create_provider()
            if hasattr(self.provider, 'enabled') and not self.provider.enabled:
                self.enabled = False
                logger.warning(f"AI provider '{self.provider_name}' is not ready; enhancer disabled")
                return
            logger.info(f"AI Enhancer initialized with provider: {self.provider_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider '{self.provider_name}': {e}")
            self.enabled = False

    def _create_provider(self):
        if self.provider_name == 'openai':
            if OpenAIProvider is None:
                raise RuntimeError('OpenAI provider is unavailable in this runtime')
            return OpenAIProvider(
                api_key=self.api_key,
                model=self.model_name or 'gpt-4o',
                endpoint=self.endpoint or 'https://api.openai.com/v1'
            )

        if self.provider_name == 'gemini':
            if GeminiProvider is None:
                raise RuntimeError('Gemini provider is unavailable in this runtime')
            return GeminiProvider(
                api_key=self.api_key,
                model=self.model_name or 'gemini-2.5-flash',
                endpoint=self.endpoint
            )

        if self.provider_name == 'claude':
            if ClaudeProvider is None:
                raise RuntimeError('Claude provider is unavailable in this runtime')
            return ClaudeProvider(
                api_key=self.api_key,
                model=self.model_name or 'claude-3-5-sonnet-latest',
                endpoint=self.endpoint or 'https://api.anthropic.com/v1'
            )

        if self.provider_name == 'custom':
            if CustomProvider is None:
                raise RuntimeError('Custom provider is unavailable in this runtime')
            return CustomProvider(
                api_key=self.api_key,
                model=self.model_name or 'default-model',
                endpoint=self.endpoint or ''
            )

        raise ValueError(f"Unsupported AI provider: {self.provider_name}")

    def enhance_conversion(self, project_path: Path, models_result: Dict, views_result: Dict) -> Dict:
        """
        Main enhancement entry point
        Applies AI fixes to converted code
        """
        if not self.enabled:
            return {'enabled': False, 'applied': []}

        logger.info(f"Starting AI enhancement for project: {project_path}")

        models_files = list(project_path.rglob('models.py'))
        routes_files = list(project_path.rglob('routes.py'))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            model_futures = [executor.submit(self._process_single_model, f) for f in models_files]  # type: ignore
            route_futures = [executor.submit(self._process_single_route, f) for f in routes_files]  # type: ignore
            concurrent.futures.wait(model_futures + route_futures)

        return {
            'enabled': True,
            'applied': self.enhancements_applied
        }

    def _process_single_model(self, models_file: Path):
        try:
            content = models_file.read_text(encoding='utf-8')

            # Check if AbstractUser is used
            if 'AbstractUser' not in content and 'AbstractBaseUser' not in content:
                return

            logger.info(f"Found AbstractUser in {models_file}")

            # Use Gemini to fix it
            fixed_content = self._fix_abstract_user_with_ai(content, models_file.name)

            if fixed_content and fixed_content != content:
                # Backup original
                backup_file = models_file.with_suffix('.py.backup')
                backup_file.write_text(content, encoding='utf-8')

                # Write fixed version
                models_file.write_text(fixed_content, encoding='utf-8')

                self.enhancements_applied.append(f"abstract_user:{models_file.name}")
                logger.info(f"[AI] Fixed AbstractUser in {models_file.name}")

        except Exception as e:
            logger.error(f"Error fixing AbstractUser in {models_file}: {e}")

    def _fix_abstract_user_with_ai(self, content: str, filename: str) -> Optional[str]:
        """Use Gemini to properly convert AbstractUser to Flask"""

        prompt = f"""You are an expert at converting Django models to Flask-SQLAlchemy.

TASK: Fix this Django model that uses AbstractUser to work with Flask-SQLAlchemy and Flask-Login.

CURRENT CODE (BROKEN):
```python
{content}
```

REQUIREMENTS:
1. Replace `AbstractUser` or `AbstractBaseUser` with `db.Model, UserMixin`
2. Add ALL standard user fields that AbstractUser provides:
   - id (primary key)
   - password (hashed password field, String(255))
   - email (unique, not null, String(254))
   - first_name (String(30))
   - last_name (String(30))
   - is_active (Boolean, default True)
   - is_staff (Boolean, default False)
   - is_superuser (Boolean, default False)
   - date_joined (DateTime, default now)
   - last_login (DateTime, nullable)

3. Remove Django-specific fields:
   - USERNAME_FIELD
   - REQUIRED_FIELDS
   - objects (custom managers like CustomUserManager)

4. Keep any custom fields that were added (like role, gender, etc.)

5. Add proper imports:
   - from flask_login import UserMixin
   - Keep the existing db import

6. Make sure ALL columns use db.Column() syntax

7. Add __tablename__ if not present

IMPORTANT: Return ONLY the fixed Python code. No explanations, no markdown code blocks, just pure Python code.
"""

        max_retries = 3
        current_prompt = prompt

        for attempt in range(max_retries):
            try:
                fixed_code = self.provider.generate_conversion(current_prompt).strip()

                # Clean markdown blocks
                fixed_code = re.sub(r'^```python\s*\n?', '', fixed_code)
                fixed_code = re.sub(r'\n?```\s*$', '', fixed_code)
                fixed_code = fixed_code.strip()

                # Phase 4: Smart Validation Layer
                import ast
                ast.parse(fixed_code) # Validates syntax correctness
                
                return fixed_code

            except SyntaxError as syntax_err:
                logger.warning(f"[AI Validation] Syntax error on attempt {attempt+1}: {syntax_err}")
                current_prompt += f"\n\nERROR: The generated code had a Python SyntaxError: {syntax_err}\nPlease fix the syntax and return valid Flask Python code."
            except Exception as e:
                logger.error(f"AI provider error on attempt {attempt+1}: {e}")
                
        logger.error("AI provider failed to generate valid syntax after maximum retries")
        return None

    def _process_single_route(self, routes_file: Path):
        try:
            content = routes_file.read_text(encoding='utf-8')

            # Check for placeholder route implementations emitted by the deterministic converter.
            if not self._has_placeholder_route_logic(content):
                return

            logger.info(f"Found placeholder routes in {routes_file}")

            # Also find corresponding views.py if it exists
            views_file = routes_file.parent / 'views.py'
            views_content = None
            if views_file.exists():
                views_content = views_file.read_text(encoding='utf-8')

            # Use Gemini to implement routes
            implemented_content = self._implement_routes_with_ai(
                content,
                views_content,
                routes_file.name
            )

            if implemented_content and implemented_content != content:
                # Backup original
                backup_file = routes_file.with_suffix('.py.backup')
                backup_file.write_text(content, encoding='utf-8')

                # Write implemented version
                routes_file.write_text(implemented_content, encoding='utf-8')

                self.enhancements_applied.append(f"routes:{routes_file.name}")
                logger.info(f"[AI] Implemented routes in {routes_file.name}")

        except Exception as e:
            logger.error(f"Error implementing routes in {routes_file}: {e}")

    def _has_placeholder_route_logic(self, content: str) -> bool:
        markers = [
            '\n    pass',
            "return 'Hello from ",
            "Operation completed",
            "Search backend integration requires project-specific implementation.",
            "OTP delivery integration requires project-specific mail implementation.",
            "# TODO:",
            "return jsonify({'success': True})",
        ]
        return any(marker in content for marker in markers)

    def _implement_routes_with_ai(self, routes_content: str, views_content: Optional[str], filename: str) -> Optional[str]:
        """Use Gemini to implement route logic"""

        views_context = ""
        if views_content:
            views_context = f"""
ORIGINAL DJANGO VIEWS (for reference):
```python
{views_content}
```
"""

        prompt = f"""You are an expert at converting Django views to Flask routes.

TASK: Implement these Flask routes that currently just have 'pass' statements.

CURRENT ROUTES (EMPTY):
```python
{routes_content}
```

{views_context}

REQUIREMENTS:
1. Replace all 'pass' statements with actual Flask route implementations
1a. Replace placeholder implementations like:
   - `return 'Hello from ...'`
   - generic `Operation completed` JSON payloads
   - TODO comments standing in for business logic
   - empty search/result scaffolding that never queries models

2. Use proper Flask patterns:
   - request.method for GET/POST handling
   - request.form for form data
   - request.args for query parameters
   - render_template() for rendering
   - redirect(url_for()) for redirects
   - flash() for messages
   - session for session management

3. Convert Django ORM to SQLAlchemy:
   - Model.objects.get(id=x) → Model.query.get(x)
   - Model.objects.filter() → Model.query.filter_by()
   - Model.objects.all() → Model.query.all()
   - model.save() → db.session.add(model); db.session.commit()
   - model.delete() → db.session.delete(model); db.session.commit()

4. Add proper error handling (try/except where needed)

5. Use Flask-Login decorators where appropriate (@login_required)

6. Import necessary Flask modules at the top:
   - from flask import request, render_template, redirect, url_for, flash, session
   - from flask_login import login_required, current_user, login_user, logout_user
   - from app import db (or wherever db comes from)

7. Keep the existing Blueprint structure

8. Add docstrings to functions

9. Do NOT invent placeholder model classes, mock query classes, fake fallback objects, or sample data.

10. Do NOT add broad try/except ImportError blocks that define replacement models in the route file.

11. If a dependency cannot be resolved from the provided context, keep the import as-is and preserve a clear TODO comment near the exact unresolved line instead of fabricating logic.

IMPORTANT: Return ONLY the fixed Python code. No explanations, no markdown code blocks, just pure Python code.
"""

        max_retries = 3
        current_prompt = prompt

        for attempt in range(max_retries):
            try:
                implemented_code = self.provider.generate_conversion(current_prompt).strip()

                # Remove markdown code blocks if present
                implemented_code = re.sub(r'^```python\s*\n?', '', implemented_code)
                implemented_code = re.sub(r'\n?```\s*$', '', implemented_code)
                implemented_code = implemented_code.strip()
                
                # Phase 4: Smart Validation Layer
                import ast
                ast.parse(implemented_code) # Validates syntax correctness

                return implemented_code

            except SyntaxError as syntax_err:
                logger.warning(f"[AI Validation] Syntax error on attempt {attempt+1}: {syntax_err}")
                current_prompt += f"\n\nERROR: The generated code had a Python SyntaxError: {syntax_err}\nPlease fix the syntax and return valid Flask Python code."
            except Exception as e:
                logger.error(f"AI provider error on attempt {attempt+1}: {e}")
                
        logger.error("AI provider failed to generate valid syntax after maximum retries")
        return None


__all__ = ['AIEnhancer']
