import ast
from pathlib import Path
from typing import Dict
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class SignalConverter:
    """
    Converts Django signals (post_save, pre_delete, etc.) to Flask-Signals / SQLAlchemy events.
    """
    def __init__(self, django_path: str, output_path: str):
        self.django_path = Path(django_path)
        self.output_path = Path(output_path)
        self.results = {'converted_signals': [], 'total_signals': 0, 'issues': []}

    def convert(self) -> Dict:
        logger.info("Starting Signals conversion...")
        
        # Typically signals are in signals.py or models.py
        signal_files = FileHandler.find_files(str(self.django_path), 'signals.py')
        
        if not signal_files:
            return self.results

        out_file = self.output_path / 'signals.py'
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        flask_code = [
            "from blinker import Namespace",
            "from extensions import db",
            "",
            "signals = Namespace()",
            ""
        ]

        for sig_file in signal_files:
            if '__pycache__' in str(sig_file): continue
            
            try:
                content = FileHandler.read_file(str(sig_file))
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and getattr(node, 'decorator_list', None):
                        for dec in node.decorator_list:
                            # Match @receiver()
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'receiver':
                                flask_code.extend(self._convert_receiver(node, dec))
                                self.results['total_signals'] += 1

            except Exception as e:
                self.results['issues'].append({'file': str(sig_file), 'error': str(e)})

        if self.results['total_signals'] > 0:
            out_file.write_text("\n".join(flask_code), encoding='utf-8')
            self.results['converted_signals'].append(str(out_file))

        logger.info(f"Signal conversion complete: {self.results['total_signals']} signals found")
        return self.results

    def _convert_receiver(self, func_node: ast.FunctionDef, dec: ast.Call) -> list:
        generated = []
        
        # E.g. signal_name = 'user-created'
        # @user_created.connect
        # def func_node.name(...):
        func_name = func_node.name
        
        generated.append(f"# Translated from Django @receiver decorator")
        generated.append(f"{func_name}_signal = signals.signal('{func_name}')")
        generated.append(f"@{func_name}_signal.connect")
        generated.append(f"def {func_name}(sender, **kwargs):")
        generated.append(f"    # TODO: Implement original logic from '{func_name}'")
        generated.append(f"    pass\n")
        
        return generated
