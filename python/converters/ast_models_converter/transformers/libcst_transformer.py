#!/usr/bin/env python3
"""
Phase 2: LibCST-based Code Transformation
Safely transforms Django models to SQLAlchemy while preserving formatting
"""

import libcst as cst
from typing import Dict, List, Optional, Union
from pathlib import Path


class DjangoToSQLAlchemyTransformer(cst.CSTTransformer):
    """Transform Django models to SQLAlchemy using LibCST"""

    def __init__(self, model_analysis: Dict):
        super().__init__()
        self.model_analysis = model_analysis
        self.imports_to_add = set()
        self.imports_to_remove = set()

    def leave_Import(self, original_node: cst.Import, updated_node: cst.Import) -> Union[cst.Import, cst.RemovalSentinel]:
        """Handle import statements"""
        # Remove Django imports
        names_to_keep = []
        for import_alias in updated_node.names:
            if isinstance(import_alias, cst.ImportAlias):
                name = import_alias.name
                if isinstance(name, cst.Attribute):
                    module_name = self._get_dotted_name(name)
                else:
                    module_name = name.value if isinstance(name, cst.Name) else str(name)

                # Remove Django-specific imports
                if not ('django' in module_name.lower()):
                    names_to_keep.append(import_alias)

        if not names_to_keep:
            return cst.RemovalSentinel.REMOVE

        return updated_node.with_changes(names=names_to_keep)

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> Union[cst.ImportFrom, cst.RemovalSentinel]:
        """Handle from...import statements"""
        module = updated_node.module

        if module is None:
            return updated_node

        module_name = self._get_dotted_name(module)

        # Remove Django imports
        if 'django' in module_name.lower():
            # Mark SQLAlchemy imports to add
            if 'django.db' in module_name:
                self.imports_to_add.add('sqlalchemy')
                self.imports_to_add.add('flask_sqlalchemy')
            return cst.RemovalSentinel.REMOVE

        return updated_node

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        """Transform Django model classes to SQLAlchemy"""
        class_name = updated_node.name.value

        # Find this model in analysis
        model_info = None
        for model in self.model_analysis.get('models', []):
            if model['name'] == class_name:
                model_info = model
                break

        if not model_info:
            return updated_node

        # Transform base classes
        new_bases = self._transform_bases(model_info)

        # Transform class body (fields)
        new_body = self._transform_model_body(updated_node.body, model_info)

        return updated_node.with_changes(
            bases=new_bases,
            body=new_body
        )

    def _transform_bases(self, model_info: Dict) -> List[cst.Arg]:
        """Transform Django base classes to SQLAlchemy"""
        new_bases = []

        # Check if AbstractUser model
        if model_info.get('is_abstract_user'):
            # Replace with db.Model, UserMixin
            new_bases.append(cst.Arg(value=cst.Attribute(
                value=cst.Name("db"),
                attr=cst.Name("Model")
            )))
            new_bases.append(cst.Arg(value=cst.Name("UserMixin")))
            self.imports_to_add.add('flask_login')
        else:
            # Standard model - use db.Model
            new_bases.append(cst.Arg(value=cst.Attribute(
                value=cst.Name("db"),
                attr=cst.Name("Model")
            )))

        return new_bases

    def _transform_model_body(self, body: cst.IndentedBlock, model_info: Dict) -> cst.IndentedBlock:
        """Transform model body (fields)"""
        new_statements = []

        # Add __tablename__
        table_name = model_info['meta'].get('db_table', model_info['name'].lower())
        tablename_assign = cst.SimpleStatementLine(body=[
            cst.Assign(
                targets=[cst.AssignTarget(target=cst.Name("__tablename__"))],
                value=cst.SimpleString(f"'{table_name}'")
            )
        ])
        new_statements.append(tablename_assign)

        # Transform fields
        for field in model_info['fields']:
            field_statement = self._create_sqlalchemy_field(field, model_info)
            if field_statement:
                new_statements.append(field_statement)

        # Keep methods (but skip Meta class and Django-specific attributes)
        for statement in body.body:
            if isinstance(statement, cst.SimpleStatementLine):
                for stmt_body in statement.body:
                    if isinstance(stmt_body, cst.Assign):
                        # Skip field assignments (already transformed)
                        target = stmt_body.targets[0].target
                        if isinstance(target, cst.Name):
                            if target.value in [f['name'] for f in model_info['fields']]:
                                continue
                            # Skip Django-specific attributes
                            if target.value in ['objects', 'USERNAME_FIELD', 'REQUIRED_FIELDS', 'EMAIL_FIELD']:
                                continue
                        new_statements.append(statement)
                    else:
                        new_statements.append(statement)
            elif isinstance(statement, cst.FunctionDef):
                # Keep methods
                new_statements.append(statement)
            elif isinstance(statement, cst.ClassDef):
                # Skip Meta class
                if statement.name.value != 'Meta':
                    new_statements.append(statement)

        return body.with_changes(body=new_statements)

    def _create_sqlalchemy_field(self, field: Dict, model_info: Dict) -> Optional[cst.SimpleStatementLine]:
        """Create SQLAlchemy field from Django field"""
        field_name = field['name']
        field_type = field['type']
        field_params = field['params']

        # Skip if no field type
        if not field_type:
            return None

        # Map Django field to SQLAlchemy
        sqlalchemy_type, column_params = self._map_field_type(field_type, field_params, model_info)

        if not sqlalchemy_type:
            return None

        # Build Column() call
        column_args = [cst.Arg(value=cst.Name(sqlalchemy_type))]

        # Add column parameters
        for param_name, param_value in column_params.items():
            column_args.append(cst.Arg(
                keyword=cst.Name(param_name),
                value=self._create_value_node(param_value)
            ))

        # Create assignment: field_name = db.Column(...)
        return cst.SimpleStatementLine(body=[
            cst.Assign(
                targets=[cst.AssignTarget(target=cst.Name(field_name))],
                value=cst.Call(
                    func=cst.Attribute(
                        value=cst.Name("db"),
                        attr=cst.Name("Column")
                    ),
                    args=column_args
                )
            )
        ])

    def _map_field_type(self, django_type: str, params: Dict, model_info: Dict) -> tuple:
        """Map Django field type to SQLAlchemy"""
        # Field type mappings
        field_map = {
            'CharField': ('String', {}),
            'TextField': ('Text', {}),
            'IntegerField': ('Integer', {}),
            'BigIntegerField': ('BigInteger', {}),
            'SmallIntegerField': ('SmallInteger', {}),
            'PositiveIntegerField': ('Integer', {}),
            'PositiveSmallIntegerField': ('SmallInteger', {}),
            'FloatField': ('Float', {}),
            'DecimalField': ('Numeric', {}),
            'BooleanField': ('Boolean', {}),
            'DateField': ('Date', {}),
            'DateTimeField': ('DateTime', {}),
            'TimeField': ('Time', {}),
            'EmailField': ('String', {'length': 254}),
            'URLField': ('String', {'length': 200}),
            'SlugField': ('String', {'length': 50}),
            'FileField': ('String', {'length': 100}),
            'ImageField': ('String', {'length': 100}),
            'BinaryField': ('LargeBinary', {}),
            'UUIDField': ('String', {'length': 36}),
            'JSONField': ('JSON', {}),
        }

        # Foreign key fields
        if 'ForeignKey' in django_type:
            related_model = params.get('to', params.get(0, 'Unknown'))
            return ('Integer', {'foreign_key': f'{related_model}.id'})
        elif 'OneToOneField' in django_type:
            related_model = params.get('to', params.get(0, 'Unknown'))
            return ('Integer', {'foreign_key': f'{related_model}.id', 'unique': True})
        elif 'ManyToManyField' in django_type:
            # Skip ManyToMany in Column definitions (handled separately)
            return (None, {})

        # Get base mapping
        sqlalchemy_type, base_params = field_map.get(django_type, ('String', {}))

        # Build column parameters
        column_params = base_params.copy()

        # Map Django parameters to SQLAlchemy
        if 'max_length' in params:
            if sqlalchemy_type == 'String':
                column_params['length'] = params['max_length']

        if 'null' in params:
            column_params['nullable'] = params['null']

        if 'blank' in params:
            # blank is form-level, but we can use it as hint for nullable
            if params['blank'] and 'nullable' not in column_params:
                column_params['nullable'] = True

        if 'unique' in params:
            column_params['unique'] = params['unique']

        if 'primary_key' in params:
            column_params['primary_key'] = params['primary_key']

        if 'default' in params:
            column_params['default'] = params['default']

        if 'db_index' in params:
            column_params['index'] = params['db_index']

        # AbstractUser fields - add primary_key to id
        if model_info.get('is_abstract_user') and field_map == 'id':
            column_params['primary_key'] = True

        return (sqlalchemy_type, column_params)

    def _create_value_node(self, value) -> cst.BaseExpression:
        """Create CST node for a value"""
        if isinstance(value, bool):
            return cst.Name("True" if value else "False")
        elif isinstance(value, int):
            return cst.Integer(str(value))
        elif isinstance(value, str):
            return cst.SimpleString(f"'{value}'")
        elif isinstance(value, float):
            return cst.Float(str(value))
        else:
            return cst.SimpleString(f"'{value}'")

    def _get_dotted_name(self, node: Union[cst.Name, cst.Attribute]) -> str:
        """Get dotted name from Name or Attribute node"""
        if isinstance(node, cst.Name):
            return node.value
        elif isinstance(node, cst.Attribute):
            base = self._get_dotted_name(node.value)
            return f"{base}.{node.attr.value}"
        return ""


def transform_models(code: str, model_analysis: Dict) -> str:
    """Transform Django models code to SQLAlchemy"""
    try:
        # Parse code with LibCST
        tree = cst.parse_module(code)

        # Transform
        transformer = DjangoToSQLAlchemyTransformer(model_analysis)
        new_tree = tree.visit(transformer)

        # Generate imports
        imports_code = _generate_imports(transformer.imports_to_add)

        # Combine imports + transformed code
        transformed_code = new_tree.code

        # Add imports at the top
        if imports_code:
            transformed_code = imports_code + "\n\n" + transformed_code

        return transformed_code

    except Exception as e:
        # If transformation fails, return original code
        return code


def _generate_imports(imports_to_add: set) -> str:
    """Generate SQLAlchemy import statements"""
    imports = []

    if 'sqlalchemy' in imports_to_add or 'flask_sqlalchemy' in imports_to_add:
        imports.append("from extensions import db")

    if 'flask_login' in imports_to_add:
        imports.append("from flask_login import UserMixin")

    return '\n'.join(imports)
