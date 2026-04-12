#!/usr/bin/env python3
"""
Phase 1: Astroid-based Semantic Analysis
Analyzes Django models to extract semantic information
"""

import astroid
from typing import Dict, List, Optional
from pathlib import Path


class AstroidModelAnalyzer:
    """Analyzes Django models using Astroid for semantic understanding"""

    def __init__(self):
        self.analysis_results = {}

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a Django models.py file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            # Parse with Astroid
            module = astroid.parse(code)

            result = {
                'file_path': str(file_path),
                'models': [],
                'imports': self._extract_imports(module),
                'success': True,
                'error': None
            }

            # Find all model classes
            for node in module.body:
                if isinstance(node, astroid.ClassDef):
                    if self._is_django_model(node):
                        model_info = self._analyze_model(node)
                        result['models'].append(model_info)

            return result

        except Exception as e:
            return {
                'file_path': str(file_path),
                'models': [],
                'imports': [],
                'success': False,
                'error': str(e)
            }

    def _extract_imports(self, module: astroid.Module) -> List[Dict]:
        """Extract import statements"""
        imports = []

        for node in module.body:
            if isinstance(node, astroid.Import):
                for name, alias in node.names:
                    imports.append({
                        'type': 'import',
                        'module': name,
                        'alias': alias
                    })
            elif isinstance(node, astroid.ImportFrom):
                for name, alias in node.names:
                    imports.append({
                        'type': 'from',
                        'module': node.modname,
                        'name': name,
                        'alias': alias
                    })

        return imports

    def _is_django_model(self, class_node: astroid.ClassDef) -> bool:
        """Check if class is a Django model"""
        try:
            for base in class_node.bases:
                base_name = self._get_name(base)
                if 'Model' in base_name or 'AbstractUser' in base_name or 'AbstractBaseUser' in base_name:
                    return True
        except:
            pass
        return False

    def _get_name(self, node) -> str:
        """Get name from various node types"""
        if isinstance(node, astroid.Name):
            return node.name
        elif isinstance(node, astroid.Attribute):
            return f"{self._get_name(node.expr)}.{node.attrname}"
        return ""

    def _analyze_model(self, class_node: astroid.ClassDef) -> Dict:
        """Analyze a Django model class"""
        model_info = {
            'name': class_node.name,
            'base_classes': [self._get_name(base) for base in class_node.bases],
            'fields': [],
            'meta': {},
            'methods': [],
            'is_abstract_user': self._is_abstract_user_model(class_node)
        }

        # Analyze class body
        for node in class_node.body:
            if isinstance(node, astroid.Assign):
                # Field assignment
                field_info = self._analyze_field(node)
                if field_info:
                    model_info['fields'].append(field_info)

            elif isinstance(node, astroid.ClassDef) and node.name == 'Meta':
                # Meta class
                model_info['meta'] = self._analyze_meta(node)

            elif isinstance(node, astroid.FunctionDef):
                # Method
                if not node.name.startswith('_'):  # Skip private methods
                    model_info['methods'].append({
                        'name': node.name,
                        'args': [arg.name for arg in node.args.args if arg.name != 'self'],
                        'decorators': self._get_decorators(node)
                    })

        return model_info

    def _is_abstract_user_model(self, class_node: astroid.ClassDef) -> bool:
        """Check if this is an AbstractUser or AbstractBaseUser model"""
        for base in class_node.bases:
            base_name = self._get_name(base)
            if 'AbstractUser' in base_name or 'AbstractBaseUser' in base_name:
                return True
        return False

    def _analyze_field(self, assign_node: astroid.Assign) -> Optional[Dict]:
        """Analyze a field assignment"""
        try:
            # Get field name
            if not assign_node.targets:
                return None

            target = assign_node.targets[0]
            if not isinstance(target, astroid.AssignName):
                return None

            field_name = target.name

            # Skip non-field assignments (Meta, managers, etc.)
            if field_name in ['objects', 'Meta'] or field_name.isupper():
                return None

            # Analyze field value (the field definition)
            field_type, field_params = self._analyze_field_value(assign_node.value)

            if not field_type:
                return None

            return {
                'name': field_name,
                'type': field_type,
                'params': field_params
            }

        except Exception:
            return None

    def _analyze_field_value(self, value_node) -> tuple:
        """Analyze field value to extract type and parameters"""
        field_type = None
        field_params = {}

        try:
            if isinstance(value_node, astroid.Call):
                # Field call like CharField(max_length=100)
                func = value_node.func

                if isinstance(func, astroid.Name):
                    field_type = func.name
                elif isinstance(func, astroid.Attribute):
                    field_type = func.attrname

                # Extract parameters
                for keyword in value_node.keywords:
                    param_name = keyword.arg
                    param_value = self._get_value(keyword.value)
                    field_params[param_name] = param_value

                # Extract positional args (like max_length as first arg)
                if value_node.args:
                    # Common pattern: CharField(100) instead of CharField(max_length=100)
                    if 'Char' in field_type or 'Text' in field_type:
                        if len(value_node.args) > 0:
                            field_params['max_length'] = self._get_value(value_node.args[0])

        except Exception:
            pass

        return field_type, field_params

    def _get_value(self, node):
        """Extract value from AST node"""
        if isinstance(node, astroid.Const):
            return node.value
        elif isinstance(node, astroid.Name):
            return node.name
        elif isinstance(node, astroid.Attribute):
            return f"{self._get_name(node.expr)}.{node.attrname}"
        elif isinstance(node, astroid.List):
            return [self._get_value(elt) for elt in node.elts]
        elif isinstance(node, astroid.Tuple):
            return tuple(self._get_value(elt) for elt in node.elts)
        return str(node)

    def _analyze_meta(self, meta_node: astroid.ClassDef) -> Dict:
        """Analyze Meta class"""
        meta_info = {}

        for node in meta_node.body:
            if isinstance(node, astroid.Assign):
                if node.targets:
                    target = node.targets[0]
                    if isinstance(target, astroid.AssignName):
                        key = target.name
                        value = self._get_value(node.value)
                        meta_info[key] = value

        return meta_info

    def _get_decorators(self, func_node: astroid.FunctionDef) -> List[str]:
        """Get decorator names"""
        decorators = []

        if func_node.decorators:
            for decorator in func_node.decorators.nodes:
                if isinstance(decorator, astroid.Name):
                    decorators.append(decorator.name)
                elif isinstance(decorator, astroid.Attribute):
                    decorators.append(decorator.attrname)

        return decorators


def analyze_models(file_path: Path) -> Dict:
    """Main entry point for analyzing models"""
    analyzer = AstroidModelAnalyzer()
    return analyzer.analyze_file(file_path)
