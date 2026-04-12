"""WSGI entry point for Flask application."""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

# Create Flask app
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)  # Use Flask config, not environment
    app.run(host="0.0.0.0", port=port, debug=debug)
