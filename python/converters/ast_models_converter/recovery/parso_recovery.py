#!/usr/bin/env python3
"""
Phase 3: Parso-based Error Recovery
Handles broken/incomplete Django code with graceful fallbacks
"""

import re
import parso
from typing import Dict, List, Optional
from pathlib import Path


class ParsoRecoveryAnalyzer:
    """Use Parso to analyze broken Django code and provide fallback conversions"""

    def __init__(self):
        self.recovery_applied = False
        self.errors_found = []

    def analyze_with_recovery(self, file_path: Path) -> Dict:
        """Analyze file with error recovery"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            # Parse with Parso (tolerates syntax errors)
            module = parso.parse(code)
            module_errors = getattr(module, 'errors', []) or []

            result = {
                'file_path': str(file_path),
                'models': [],
                'has_errors': len(module_errors) > 0,
                'errors': [self._format_error(err) for err in module_errors],
                'recovery_applied': False,
                'success': True
            }

            # Extract models even from broken code
            models = self._extract_models_from_tree(module)
            if not models:
                models = self._extract_models_with_regex(code)
            result['models'] = models

            if models:
                result['recovery_applied'] = True

            return result

        except Exception as e:
            return {
                'file_path': str(file_path),
                'models': [],
                'has_errors': True,
                'errors': [str(e)],
                'recovery_applied': False,
                'success': False
            }

    def _extract_models_with_regex(self, code: str) -> List[Dict]:
        """Fallback extractor for malformed legacy Django model files."""
        models = []
        normalized_code = code.replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
        class_pattern = re.compile(
            r'^class\s+(?P<name>\w+)\((?P<bases>[^)]*)\):(?P<body>.*?)(?=^class\s+\w+\(|\Z)',
            re.MULTILINE | re.DOTALL
        )

        for match in class_pattern.finditer(normalized_code):
            class_name = match.group('name')
            base_text = match.group('bases').strip()
            base_classes = [base.strip() for base in base_text.split(',') if base.strip()]
            model_info = {
                'name': class_name,
                'base_classes': base_classes,
                'fields': self._extract_fields_with_regex(match.group('body')),
                'source': match.group(0),
                'meta': self._extract_meta_with_regex(match.group('body')),
                'is_abstract_user': any(
                    'AbstractUser' in base or 'AbstractBaseUser' in base
                    for base in base_classes
                )
            }

            if self._is_model_class(model_info):
                models.append(model_info)

        return models

    def _extract_fields_with_regex(self, class_body: str) -> List[Dict]:
        fields = []
        for raw_line in class_body.splitlines():
            line = raw_line.split('#', 1)[0].rstrip()
            if not line or '=' not in line:
                continue

            left, right = line.split('=', 1)
            field_name = left.strip()
            expression = right.strip()

            if field_name in ['objects', 'Meta'] or field_name.isupper():
                continue

            field_match = re.match(r'(?:(?:models|phonenumber_field\.modelfields)\.)?(?P<type>\w+)\((?P<args>.*)\)$', expression)
            if not field_match:
                continue

            field_type = field_match.group('type')
            args = field_match.group('args')
            params = self._extract_regex_params(args)
            positional_args = self._extract_positional_args(args)

            if field_type in ('ForeignKey', 'OneToOneField'):
                if 'to' not in params and positional_args:
                    params['to'] = positional_args[0].strip('"\'')
                if len(positional_args) > 1 and 'on_delete' not in params:
                    params['on_delete'] = positional_args[1]

            fields.append({
                'name': field_name,
                'type': field_type,
                'params': params
            })

        return fields

    def _extract_meta_with_regex(self, class_body: str) -> Dict:
        meta = {}
        meta_match = re.search(r'class\s+Meta:\s*(?P<body>.*?)(?=^\s*def\s|^\s*class\s|\Z)', class_body, re.MULTILINE | re.DOTALL)
        if not meta_match:
            return meta

        body = meta_match.group('body')
        db_table = re.search(r"db_table\s*=\s*['\"]([^'\"]+)['\"]", body)
        if db_table:
            meta['db_table'] = db_table.group(1)

        if re.search(r'managed\s*=\s*False', body):
            meta['managed'] = False

        unique_together = re.search(r'unique_together\s*=\s*(.+)', body)
        if unique_together:
            meta['unique_together'] = unique_together.group(1).strip()

        return meta

    def _extract_regex_params(self, args: str) -> Dict:
        params = {}
        for key, raw_value in re.findall(r'(\w+)\s*=\s*((?:[^,(]|\([^)]*\))+)', args):
            params[key] = self._normalize_regex_value(raw_value.strip())
        return params

    def _extract_positional_args(self, args: str) -> List[str]:
        cleaned_args = re.sub(r'\b\w+\s*=\s*((?:[^,(]|\([^)]*\))+)', '', args)
        parts = []
        current = []
        depth = 0

        for char in cleaned_args:
            if char == ',' and depth == 0:
                value = ''.join(current).strip()
                if value:
                    parts.append(value)
                current = []
                continue

            if char == '(':
                depth += 1
            elif char == ')' and depth > 0:
                depth -= 1

            current.append(char)

        tail = ''.join(current).strip()
        if tail:
            parts.append(tail)

        return [part for part in parts if part]

    def _normalize_regex_value(self, value: str):
        if value in ('True', 'False'):
            return value == 'True'
        if re.fullmatch(r'\d+', value):
            return int(value)
        if re.fullmatch(r'\d+\.\d+', value):
            return float(value)
        return value.strip('"\'')

    def _format_error(self, error) -> Dict:
        """Format Parso error object"""
        return {
            'message': error.message,
            'line': error.start_pos[0],
            'column': error.start_pos[1],
            'type': error.type
        }

    def _extract_models_from_tree(self, tree) -> List[Dict]:
        """Extract model information from Parso tree"""
        models = []

        # Traverse tree to find class definitions
        for node in self._walk_tree(tree):
            if node.type == 'classdef':
                model_info = self._analyze_class_node(node)
                if model_info and self._is_model_class(model_info):
                    models.append(model_info)

        return models

    def _walk_tree(self, node):
        """Walk Parso tree recursively"""
        yield node
        try:
            for child in node.children:
                yield from self._walk_tree(child)
        except AttributeError:
            pass

    def _analyze_class_node(self, class_node) -> Optional[Dict]:
        """Analyze a class definition node"""
        try:
            # Get class name
            class_name = None
            for child in class_node.children:
                if child.type == 'name':
                    class_name = child.value
                    break

            if not class_name:
                return None

            # Get base classes
            base_classes = self._extract_base_classes(class_node)

            # Get class body
            fields = self._extract_fields(class_node)

            return {
                'name': class_name,
                'base_classes': base_classes,
                'fields': fields,
                'source': class_node.get_code()
            }

        except Exception:
            return None

    def _is_model_class(self, class_info: Dict) -> bool:
        """Check if class is likely a Django model"""
        base_classes = class_info.get('base_classes', [])
        for base in base_classes:
            if 'Model' in base or 'AbstractUser' in base or 'AbstractBaseUser' in base:
                return True
        return False

    def _extract_base_classes(self, class_node) -> List[str]:
        """Extract base class names"""
        base_classes = []

        try:
            for child in class_node.children:
                if child.type == 'arglist':
                    # Parse argument list for base classes
                    for arg_child in child.children:
                        if arg_child.type == 'name':
                            base_classes.append(arg_child.value)
                        elif arg_child.type == 'trailer':
                            # Dotted name like models.Model
                            base_name = self._get_dotted_name(arg_child)
                            if base_name:
                                base_classes.append(base_name)
        except Exception:
            pass

        return base_classes

    def _get_dotted_name(self, node) -> str:
        """Get dotted name from node"""
        parts = []
        try:
            for child in self._walk_tree(node):
                if child.type == 'name':
                    parts.append(child.value)
        except Exception:
            pass
        return '.'.join(parts) if parts else ''

    def _extract_fields(self, class_node) -> List[Dict]:
        """Extract field definitions from class body"""
        fields = []

        try:
            # Find class body (suite)
            for child in class_node.children:
                if child.type == 'suite':
                    # Look for assignments in suite
                    for stmt in child.children:
                        field_info = self._analyze_statement(stmt)
                        if field_info:
                            fields.append(field_info)
        except Exception:
            pass

        return fields

    def _analyze_statement(self, stmt_node) -> Optional[Dict]:
        """Analyze a statement to extract field information"""
        try:
            # Look for assignment: field_name = FieldType(...)
            if stmt_node.type == 'simple_stmt':
                for child in stmt_node.children:
                    if child.type == 'expr_stmt':
                        field_info = self._parse_field_assignment(child)
                        if field_info:
                            return field_info
        except Exception:
            pass
        return None

    def _parse_field_assignment(self, expr_node) -> Optional[Dict]:
        """Parse field assignment expression"""
        try:
            # Get left side (field name)
            field_name = None
            field_type = None
            field_params = {}

            children_list = list(expr_node.children)

            # First child should be field name
            if children_list and children_list[0].type == 'name':
                field_name = children_list[0].value

            # Look for function call (field type)
            for child in children_list:
                if child.type == 'trailer' and self._is_function_call(child):
                    # Previous sibling should be field type
                    idx = children_list.index(child)
                    if idx > 0:
                        prev = children_list[idx - 1]
                        if prev.type == 'name':
                            field_type = prev.value

                    # Extract parameters from call
                    field_params = self._extract_call_params(child)

            if field_name and field_type:
                # Skip non-field attributes
                if field_name in ['objects', 'Meta'] or field_name.isupper():
                    return None

                return {
                    'name': field_name,
                    'type': field_type,
                    'params': field_params
                }

        except Exception:
            pass

        return None

    def _is_function_call(self, node) -> bool:
        """Check if node represents a function call"""
        try:
            for child in node.children:
                if child.type == 'arglist':
                    return True
        except Exception:
            pass
        return False

    def _extract_call_params(self, call_node) -> Dict:
        """Extract parameters from function call"""
        params = {}

        try:
            for child in call_node.children:
                if child.type == 'arglist':
                    # Parse arguments
                    for arg_child in child.children:
                        if arg_child.type == 'argument':
                            # Keyword argument: key=value
                            param_name, param_value = self._parse_argument(arg_child)
                            if param_name:
                                params[param_name] = param_value
        except Exception:
            pass

        return params

    def _parse_argument(self, arg_node) -> tuple:
        """Parse keyword argument"""
        try:
            children = list(arg_node.children)
            if len(children) >= 3:
                # Format: name = value
                param_name = children[0].value if children[0].type == 'name' else None
                param_value = self._get_node_value(children[2])
                return param_name, param_value
        except Exception:
            pass
        return None, None

    def _get_node_value(self, node):
        """Extract value from node"""
        try:
            if node.type == 'number':
                value = node.value
                return int(value) if '.' not in value else float(value)
            elif node.type == 'string':
                # Remove quotes
                return node.value.strip('"\'')
            elif node.type == 'name':
                value = node.value
                if value == 'True':
                    return True
                elif value == 'False':
                    return False
                return value
        except Exception:
            pass
        return node.get_code() if hasattr(node, 'get_code') else str(node)


def recover_models(file_path: Path) -> Dict:
    """Attempt to recover model information from broken code"""
    analyzer = ParsoRecoveryAnalyzer()
    return analyzer.analyze_with_recovery(file_path)


def create_fallback_model(
    model_name: str,
    table_name: str = None,
    fields: List[Dict] = None,
    is_user_model: bool = False
) -> str:
    """Create a basic fallback SQLAlchemy model"""
    if not table_name:
        table_name = model_name.lower()
    fields = fields or []

    bases = "db.Model, UserMixin" if is_user_model else "db.Model"
    lines = [
        f"class {model_name}({bases}):",
        f"    __tablename__ = '{table_name}'",
        ""
    ]

    rendered_fields = [_render_field(field) for field in fields]
    rendered_fields = [field for field in rendered_fields if field]

    if rendered_fields:
        lines.extend([f"    {field}" for field in rendered_fields])
    else:
        lines.append("    id = db.Column(db.Integer, primary_key=True)")
        lines.append("    # TODO: Add fields manually - automatic conversion failed")

    lines.extend([
        "",
        "    def __repr__(self):",
        f"        return f'<{model_name} {{getattr(self, \"id\", None)}}>'"
    ])

    return "\n".join(lines)


def _render_field(field: Dict) -> Optional[str]:
    field_name = field.get('name')
    field_type = field.get('type')
    params = field.get('params', {}) or {}

    if not field_name or not field_type:
        return None

    if field_type == 'ManyToManyField':
        return f"# TODO: map ManyToManyField for {field_name}"

    if field_type == 'ForeignKey':
        related_model = params.get('to', 'related_model').split('.')[-1]
        fk_target = 'id'
        if related_model == 'Country':
            fk_target = 'code'
        column_type = 'db.String(3)' if fk_target == 'code' else 'db.Integer'
        options = [f"db.ForeignKey('{related_model.lower()}.{fk_target}')"]
        if params.get('primary_key'):
            options.append('primary_key=True')
        if params.get('null') is False:
            options.append('nullable=False')
        return f"{field_name} = db.Column({column_type}, {', '.join(options)})"

    type_map = {
        'AutoField': 'db.Integer',
        'IntegerField': 'db.Integer',
        'SmallIntegerField': 'db.SmallInteger',
        'FloatField': 'db.Float',
        'CharField': lambda p: f"db.String({p.get('max_length', 255)})",
        'PhoneNumberField': lambda p: f"db.String({p.get('max_length', 32)})",
        'EmailField': lambda p: f"db.String({p.get('max_length', 254)})",
        'DateTimeField': 'db.DateTime',
        'BooleanField': 'db.Boolean',
        'TextField': 'db.Text',
    }

    mapped = type_map.get(field_type, 'db.String(255)')
    column_type = mapped(params) if callable(mapped) else mapped
    options = []

    if params.get('primary_key'):
        options.append('primary_key=True')
    if params.get('unique'):
        options.append('unique=True')
    if params.get('null') is False:
        options.append('nullable=False')
    if params.get('null') is True:
        options.append('nullable=True')

    if 'default' in params:
        default_value = params['default']
        if isinstance(default_value, str) and not default_value.startswith(("'", '"')):
            default_value = repr(default_value)
        options.append(f"default={default_value}")

    joined = ', '.join([column_type] + options) if options else column_type
    return f"{field_name} = db.Column({joined})"
