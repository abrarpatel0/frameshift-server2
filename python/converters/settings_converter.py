import ast
from pathlib import Path
from typing import Dict, Any
from ..utils.logger import logger
from ..utils.file_handler import FileHandler


class SettingsConverter:
    """
    Parses Django's settings.py and maps relevant configurations to Flask equivalent configs.
    """

    def __init__(self, django_path: str):
        self.django_path = Path(django_path)
        self.settings_file = self._find_settings_file()
        self.extracted_settings = {
            'SECRET_KEY': None,
            'DEBUG': True,
            'ALLOWED_HOSTS': [],
            'DATABASES': {},
            'STATIC_URL': '/static/',
            'TIME_ZONE': 'UTC',
            'LANGUAGE_CODE': 'en-us',
            'CUSTOM_VARIABLES': {}
        }

    def _find_settings_file(self) -> Path:
        """Find the exact settings.py file in the Django project"""
        # Look for settings.py in immediate subdirectories of project root
        for subdir in self.django_path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('.'):
                potential_file = subdir / 'settings.py'
                if potential_file.exists():
                    return potential_file
        
        # Fallback to a deeper search via FileHandler
        files = FileHandler.find_files(str(self.django_path), 'settings.py')
        valid_files = [f for f in files if '__pycache__' not in str(f)]
        if valid_files:
            return Path(valid_files[0])
        return None

    def convert(self) -> Dict[str, Any]:
        """Parses the AST of settings.py and extracts the environment definitions."""
        if not self.settings_file or not self.settings_file.exists():
            logger.warning("No settings.py found. Using default configurations.")
            return self.extracted_settings

        logger.info(f"Parsing settings from {self.settings_file}")
        try:
            content = self.settings_file.read_text(encoding='utf-8')
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            key = target.id
                            try:
                                value = ast.literal_eval(node.value)
                                self._map_setting(key, value)
                            except ValueError:
                                # Not entirely a literal evaluate-able value (possibly an env variable)
                                # Defaulting to string representation or ignoring if complex
                                if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'config':
                                    # Very naive handling of decoupled configs like python-decouple
                                    pass
                                elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                                    if node.value.func.attr == 'environ':
                                        pass
                                
        except Exception as e:
            logger.error(f"Error parsing settings.py: {e}")

        return self.extracted_settings

    def _map_setting(self, key: str, value: Any):
        """Map Django extracted value into standard variables."""
        if key in ['SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'STATIC_URL', 'TIME_ZONE', 'LANGUAGE_CODE']:
            self.extracted_settings[key] = value
        elif key == 'DATABASES':
            self.extracted_settings['DATABASES'] = self._parse_databases(value)
        elif key.isupper():
            # Treat other uppercase assignments as custom constants
            self.extracted_settings['CUSTOM_VARIABLES'][key] = value

    def _parse_databases(self, db_dict: Dict) -> Dict:
        """Parse Django DB dict to understand engine backend type."""
        flask_dbs = {}
        if not isinstance(db_dict, dict):
            return flask_dbs
            
        for db_name, db_config in db_dict.items():
            if isinstance(db_config, dict):
                engine = db_config.get('ENGINE', '')
                db_name_str = db_config.get('NAME', 'dev.db')
                if 'sqlite3' in engine:
                    flask_dbs[db_name] = f"sqlite:///{db_name_str}"
                elif 'postgresql' in engine:
                    flask_dbs[db_name] = f"postgresql://user:pass@localhost/{db_name_str}"
                elif 'mysql' in engine:
                    flask_dbs[db_name] = f"mysql+pymysql://user:pass@localhost/{db_name_str}"
        return flask_dbs
