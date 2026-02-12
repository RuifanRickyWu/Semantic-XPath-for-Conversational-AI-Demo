"""
Semantic XPath Resource - Flask Blueprint defining API routes.

Routes:
  POST /api/cold_start  - Generate schemas and memory from a user query.
  GET  /api/health       - Health check endpoint.
"""

from flask import Blueprint, request, jsonify

from core.semantic_xpath_service import SemanticXpathService

semantic_xpath_bp = Blueprint("semantic_xpath", __name__)

# Instantiate the service (singleton for the blueprint)
_service = SemanticXpathService()


@semantic_xpath_bp.route("/cold_start", methods=["POST"])
def cold_start():
    """
    POST /api/cold_start

    Request body (JSON):
        {
            "query": "5 days travel plan in Toronto",
            "save": true,       // optional, default true
            "activate": false   // optional, default false
        }

    Response (200):
        {
            "success": true,
            "plan_output": { ... },
            "user_facing": "...",
            "task": { ... },
            "task_schema": { ... },
            "domain_schema": { ... },
            "memory_xml": "<?xml ...>",
            "display": { ... }
        }

    Response (400):
        { "success": false, "error": "Missing 'query' in request body" }

    Response (500):
        { "success": false, "error": "..." }
    """
    data = request.get_json() or {}

    query = (data.get("query") or data.get("request") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "Missing 'query' in request body"}), 400

    save = bool(data.get("save", True))
    activate = bool(data.get("activate", False))

    try:
        result = _service.cold_start(query=query, save=save, activate=activate)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    status = 200 if result.get("success") else 500
    return jsonify(result), status
