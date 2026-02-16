"""
Registry QA Service - Handles the REGISTRY_QA intent.

Uses RegistryQueryGenerationService + SemanticXPathExecutor to generate and execute
queries on registry XML. Never changes active_task_id or active_version_id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from common.types import (
    HandlerResult,
    IntentResult,
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


def _format_retrieved_nodes(
    retrieved_nodes: List[Dict[str, Any]],
    target: str,
    active_task_id: Optional[str],
    active_version_id: Optional[str],
) -> str:
    """Format XPath execution results for display (generic, no hardcoded node types)."""
    from services.intent_handling.node_format import format_per_node_for_hint

    if not retrieved_nodes:
        if target == "tasks":
            return "You have no saved tasks yet."
        return "No versions found."

    formatted = format_per_node_for_hint(retrieved_nodes)
    prefix = "Your saved tasks:\n" if target == "tasks" else "Versions:\n"
    return prefix + formatted


class RegistryQAService(BaseIntentHandler):
    """Handler for REGISTRY_QA intent; executes semantic XPath on registry XML."""

    intent: str = "REGISTRY_QA"

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
            hint = "Registry is not available."
            return _result(hint)

        if query_service is None:
            hint = "Registry query service is not configured."
            return _result(hint)

        if executor is None:
            hint = "Semantic XPath executor is not configured."
            return _result(hint)

        schema = _get_registry_schema(registry)
        if not schema:
            hint = "Registry schema is not available."
            return _result(hint)

        registry_xml = _get_registry_xml(registry)
        if not registry_xml:
            hint = "Registry XML is not available."
            return _result(hint)

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        active_task_id = ctx.session.active_task_id
        active_version_id = ctx.session.active_version_id if active_task_id else None

        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="REGISTRY_QA",
            context_messages=ctx.context_messages,
            active_task_id=active_task_id,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            hint = (
                "I couldn't understand that registry query. "
                "Try asking to list your tasks or show versions of a specific task."
            )
            return _result(hint)
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=registry_xml,
                schema=schema,
            )
        except Exception:
            hint = "Something went wrong while querying the registry."
            return _result(hint)

        target = gen_result.registry_target or "tasks"
        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        if self._result_verifier and per_node:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="REGISTRY_QA",
                context={"active_task_id": active_task_id},
            )
            per_node = v_res.verified_nodes

        formatted = _format_retrieved_nodes(
            per_node,
            target=target,
            active_task_id=active_task_id,
            active_version_id=active_version_id,
        )
        hint = "Retrieved nodes (the answer set):\n" + formatted

        return _result(hint)


def _result(hint: str) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="REGISTRY_QA",
            generation_hint=hint,
        ),
    )
