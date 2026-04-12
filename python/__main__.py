"""
Module entry point for Python conversion engine.
Allows running as: python -m python
"""
import sys
from pathlib import Path

# Ensure parent directory is in path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.main import main

if __name__ == "__main__":
    sys.exit(main())
