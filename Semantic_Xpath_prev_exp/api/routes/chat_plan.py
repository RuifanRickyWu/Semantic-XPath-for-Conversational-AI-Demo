"""
Chat/Plan endpoint (no CRUD).

POST /api/chat_plan
"""

from flask import Blueprint, request, jsonify

from pipeline_execution.cold_start.chat_plan_router import ChatPlanRouter
from pipeline_execution.cold_start import TaskBootstrapper

bp = Blueprint("chat_plan", __name__)


@bp.route("/chat_plan", methods=["POST"])
def chat_plan():
    data = request.get_json() or {}
    query = (data.get("query") or data.get("request") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "Missing 'query' in request body"}), 400

    router = ChatPlanRouter()
    result = router.route(query)
    return jsonify(result)


@bp.route("/chat_plan/reset", methods=["POST"])
def chat_plan_reset():
    bootstrapper = TaskBootstrapper()
    result = bootstrapper.reset_all()
    return jsonify(result)
