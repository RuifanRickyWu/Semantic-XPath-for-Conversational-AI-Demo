"""
Semantic XPath Service - Top-level service orchestrator.

Delegates to:
- OrchestratorService for chat / plan creation

All dependencies are injected via the constructor (created by app_factory).
"""

from __future__ import annotations

from typing import Any, Dict

from common.utils import strip_none
from services.orchestrator_service import OrchestratorService


class SemanticXpathService:
    """
    Main service orchestrator for the Semantic XPath system.
    Receives a fully-wired OrchestratorService from the app factory.
    """

    def __init__(self, orchestrator: OrchestratorService) -> None:
        self._orchestrator = orchestrator

    def chat(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Process a user message through the conversation pipeline.

        Returns:
            Dict with success status, response type, message, and session updates.
        """
        resp = self._orchestrator.orchestrate(message, session_id)

        return {
            "success": True,
            "type": resp.routing.intent,
            "message": resp.assistant_message,
            "session_id": session_id,
            "session_updates": strip_none({
                "active_task_id": resp.session_updates.active_task_id,
                "active_version_id": resp.session_updates.active_version_id,
            }),
        }
