"""
Plan QA Service - Handles the PLAN_QA intent.

Answers questions about plan content using:
  state_store (load plan XML) -> plan_query_service (generate XPath) -> executor -> format results
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from common.types import (
    HandlerResult,
    IntentResult,
    SessionUpdate,
)
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler
from services.query_generation.models import QueryGenerationRequest, QueryGenerationResult


def _plan_schema_from_xml(xml_manager: Any, plan_xml: str) -> dict:
    """Build plan schema in nodes format from XML (mirrors registry schema)."""
    raw = xml_manager.sync_schema(plan_xml, "plan")
    nodes: Dict[str, Dict[str, Any]] = {}
    attrs = raw.get("attributes", {})
    children_map = raw.get("children", {})
    for tag in raw.get("node_types", []):
        nodes[tag] = {
            "fields": list(attrs.get(tag, [])),
            "children": list(children_map.get(tag, [])),
        }
    return {"nodes": nodes, "root": raw.get("root", "Plan")}


def _format_plan_nodes(per_node: List[Dict[str, Any]]) -> str:
    """Format plan retrieval results for display (generic, no hardcoded fields)."""
    from services.intent_handling.node_format import format_per_node_for_hint

    return format_per_node_for_hint(per_node)


class PlanQAService(BaseIntentHandler):
    """Handler for PLAN_QA intent; executes semantic XPath on plan XML."""

    intent: str = "PLAN_QA"

    def __init__(
        self,
        state_store: Optional[Any] = None,
        plan_query_service: Optional[Any] = None,
        executor: Optional[Any] = None,
        result_verifier: Optional[Any] = None,
    ) -> None:
        self._state_store = state_store
        self._plan_query_service = plan_query_service
        self._executor = executor
        self._result_verifier = result_verifier

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        state_store = self._state_store
        query_service = self._plan_query_service
        executor = self._executor

        if state_store is None:
            return _result("Plan state store is not available.")

        if query_service is None:
            return _result("Plan query service is not configured.")

        if executor is None:
            return _result("Semantic XPath executor is not configured.")

        task_id = ctx.session.active_task_id
        version_id = ctx.session.active_version_id

        if not task_id or not version_id:
            return _result(
                "No plan is currently loaded. Create a plan or open a task first."
            )

        try:
            core = state_store.load_core(task_id, version_id)
            plan_xml = core.xml_str
        except FileNotFoundError:
            return _result(
                "The plan for this task could not be found. It may not have been created yet."
            )

        xml_manager = getattr(state_store, "xml_manager", None)
        if xml_manager is None:
            return _result("XML manager is not available.")

        schema = _plan_schema_from_xml(xml_manager, plan_xml)

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="PLAN_QA",
            context_messages=ctx.context_messages,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            return _result(
                "I couldn't understand that plan question. "
                "Try asking about specific days, meals, activities, or content."
            )
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=plan_xml,
                schema=schema,
            )
        except Exception:
            return _result("Something went wrong while querying the plan.")

        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        step_scoring_trace = getattr(exec_result.retrieval_detail, "step_scoring_trace", []) or []

        if self._result_verifier and per_node:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="PLAN_QA",
                context={"active_task_id": task_id},
            )
            per_node = v_res.verified_nodes

        formatted = _format_plan_nodes(per_node)
        hint = formatted

        affected_paths = [
            item.get("tree_path") or []
            for item in per_node
        ]

        return HandlerResult(
            session_updates=SessionUpdate(),
            generation_hint=hint,
            intent_result=IntentResult(
                intent="PLAN_QA",
                generation_hint=hint,
                xpath_query=gen_result.xpath_query,
                original_query=request,
                affected_node_paths=affected_paths,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            ),
        )


def _result(hint: str) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="PLAN_QA",
            generation_hint=hint,
        ),
    )
