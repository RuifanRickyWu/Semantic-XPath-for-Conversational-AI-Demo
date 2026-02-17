"""
Semantic XPath Service - Top-level service orchestrator.

Delegates to:
- OrchestratorService for chat / plan creation
- RegistryStore, TaskStateStore, SessionStore for task/plan REST endpoints

All dependencies are injected via the constructor (created by app_factory).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from common.types import RegistryApplyRequest, SessionUpdate
from common.utils import strip_none
from services.orchestrator_service import OrchestratorService

if TYPE_CHECKING:
    from stores.registry_store import RegistryStore
    from stores.session_store import SessionStore
    from stores.task_state_store import TaskStateStore


class SemanticXpathService:
    """
    Main service orchestrator for the Semantic XPath system.
    Receives a fully-wired OrchestratorService from the app factory.
    """

    def __init__(
        self,
        orchestrator: OrchestratorService,
        registry_store: Optional["RegistryStore"] = None,
        state_store: Optional["TaskStateStore"] = None,
        session_store: Optional["SessionStore"] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._registry_store = registry_store
        self._state_store = state_store
        self._session_store = session_store

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

    # ------------------------------------------------------------------
    # Task REST endpoints
    # ------------------------------------------------------------------

    def list_tasks(self) -> Dict[str, Any]:
        """Return lightweight metadata for all tasks (for tab bar rendering)."""
        result = self._registry_store.apply(
            RegistryApplyRequest(action="LIST_TASKS")
        )
        tasks = []
        for t in result.tasks or []:
            meta = t.get("metadata", {})
            tasks.append({
                "task_id": t["task_id"],
                "task_name": meta.get("task_name"),
                "active_version_id": t["active_version_id"],
                "version_count": t.get("version_count", 0),
                "updated_at": meta.get("updated_at"),
            })
        return {
            "active_task_id": result.active_task_id,
            "tasks": tasks,
        }

    def get_task_plan(
        self, task_id: str, version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load plan XML for a task's active (or specified) version."""
        if not version_id:
            versions_result = self._registry_store.apply(
                RegistryApplyRequest(action="LIST_VERSIONS", task_id=task_id)
            )
            version_id = versions_result.active_version_id
        if not version_id:
            raise FileNotFoundError(f"No active version for task {task_id}")
        core = self._state_store.load_core(task_id, version_id)
        return {
            "task_id": task_id,
            "version_id": version_id,
            "plan_xml": core.xml_str,
        }

    def activate_task(self, task_id: str, session_id: str) -> Dict[str, Any]:
        """Activate a task and sync the session (for tab click switching)."""
        result = self._registry_store.apply(
            RegistryApplyRequest(action="ACTIVATE_TASK", task_id=task_id)
        )
        self._session_store.update_session(
            session_id,
            SessionUpdate(
                active_task_id=result.active_task_id,
                active_version_id=result.active_version_id,
            ),
        )
        return {
            "active_task_id": result.active_task_id,
            "active_version_id": result.active_version_id,
        }
