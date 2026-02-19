"""
Chat Resource - Flask Blueprint factory for API routes.

Routes:
  GET  /api/health                    - Health check endpoint
  POST /api/chat                      - Process a user message
  GET  /api/tasks                     - List all tasks (tab bar)
  GET  /api/tasks/<task_id>/plan      - Get plan XML for a task
  PUT  /api/tasks/<task_id>/activate  - Activate a task (tab click)

The blueprint is created via create_chat_blueprint() which
receives the service instance from the app factory (no internal creation).
"""

from flask import Blueprint, request, jsonify, current_app

from services.intent_handling.semantic_xpath_service import SemanticXpathService


def create_chat_blueprint(service: SemanticXpathService) -> Blueprint:
    """Create and return the chat blueprint with an injected service."""
    bp = Blueprint("chat", __name__)

    @bp.route("/health", methods=["GET"])
    def health():
        """GET /api/health — lightweight backend liveness probe."""
        return jsonify({"success": True, "status": "ok"}), 200

    @bp.route("/debug/openai", methods=["GET"])
    def debug_openai():
        """GET /api/debug/openai — diagnose OpenAI connectivity."""
        import os, traceback
        info = {
            "has_openai_key_env": bool(os.getenv("OPENAI_API_KEY")),
            "key_prefix": (os.getenv("OPENAI_API_KEY") or "")[:8] + "...",
        }
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            models = client.models.list()
            info["openai_reachable"] = True
            info["model_count"] = len(models.data)
        except Exception as e:
            info["openai_reachable"] = False
            info["error_type"] = type(e).__name__
            info["error"] = str(e)
            info["traceback"] = traceback.format_exc()
        return jsonify(info), 200

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
            import traceback
            return jsonify({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            }), 500

        return jsonify(result), 200

    # ------------------------------------------------------------------
    # Task REST endpoints
    # ------------------------------------------------------------------

    @bp.route("/tasks", methods=["GET"])
    def list_tasks():
        """GET /api/tasks — lightweight task list for tab bar."""
        session_id = (request.args.get("session_id") or "default").strip()
        try:
            result = service.list_tasks(session_id=session_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify(result), 200

    @bp.route("/tasks/<task_id>/plan", methods=["GET"])
    def get_task_plan(task_id: str):
        """GET /api/tasks/<task_id>/plan — plan XML for a task version."""
        version_id = request.args.get("version")
        session_id = (request.args.get("session_id") or "default").strip()
        try:
            result = service.get_task_plan(task_id, session_id=session_id, version_id=version_id)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify(result), 200

    @bp.route("/tasks/<task_id>/activate", methods=["PUT"])
    def activate_task(task_id: str):
        """PUT /api/tasks/<task_id>/activate — switch active task (tab click)."""
        data = request.get_json() or {}
        session_id = (data.get("session_id") or "default").strip()
        try:
            result = service.activate_task(task_id, session_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify(result), 200

    @bp.route("/session/seed", methods=["POST"])
    def seed_session():
        """POST /api/session/seed — add one prebuilt example plan to this session."""
        data = request.get_json() or {}
        session_id = (data.get("session_id") or "default").strip()
        template_key = (data.get("template_key") or "").strip()
        if not template_key:
            return jsonify({"error": "Missing 'template_key' in request body"}), 400
        try:
            result = service.seed_example_plan(session_id=session_id, template_key=template_key)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"success": True, **result}), 200

    @bp.route("/session/<session_id>", methods=["DELETE"])
    def clear_session(session_id: str):
        """DELETE /api/session/<session_id> — clear one user session workspace."""
        session_id = (session_id or "default").strip()
        try:
            service.clear_session(session_id=session_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"success": True}), 200

    @bp.route("/admin/session-metrics", methods=["GET"])
    def session_metrics():
        """GET /api/admin/session-metrics — session observability metrics."""
        try:
            metrics = service.get_session_metrics()
            sweeper_interval = int(
                current_app.config.get("SESSION_SWEEPER_INTERVAL_SECONDS", 30 * 60)
            )
            return jsonify(
                {
                    "success": True,
                    **metrics,
                    "sweeper_interval_seconds": sweeper_interval,
                }
            ), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return bp
