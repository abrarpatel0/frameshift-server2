import ast
import os
from pathlib import Path
from typing import Dict, List
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class AdminConverter:
    """
    Converts Django admin (admin.py) to Flask-Admin views.
    """
    def __init__(self, django_path: str, output_path: str):
        self.django_path = Path(django_path)
        self.output_path = Path(output_path)
        self.results = {'converted_admins': [], 'total_models_registered': 0, 'issues': []}

    def convert(self) -> Dict:
        logger.info("Starting Admin conversion (Django to Flask-Admin)")
        admin_files = FileHandler.find_files(str(self.django_path), 'admin.py')

        for admin_file in admin_files:
            if '__pycache__' in str(admin_file):
                continue
            try:
                content = FileHandler.read_file(str(admin_file))
                flask_code = self._convert_admin_file(content, Path(admin_file))
                if flask_code:
                    app_name = Path(admin_file).parent.name
                    out_file = self.output_path / app_name / 'admin_views.py'
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(flask_code, encoding='utf-8')
                    self.results['converted_admins'].append(str(out_file))
            except Exception as e:
                self.results['issues'].append({'file': str(admin_file), 'error': str(e)})

        logger.info(f"Admin conversion complete: {self.results['total_models_registered']} models registered")
        return self.results

    def _convert_admin_file(self, content: str, file_path: Path) -> str:
        tree = ast.parse(content)
        imports = [
            "from flask_admin.contrib.sqla import ModelView",
            "from extensions import db",
            "from .models import *"
        ]
        admin_code = []
        registered_models = []

        # Find admin.site.register and @admin.register
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == 'register' and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'site':
                    # admin.site.register(Model)
                    if node.args and isinstance(node.args[0], ast.Name):
                        model_name = node.args[0].id
                        registered_models.append(model_name)
                        admin_code.append(f"class {model_name}AdminView(ModelView):")
                        admin_code.append("    pass  # Auto-mapped from admin.site.register")

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'register':
                        # @admin.register(Model)
                        if decorator.args and isinstance(decorator.args[0], ast.Name):
                            model_name = decorator.args[0].id
                            registered_models.append(model_name)
                            admin_code.append(f"class {model_name}AdminView(ModelView):")
                            for item in node.body:
                                if isinstance(item, ast.Assign) and getattr(item.targets[0], 'id', '') == 'list_display':
                                    fields = [f.value for f in getattr(item.value, 'elts', []) if hasattr(f, 'value')]
                                    admin_code.append(f"    column_list = {fields}")
                            if len(admin_code) == 1 or admin_code[-1].startswith("class"):
                                admin_code.append("    pass")

        self.results['total_models_registered'] += len(registered_models)
        
        if admin_code:
            code = "\n".join(imports) + "\n\n" + "\n\n".join(admin_code) + "\n\n"
            code += "def init_admin_views(admin_app):\n"
            for model in set(registered_models):
                code += f"    admin_app.add_view({model}AdminView({model}, db.session))\n"
            return code
        return ""
