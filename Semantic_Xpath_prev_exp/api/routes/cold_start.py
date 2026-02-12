"""
Cold start endpoint for generating a schema and memory tree.

POST /api/cold_start
"""

from flask import Blueprint, request, jsonify

from pipeline_execution.cold_start import TaskBootstrapper

bp = Blueprint("cold_start", __name__)


@bp.route("/cold_start", methods=["POST"])
def cold_start():
    data = request.get_json() or {}

    query = (data.get("query") or data.get("request") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "Missing 'query' in request body"}), 400

    save = bool(data.get("save", True))
    activate = bool(data.get("activate", False))

    bootstrapper = TaskBootstrapper()
    result = bootstrapper.generate(query, save=save, activate=activate)

    status = 200 if result.get("success") else 500
    return jsonify(result), status
