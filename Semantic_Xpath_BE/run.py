"""
Flask application entry point for the Semantic XPath API.

Creates and configures the Flask app with:
- CORS support for the React frontend
- Blueprint registration for API routes
- Health check endpoint
"""

import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS

# Ensure the Semantic_Xpath_BE directory is on the Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.semantic_xpath_resource import semantic_xpath_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for the React frontend
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    # Register the main API blueprint
    app.register_blueprint(semantic_xpath_bp, url_prefix="/api")

    # Health check endpoint
    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
