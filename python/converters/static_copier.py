"""
Static Files Copier
Copies Django static files to Flask static directory
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List
from ..utils.logger import logger


class StaticCopier:
    """Copy static files from Django to Flask project"""

    def __init__(self, django_path: str, output_path: str):
        self.django_path = Path(django_path)
        self.output_path = Path(output_path)
        self.excluded_dirs = {
            '.git', '__pycache__', 'node_modules', '.next',
            'venv', '.venv', 'env', '.idea', '.vscode'
        }
        self.results = {
            'copied_files': [],
            'total_static_files': 0,
            'total_size_bytes': 0,
            'issues': [],
            'warnings': []
        }

    def copy(self) -> Dict:
        """Copy all static files to Flask static/ directory"""
        logger.info("Starting static files copy")

        # Find all static directories in Django project
        static_dirs = self._find_static_directories()

        if not static_dirs:
            logger.warning("No static directories found")
            return self.results

        # Create Flask static directory
        flask_static_dir = self.output_path / 'static'
        flask_static_dir.mkdir(parents=True, exist_ok=True)

        # Copy all static files
        for static_dir in static_dirs:
            self._copy_directory(static_dir, flask_static_dir)

        logger.info(f"Static files copy complete. Copied {self.results['total_static_files']} files ({self.results['total_size_bytes']} bytes)")
        return self.results

    def _find_static_directories(self) -> List[Path]:
        """Find all 'static' directories in Django project"""
        static_dirs = []

        for root, dirs, _ in os.walk(self.django_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs and not d.startswith('.')]
            if 'static' in dirs:
                static_dir = Path(root) / 'static'
                static_dirs.append(static_dir)
                logger.info(f"Found static directory: {static_dir}")

        return static_dirs

    def _copy_directory(self, source_dir: Path, dest_dir: Path):
        """Recursively copy a static directory"""
        try:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs and not d.startswith('.')]

                for filename in files:
                    item = Path(root) / filename

                    # Calculate relative path from source static dir
                    relative_path = item.relative_to(source_dir)

                    # Determine destination
                    dest_file = dest_dir / relative_path

                    # Create parent directories
                    dest_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(item, dest_file)

                    # Track results
                    file_size = item.stat().st_size
                    self.results['copied_files'].append({
                        'source': str(item),
                        'destination': str(dest_file),
                        'size': file_size
                    })
                    self.results['total_static_files'] += 1
                    self.results['total_size_bytes'] += file_size

                    logger.debug(f"Copied: {relative_path}")

        except Exception as e:
            logger.error(f"Error copying {source_dir}: {e}")
            self.results['issues'].append({
                'directory': str(source_dir),
                'error': str(e)
            })


__all__ = ['StaticCopier']
