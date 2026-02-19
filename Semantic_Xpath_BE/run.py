"""
Flask application entry point.

Delegates to app_factory.create_app() which handles all
component creation, wiring, and Flask configuration.
"""

import sys
from pathlib import Path

# Ensure the Semantic_Xpath_BE directory is on the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
