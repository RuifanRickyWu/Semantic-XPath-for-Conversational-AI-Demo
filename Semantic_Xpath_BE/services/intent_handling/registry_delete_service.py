"""
Registry Delete Service - Handles the REGISTRY_DELETE intent.

Deletes tasks or versions from the registry using:
  retriever -> extract task_id/version_id -> registry.apply(DELETE_TASK | DELETE_VERSION)

If the active task or version is deleted, switches to the latest remaining one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from common.types import (
    HandlerResult,
    IntentResult,
    RegistryApplyRequest,
    RegistryApplyResult,
    SessionUpdate,
)
from interfaces import TaskRegistry
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler
from services.query_generation.models import QueryGenerationRequest, QueryGenerationResult


def _get_registry_schema(registry: Any) -> Optional[dict]:
    """Get registry schema if the registry supports it."""
    getter = getattr(registry, "get_registry_schema", None)
    return getter() if callable(getter) else None


def _get_registry_xml(registry: Any) -> Optional[str]:
    """Get registry XML if the registry supports it."""
    getter = getattr(registry, "get_registry_xml", None)
    return getter() if callable(getter) else None


def _extract_ids_from_result(
    per_node: List[Dict[str, Any]],
    target: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Brute-force extract task_id and version_id from retrieval result.
    Returns (task_id, version_id).
    """
    if not per_node:
        return None, None
    entry = per_node[0]
    node = entry.get("node") or {}
    attrs = node.get("attributes") or {}
    tree_path = entry.get("tree_path_display") or entry.get("tree_path") or []

    if target == "tasks":
        task_id = attrs.get("task_id")
        return task_id, None

    if target == "versions":
        version_id = attrs.get("version_id")
        task_id = None
        for seg in tree_path:
            s = seg if isinstance(seg, dict) else {}
            if s.get("type") == "Task":
                task_id = (s.get("attributes") or {}).get("task_id")
                break
        return task_id, version_id

    return None, None


class RegistryDeleteService(BaseIntentHandler):
    """Handler for REGISTRY_DELETE intent; deletes tasks or versions."""

    intent: str = "REGISTRY_DELETE"

    def __init__(
        self,
        registry: Optional[TaskRegistry] = None,
        registry_query_service: Optional[Any] = None,
        executor: Optional[Any] = None,
        result_verifier: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._registry_query_service = registry_query_service
        self._executor = executor
        self._result_verifier = result_verifier

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        registry = self._registry
        query_service = self._registry_query_service
        executor = self._executor

        if registry is None:
            return _result("Registry is not available.")

        if query_service is None:
            return _result("Registry query service is not configured.")

        if executor is None:
            return _result("Semantic XPath executor is not configured.")

        schema = _get_registry_schema(registry)
        if not schema:
            return _result("Registry schema is not available.")

        registry_xml = _get_registry_xml(registry)
        if not registry_xml:
            return _result("Registry XML is not available.")

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        active_task_id = ctx.session.active_task_id

        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="REGISTRY_DELETE",
            context_messages=ctx.context_messages,
            active_task_id=active_task_id,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            return _result(
                "I couldn't understand that registry request. "
                "Try 'delete my Paris trip' or 'remove version 2'."
            )
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=registry_xml,
                schema=schema,
            )
        except Exception:
            return _result("Something went wrong while querying the registry.")

        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        if not per_node:
            return _result("No matching task or version found.")

        if self._result_verifier:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="REGISTRY_DELETE",
                context={"active_task_id": active_task_id},
            )
            per_node = v_res.verified_nodes
        if not per_node:
            return _result("No matching task or version found.")

        target = gen_result.registry_target or "tasks"
        task_id, version_id = _extract_ids_from_result(per_node, target)

        if not task_id:
            return _result("Could not determine which task to delete.")

        try:
            if target == "tasks":
                apply_res = registry.apply(
                    RegistryApplyRequest(action="DELETE_TASK", task_id=task_id)
                )
                hint = _build_task_delete_hint(task_id, apply_res)
            else:
                if not version_id:
                    return _result("Could not determine which version to delete.")
                apply_res = registry.apply(
                    RegistryApplyRequest(
                        action="DELETE_VERSION",
                        task_id=task_id,
                        version_id=version_id,
                    )
                )
                hint = _build_version_delete_hint(task_id, version_id, apply_res)
        except ValueError as e:
            return _result(str(e))

        session_updates = SessionUpdate(
            active_task_id=apply_res.active_task_id,
            active_version_id=apply_res.active_version_id,
        )

        return HandlerResult(
            session_updates=session_updates,
            generation_hint=hint,
            intent_result=IntentResult(
                intent="REGISTRY_DELETE",
                generation_hint=hint,
            ),
        )


def _build_task_delete_hint(
    deleted_task_id: str,
    apply_res: RegistryApplyResult,
) -> str:
    """Build a short hint for the chatter after task deletion."""
    t = apply_res.active_task_id
    v = apply_res.active_version_id
    if t:
        return f"Deleted task {deleted_task_id}. Switched to task {t} (version {v})."
    return f"Deleted task {deleted_task_id}. No tasks remaining."


def _build_version_delete_hint(
    task_id: str,
    deleted_version_id: str,
    apply_res: RegistryApplyResult,
) -> str:
    """Build a short hint for the chatter after version deletion."""
    v = apply_res.active_version_id
    return f"Deleted version {deleted_version_id} of task {task_id}. Switched to version {v}."


def _result(hint: str) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="REGISTRY_DELETE",
            generation_hint=hint,
        ),
    )
