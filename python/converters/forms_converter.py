import ast
import os
from pathlib import Path
from typing import Dict, List
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class FormsConverter:
    """
    Converts Django forms (forms.py) to Flask-WTF forms.
    """
    def __init__(self, django_path: str, output_path: str):
        self.django_path = Path(django_path)
        self.output_path = Path(output_path)
        self.results = {'converted_forms': [], 'total_forms': 0, 'issues': []}

    def convert(self) -> Dict:
        logger.info("Starting Forms conversion (Django to Flask-WTF)")
        form_files = FileHandler.find_files(str(self.django_path), 'forms.py')

        for form_file in form_files:
            if '__pycache__' in str(form_file):
                continue
            try:
                content = FileHandler.read_file(str(form_file))
                flask_code = self._convert_form_file(content, Path(form_file))
                if flask_code:
                    app_name = Path(form_file).parent.name
                    out_file = self.output_path / app_name / 'forms.py'
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(flask_code, encoding='utf-8')
                    self.results['converted_forms'].append(str(out_file))
            except Exception as e:
                self.results['issues'].append({'file': str(form_file), 'error': str(e)})

        logger.info(f"Forms conversion complete: {self.results['total_forms']} converted")
        return self.results

    def _convert_form_file(self, content: str, file_path: Path) -> str:
        tree = ast.parse(content)
        imports = ["from flask_wtf import FlaskForm", "from wtforms import StringField, PasswordField, BooleanField, IntegerField, TextAreaField, DateField, DecimalField, SubmitField", "from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional"]
        forms_code = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if any('Form' in base.id for base in node.bases if isinstance(base, ast.Name)):
                    self.results['total_forms'] += 1
                    forms_code.append(self._convert_form_class(node))
            elif isinstance(node, ast.ImportFrom) and node.module == 'models':
                imports.append(f"from .models import {', '.join([alias.name for alias in node.names])}")

        if forms_code:
            return "\n".join(imports) + "\n\n" + "\n\n".join(forms_code)
        return ""

    def _convert_form_class(self, node: ast.ClassDef) -> str:
        lines = [f"class {node.name}(FlaskForm):"]
        has_fields = False
        
        for item in node.body:
            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
                field_name = item.targets[0].id
                if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute):
                    field_type = item.value.func.attr
                    wt_field = self._map_field(field_type)
                    validators = self._map_validators(item.value.keywords)
                    lines.append(f"    {field_name} = {wt_field}('{field_name.capitalize()}', validators=[{validators}])")
                    has_fields = True
            elif isinstance(item, ast.ClassDef) and item.name == 'Meta':
                model, fields = None, None
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign) and isinstance(meta_item.targets[0], ast.Name):
                        if meta_item.targets[0].id == 'model' and isinstance(meta_item.value, ast.Name):
                            model = meta_item.value.id
                        elif meta_item.targets[0].id == 'fields' and isinstance(meta_item.value, ast.List):
                            fields = [elt.value for elt in meta_item.value.elts if hasattr(elt, 'value')]
                            has_fields = True
                
                if model and fields:
                    lines.append(f"    # Auto-mapped from ModelForm Meta: {model}")
                    for f in fields:
                        lines.append(f"    {f} = StringField('{f.capitalize()}')")

        if not has_fields:
            lines.append("    pass")
            
        lines.append("    submit = SubmitField('Submit')")
        return "\n".join(lines)

    def _map_field(self, django_field: str) -> str:
        mapping = {
            'CharField': 'StringField', 'EmailField': 'StringField',
            'IntegerField': 'IntegerField', 'BooleanField': 'BooleanField',
            'TextField': 'TextAreaField', 'DateField': 'DateField',
            'DecimalField': 'DecimalField', 'PasswordField': 'PasswordField'
        }
        return mapping.get(django_field, 'StringField')

    def _map_validators(self, keywords: List[ast.keyword]) -> str:
        validators = ["DataRequired()"]
        for kw in keywords:
            if kw.arg == 'required' and getattr(kw.value, 'value', True) is False:
                validators[0] = "Optional()"
            elif kw.arg == 'max_length' and hasattr(kw.value, 'value'):
                validators.append(f"Length(max={kw.value.value})")
        return ", ".join(validators)
