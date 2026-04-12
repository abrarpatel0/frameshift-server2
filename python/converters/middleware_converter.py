import ast
from pathlib import Path
from typing import Dict
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class MiddlewareConverter:
    """
    Converts Django middleware strings/classes to Flask before_request/after_request patterns.
    """
    def __init__(self, django_path: str, output_path: str):
        self.django_path = Path(django_path)
        self.output_path = Path(output_path)
        self.results = {'converted_middleware': [], 'custom_middlewares_found': 0, 'issues': []}

    def convert(self) -> Dict:
        logger.info("Starting Middleware conversion...")
        
        # Look for custom middleware classes in the project
        middleware_files = FileHandler.find_files(str(self.django_path), 'middleware.py')
        
        out_file = self.output_path / 'middleware.py'
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        flask_code = [
            "from flask import request, session, redirect, url_for, g",
            "import time",
            ""
        ]

        for mw_file in middleware_files:
            if '__pycache__' in str(mw_file): continue
            
            try:
                content = FileHandler.read_file(str(mw_file))
                tree = ast.parse(content)
                
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        flask_code.extend(self._convert_middleware_class(node))
                        self.results['custom_middlewares_found'] += 1

            except Exception as e:
                self.results['issues'].append({'file': str(mw_file), 'error': str(e)})

        if self.results['custom_middlewares_found'] > 0:
            flask_code.append("\n# Call this in app factory to register middlewares")
            flask_code.append("def init_middleware(app):")
            flask_code.append("    # Note: These are automatically generated translations.")
            flask_code.append("    pass\n")

            out_file.write_text("\n".join(flask_code), encoding='utf-8')
            self.results['converted_middleware'].append(str(out_file))
            
        logger.info(f"Middleware conversion complete: {self.results['custom_middlewares_found']} custom items")
        return self.results

    def _convert_middleware_class(self, node: ast.ClassDef) -> list:
        # Skeleton for before/after request
        generated = []
        class_name = node.name
        
        generated.append(f"# Translated from Django middleware: {class_name}")
        generated.append(f"def {class_name.lower()}_before_request():")
        generated.append(f"    # TODO: Implement pre-request logic from {class_name}.__call__")
        generated.append(f"    pass\n")
        
        generated.append(f"def {class_name.lower()}_after_request(response):")
        generated.append(f"    # TODO: Implement post-request logic from {class_name}.__call__")
        generated.append(f"    return response\n")
        
        return generated
