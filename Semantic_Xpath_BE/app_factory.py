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
from services.routting.routting_service import RouttingService
from services.chatting.chatting_service import ChattingService
from services.intent_handling.base_chat_service import BaseChatService
from services.intent_handling.plan_edit_service import PlanEditService
from services.intent_handling.plan_builder_service import PlanBuilderService
from services.intent_handling.plan_qa_service import PlanQAService
from services.intent_handling.registry_edit_service import RegistryEditService
from services.intent_handling.registry_qa_service import RegistryQAService
from stores.context_store import ContextStore
from stores.session_store import SessionStore
from stores.registry_store import RegistryStore
from stores.task_state_store import TaskStateStore
from stores.xml_manager import XmlManager
from services.orchestrator_service import OrchestratorService
from services.intent_handling.plan_create_service import PlanCreateService
from services.intent_handling.semantic_xpath_service import SemanticXpathService
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
    routting_service = RouttingService(client=openai_client)
    chatting_service = ChattingService(client=openai_client)
    plan_builder_service = PlanBuilderService(client=openai_client)

    # ------------------------------------------------------------------
    # 3. Stateful stores (no external dependencies)
    # ------------------------------------------------------------------
    session_store = SessionStore()
    context_store = ContextStore()
    xml_manager = XmlManager()
    registry_store = RegistryStore(xml_manager=xml_manager)
    state_store = TaskStateStore(xml_manager=xml_manager)

    # ------------------------------------------------------------------
    # 4. Composite services (depend on stores + clients)
    # ------------------------------------------------------------------
    plan_create_service = PlanCreateService(
        registry=registry_store,
        plan_builder=plan_builder_service,
        state_store=state_store,
    )
    chat_service = BaseChatService()
    plan_qa_service = PlanQAService()
    plan_edit_service = PlanEditService()
    registry_qa_service = RegistryQAService()
    registry_edit_service = RegistryEditService()

    orchestrator = OrchestratorService(
        routting=routting_service,
        session_service=session_store,
        context_service=context_store,
        plan_create_service=plan_create_service,
        chatting=chatting_service,
        registry=registry_store,
        chat_service=chat_service,
        plan_qa_service=plan_qa_service,
        plan_edit_service=plan_edit_service,
        registry_qa_service=registry_qa_service,
        registry_edit_service=registry_edit_service,
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
