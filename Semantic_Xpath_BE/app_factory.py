"""
Application Factory - Central composition root.

Creates and wires ALL services, clients, and resources,
then injects them into the components that need them.

No component should create its own dependencies internally.
"""

from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from clients.openai_client import OpenAIClient
from services.router_service import RouterService
from services.chatter.chatter_service import ChatterService
from services.intent_handling.plan_builder_service import PlanBuilderService
from stores.context_store import ContextStore
from stores.session_store import SessionStore
from stores.registry_store import RegistryStore
from stores.state_store import StateStore
from services.orchestrator_service import OrchestratorService
from services.intent_handling.plan_create_service import PlanCreateService
from services.semantic_xpath_service import SemanticXpathService
from api.chat_resource import create_chat_blueprint


def create_app() -> Flask:
    """Create and configure the Flask application with all dependencies."""

    # ------------------------------------------------------------------
    # 1. Infrastructure / external clients
    # ------------------------------------------------------------------
    openai_client = OpenAIClient()

    # ------------------------------------------------------------------
    # 2. Services that wrap the OpenAI client
    # ------------------------------------------------------------------
    router_service = RouterService(client=openai_client)
    chatter_service = ChatterService(client=openai_client)
    plan_builder_service = PlanBuilderService(client=openai_client)

    # ------------------------------------------------------------------
    # 3. Stateful stores (no external dependencies)
    # ------------------------------------------------------------------
    session_store = SessionStore()
    context_store = ContextStore()
    registry_store = RegistryStore()
    state_store = StateStore()

    # ------------------------------------------------------------------
    # 4. Composite services (depend on stores + clients)
    # ------------------------------------------------------------------
    plan_create_service = PlanCreateService(
        registry=registry_store,
        state_store=state_store,
        plan_builder=plan_builder_service,
    )

    orchestrator = OrchestratorService(
        router=router_service,
        session_service=session_store,
        context_service=context_store,
        plan_create_service=plan_create_service,
        chatter=chatter_service,
    )

    # ------------------------------------------------------------------
    # 5. Top-level service
    # ------------------------------------------------------------------
    semantic_xpath_service = SemanticXpathService(orchestrator=orchestrator)

    # ------------------------------------------------------------------
    # 6. Flask app + blueprint (resource layer)
    # ------------------------------------------------------------------
    app = Flask(__name__)

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

    chat_bp = create_chat_blueprint(semantic_xpath_service)
    app.register_blueprint(chat_bp, url_prefix="/api")

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app
