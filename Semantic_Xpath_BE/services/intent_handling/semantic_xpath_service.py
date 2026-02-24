"""
Semantic XPath Service - Top-level service orchestrator.

Delegates to:
- OrchestratorService for chat / plan creation
- RegistryStore, TaskStateStore, SessionStore for task/plan REST endpoints

All dependencies are injected via the constructor (created by app_factory).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from common.types import RegistryApplyRequest, ReplaceXmlNode, SessionUpdate
from common.utils import strip_none
from services.orchestrator_service import OrchestratorService
from stores.session_activity_store import SessionActivityStore
from stores.session_scope import session_scope

if TYPE_CHECKING:
    from stores.context_store import ContextStore
    from stores.session_scoped_registry_store import SessionScopedRegistryStore
    from stores.session_store import SessionStore
    from stores.task_state_store import TaskStateStore

_BASE_DIR = Path(__file__).resolve().parents[2]
_EXAMPLE_TEMPLATES = {
    "sandiego_trip_3d": {
        "label": "Show me a 3 Day Trip in San Diego",
        "task_name": "3 Day Trip in San Diego",
        "version_summary": "Seeded example: San Diego itinerary",
        "path": _BASE_DIR / "storage" / "templates" / "sandiego_trip_3d.xml",
    },
    "10day_toronto_trip": {
        "label": "Show me a 10 Day Trip in Toronto",
        "task_name": "10 Day Trip in Toronto",
        "version_summary": "Seeded example: 10-day Toronto itinerary",
        "path": _BASE_DIR / "storage" / "templates" / "10day_toronto_trip.xml",
    },
    "acl_2026_conference": {
        "label": "Show me the ACL 2026 Conference case",
        "task_name": "ACL 2026 Conference Trip",
        "version_summary": "Seeded example: ACL 2026 conference itinerary",
        "path": _BASE_DIR / "storage" / "templates" / "acl_2026_conference.xml",
    },
    "todolist": {
        "label": "PhD Student Todo List",
        "task_name": "PhD Student Todo List",
        "version_summary": "Seeded example: PhD student todo list",
        "path": _BASE_DIR / "storage" / "templates" / "todolist.xml",
    },
}


class SemanticXpathService:
    """
    Main service orchestrator for the Semantic XPath system.
    Receives a fully-wired OrchestratorService from the app factory.
    """

    def __init__(
        self,
        orchestrator: OrchestratorService,
        registry_store: Optional["SessionScopedRegistryStore"] = None,
        state_store: Optional["TaskStateStore"] = None,
        session_store: Optional["SessionStore"] = None,
        context_store: Optional["ContextStore"] = None,
        session_activity_store: Optional[SessionActivityStore] = None,
        session_idle_ttl_seconds: int = 5 * 60 * 60,
    ) -> None:
        self._orchestrator = orchestrator
        self._registry_store = registry_store
        self._state_store = state_store
        self._session_store = session_store
        self._context_store = context_store
        self._session_activity_store = session_activity_store or SessionActivityStore()
        self._session_idle_ttl_seconds = max(0, int(session_idle_ttl_seconds))

    def chat(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Process a user message through the conversation pipeline.

        Returns:
            Dict with success status, response type, message, and session updates.
        """
        self._expire_if_idle(session_id)
        with session_scope(session_id):
            resp = self._orchestrator.orchestrate(message, session_id)
        self._touch_session(session_id)

        intent_meta = self._extract_intent_meta(resp)

        result: Dict[str, Any] = {
            "success": True,
            "type": resp.routing.intent,
            "message": resp.assistant_message,
            "session_id": session_id,
            "requires_clarification": bool(resp.routing.requires_clarification),
            "clarification_question": (
                resp.routing.clarification_question
                if resp.routing.requires_clarification
                else None
            ),
            "session_updates": strip_none({
                "active_task_id": resp.session_updates.active_task_id,
                "active_version_id": resp.session_updates.active_version_id,
            }),
        }

        if intent_meta.get("xpath_query"):
            result["xpath_query"] = intent_meta["xpath_query"]
        if intent_meta.get("original_query"):
            result["original_query"] = intent_meta["original_query"]
        if intent_meta.get("affected_node_paths"):
            result["affected_node_paths"] = intent_meta["affected_node_paths"]
        if intent_meta.get("scoring_trace"):
            result["scoring_trace"] = intent_meta["scoring_trace"]
        if intent_meta.get("per_node_detail"):
            result["per_node_detail"] = intent_meta["per_node_detail"]

        return result

    @staticmethod
    def _extract_intent_meta(resp: Any) -> Dict[str, Any]:
        """Extract CRUD metadata (xpath, original query, affected paths, scoring) from TurnResponse."""
        meta: Dict[str, Any] = {}
        intent_results = getattr(resp, "intent_results", None) or []
        for ir in intent_results:
            if not isinstance(ir, dict):
                continue
            if ir.get("xpath_query") and not meta.get("xpath_query"):
                meta["xpath_query"] = ir["xpath_query"]
            if ir.get("original_query") and not meta.get("original_query"):
                meta["original_query"] = ir["original_query"]
            if ir.get("affected_node_paths") and not meta.get("affected_node_paths"):
                meta["affected_node_paths"] = ir["affected_node_paths"]
            if ir.get("scoring_trace") and not meta.get("scoring_trace"):
                meta["scoring_trace"] = ir["scoring_trace"]
            if ir.get("per_node_detail") and not meta.get("per_node_detail"):
                meta["per_node_detail"] = ir["per_node_detail"]
        return meta

    # ------------------------------------------------------------------
    # Task REST endpoints
    # ------------------------------------------------------------------

    def list_tasks(self, session_id: str) -> Dict[str, Any]:
        """Return lightweight metadata for all tasks (for tab bar rendering)."""
        self._expire_if_idle(session_id)
        with session_scope(session_id):
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
            response = {
                "active_task_id": result.active_task_id,
                "tasks": tasks,
            }
        self._touch_session(session_id)
        return response

    def get_task_plan(
        self, task_id: str, session_id: str, version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load plan XML for a task's active (or specified) version."""
        self._expire_if_idle(session_id)
        with session_scope(session_id):
            if not version_id:
                versions_result = self._registry_store.apply(
                    RegistryApplyRequest(action="LIST_VERSIONS", task_id=task_id)
                )
                version_id = versions_result.active_version_id
            if not version_id:
                raise FileNotFoundError(f"No active version for task {task_id}")
            core = self._state_store.load_core(task_id, version_id)
            response = {
                "task_id": task_id,
                "version_id": version_id,
                "plan_xml": core.xml_str,
            }
        self._touch_session(session_id)
        return response

    def activate_task(self, task_id: str, session_id: str) -> Dict[str, Any]:
        """Activate a task and sync the session (for tab click switching)."""
        self._expire_if_idle(session_id)
        with session_scope(session_id):
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
            response = {
                "active_task_id": result.active_task_id,
                "active_version_id": result.active_version_id,
            }
        self._touch_session(session_id)
        return response

    def list_example_templates(self) -> Dict[str, Any]:
        """Return all available example templates from backend registry."""
        templates = [
            {
                "template_key": template_key,
                "label": str(meta["label"]),
                "task_name": str(meta["task_name"]),
            }
            for template_key, meta in _EXAMPLE_TEMPLATES.items()
        ]
        return {"templates": templates}

    def seed_example_plan(self, session_id: str, template_key: str) -> Dict[str, Any]:
        """Create one pre-built example plan inside the current empty session."""
        self._expire_if_idle(session_id)
        template = _EXAMPLE_TEMPLATES.get(template_key)
        if template is None:
            raise ValueError(f"Unknown template_key: {template_key}")

        xml_path = Path(template["path"])
        xml_str = xml_path.read_text(encoding="utf-8")

        with session_scope(session_id):
            create_res = self._registry_store.apply(
                RegistryApplyRequest(
                    action="CREATE_TASK",
                    metadata={
                        "task_name": template["task_name"],
                        "version_summary": template["version_summary"],
                    },
                )
            )
            task_id = create_res.active_task_id or create_res.created_task_id
            version_id = create_res.active_version_id or create_res.created_version_id
            if not task_id or not version_id:
                raise RuntimeError("Failed to allocate task/version for seeded example.")

            commit_result = self._state_store.commit(
                task_id=task_id,
                base_version_id=version_id,
                ops=[ReplaceXmlNode(xpath=".", xml_fragment=xml_str)],
                commit_message=str(template["version_summary"]),
            )
            if commit_result.status != "OK":
                raise RuntimeError(
                    "Failed to seed example XML: "
                    + ", ".join(commit_result.errors or ["unknown error"])
                )

            self._session_store.update_session(
                session_id,
                SessionUpdate(
                    active_task_id=task_id,
                    active_version_id=version_id,
                ),
            )
            response = {
                "active_task_id": task_id,
                "active_version_id": version_id,
                "task_name": template["task_name"],
            }
        self._touch_session(session_id)
        return response

    def clear_session(self, session_id: str) -> None:
        """Clear all in-memory and persisted data for one session."""
        self._session_store.clear_session(session_id)
        if self._context_store is not None:
            self._context_store.clear_session(session_id)
        self._state_store.clear_session_data(session_id)
        if hasattr(self._registry_store, "clear_session"):
            self._registry_store.clear_session(session_id)
        self._session_activity_store.clear(session_id)

    def clear_expired_sessions(self) -> int:
        """Clear all sessions idle longer than configured TTL. Returns count."""
        expired_ids = self._session_activity_store.get_expired_session_ids(
            self._session_idle_ttl_seconds
        )
        for sid in expired_ids:
            self.clear_session(sid)
        return len(expired_ids)

    def get_session_metrics(self) -> Dict[str, int]:
        """Return lightweight counters for session observability."""
        tracked = self._session_activity_store.get_tracked_session_count()
        expired_candidates = len(
            self._session_activity_store.get_expired_session_ids(
                self._session_idle_ttl_seconds
            )
        )
        return {
            "tracked_sessions": tracked,
            "expired_candidate_sessions": expired_candidates,
            "session_idle_ttl_seconds": self._session_idle_ttl_seconds,
        }

    def _expire_if_idle(self, session_id: str) -> None:
        if self._session_activity_store.is_expired(
            session_id, self._session_idle_ttl_seconds
        ):
            self.clear_session(session_id)

    def _touch_session(self, session_id: str) -> None:
        self._session_activity_store.touch(session_id)
