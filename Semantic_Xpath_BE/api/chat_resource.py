"""
Chat Resource - Flask Blueprint factory for API routes.

Routes:
  POST /api/chat       - Process a user message (chat, plan creation, etc.)

The blueprint is created via create_chat_blueprint() which
receives the service instance from the app factory (no internal creation).
"""

from flask import Blueprint, request, jsonify

from services.semantic_xpath_service import SemanticXpathService


def create_chat_blueprint(service: SemanticXpathService) -> Blueprint:
    """Create and return the chat blueprint with an injected service."""
    bp = Blueprint("chat", __name__)

    @bp.route("/chat", methods=["POST"])
    def chat():
        """
        POST /api/chat

        Request body (JSON):
            {
                "message": "Create a 3-day Toronto itinerary",
                "session_id": "user_abc_123"   // optional, defaults to "default"
            }

        Response (200):
            {
                "success": true,
                "type": "CHAT" | "PLAN_CREATE",
                "message": "assistant response text",
                "session_id": "user_abc_123",
                "session_updates": {
                    "active_task_id": "t1",
                    "active_version_id": "v1"
                }
            }

        Response (400):
            { "success": false, "error": "Missing 'message' in request body" }

        Response (500):
            { "success": false, "error": "..." }
        """
        data = request.get_json() or {}

        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"success": False, "error": "Missing 'message' in request body"}), 400

        session_id = (data.get("session_id") or "default").strip()

        try:
            result = service.chat(message=message, session_id=session_id)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        return jsonify(result), 200

    return bp
