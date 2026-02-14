"""
Tests for OrchestratorService.

Adapted from Semantic_XPath_Demo/refactor/tests/test_controller.py.
Uses mock/stub dependencies to test the orchestrator's pipeline logic:
routing sanitization, reformulation, context passing, clarification,
plan_create field forwarding, session updates, and intent memory recording.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pytest

from common.types import (
    ConversationContext,
    ContextTurn,
    HandlerResult,
    IntentMemory,
    RealizeRequest,
    RouteInput,
    RouteResult,
    RoutingDecision,
    RegistryApplyResult,
    SessionSnapshot,
    SessionUpdate,
    TurnRequest,
)
from services.intent_handling.intent_handling_service import IntentContext
from services.orchestrator_service import OrchestratorService
from stores.context_store import ContextStore
from stores.session_store import SessionStore


# ---------------------------------------------------------------------------
# Stubs / mocks
# ---------------------------------------------------------------------------


class StubRoutting:
    """Returns a fixed RouteResult for any input."""

    def __init__(self, result: RouteResult) -> None:
        self.result = result
        self.last_input: Optional[RouteInput] = None

    def route(self, input: RouteInput) -> RouteResult:
        self.last_input = input
        return self.result


class StubPlanCreateService:
    """Returns a fixed HandlerResult for any plan create request."""

    def __init__(self, result: HandlerResult | None = None) -> None:
        self.result = result or HandlerResult(session_updates=SessionUpdate())
        self.last_args: Optional[tuple] = None

    def handle(self, ctx: IntentContext) -> HandlerResult:
        self.last_args = (ctx.req, ctx.routing, ctx.context_messages)
        return self.result


class RecordingChatting:
    """Records all realize() calls and returns 'ok'."""

    def __init__(self) -> None:
        self.requests: List[RealizeRequest] = []

    def realize(self, req: RealizeRequest) -> str:
        self.requests.append(req)
        return "ok"


class StubRegistry:
    def __init__(self, result: RegistryApplyResult) -> None:
        self.result = result
        self.last_action: str | None = None

    def apply(self, req):
        self.last_action = req.action
        return self.result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mk_routing(
    intent: str, registry_op: int,
    reformulated: str | None = None, rc: bool = False,
) -> RoutingDecision:
    return RoutingDecision(
        intent=intent,
        registry_op=registry_op,
        intent_label=intent,
        confidence=0.9,
        requires_clarification=rc,
        clarification_question="clarify?" if rc else "",
        reformulated_utterance=reformulated,
    )


def make_orchestrator(
    route_result: RouteResult,
    plan_create_result: HandlerResult | None = None,
    context_service: ContextStore | None = None,
    registry=None,
):
    routting = StubRoutting(route_result)
    session_store = SessionStore()
    ctx_store = context_service or ContextStore(window_size=4, max_message_chars=600)
    plan_create = StubPlanCreateService(plan_create_result)
    chatting = RecordingChatting()

    orchestrator = OrchestratorService(
        routting=routting,
        session_service=session_store,
        context_service=ctx_store,
        plan_create_service=plan_create,
        chatting=chatting,
        registry=registry,
    )
    return orchestrator, routting, session_store, plan_create, chatting


def expected_registry_op(intent: str, initial: int, session_active: bool) -> int:
    if intent in {"CHAT", "PLAN_CREATE"}:
        return 0
    if intent in {"REGISTRY_QA", "REGISTRY_EDIT"}:
        return 1
    if intent in {"PLAN_QA", "PLAN_EDIT"} and not session_active:
        return 1
    return initial


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "variant,intent,session_active,initial_registry_op",
    [
        (v, intent, active, reg)
        for v in range(5)
        for intent in [
            "CHAT", "PLAN_QA", "PLAN_EDIT",
            "PLAN_CREATE", "REGISTRY_QA", "REGISTRY_EDIT",
        ]
        for active in [False, True]
        for reg in [0, 1]
    ],
)
def test_orchestrator_sanitize_registry_op(variant, intent, session_active, initial_registry_op):
    routing = mk_routing(intent, initial_registry_op)
    route_result = RouteResult(routing=routing, effective_utterance=f"u-{variant}")
    orchestrator, routting, session_store, plan_create, chatting = make_orchestrator(route_result)

    # Set up session state if needed
    if session_active:
        session_store.update_session(
            "s1", SessionUpdate(active_task_id="t1", active_version_id="v1")
        )

    orchestrator.orchestrate(f"u-{variant}", "s1")
    chatting_req = chatting.requests[-1]
    assert chatting_req.routing.registry_op == expected_registry_op(
        intent, initial_registry_op, session_active
    )


def test_orchestrator_reformulation_sets_original():
    routing = mk_routing("CHAT", 0, reformulated="clear request")
    route_result = RouteResult(
        routing=routing,
        effective_utterance="clear request",
        original_utterance="messy request",
    )
    orchestrator, _, _, _, chatting = make_orchestrator(route_result)
    orchestrator.orchestrate("messy request", "s1")

    chatting_req = chatting.requests[-1]
    assert chatting_req.utterance == "clear request"
    assert chatting_req.original_utterance == "messy request"


def test_orchestrator_passes_context_to_chatting():
    routing = mk_routing("CHAT", 0)
    route_result = RouteResult(routing=routing, effective_utterance="hello")
    ctx_store = ContextStore(window_size=4, max_message_chars=600)
    # Pre-seed some context
    ctx_store.record_turn("s1", "hi", "hey there")

    orchestrator, _, _, _, chatting = make_orchestrator(
        route_result, context_service=ctx_store,
    )
    orchestrator.orchestrate("hello", "s1")

    chatting_req = chatting.requests[-1]
    assert chatting_req.context_messages is not None
    assert chatting_req.conversation_context is not None


def test_orchestrator_clarification_mapping():
    routing = mk_routing("PLAN_EDIT", 0)
    route_result = RouteResult(routing=routing, effective_utterance="edit")
    # Plan edit is currently a stub in the orchestrator (returns empty HandlerResult).
    # But if the handler returns stop=True with generation_hint, it should map to state_context.
    # We test via PLAN_CREATE with a clarification result.
    routing_pc = mk_routing("PLAN_CREATE", 0)
    route_result_pc = RouteResult(routing=routing_pc, effective_utterance="create")
    plan_result = HandlerResult(stop=True, generation_hint="Need clarification")
    orchestrator, _, _, _, chatting = make_orchestrator(route_result_pc, plan_result)
    orchestrator.orchestrate("create", "s1")

    chatting_req = chatting.requests[-1]
    assert chatting_req.state_context == {"clarification_question": "Need clarification"}


def test_orchestrator_plan_create_passes_task_fields():
    routing = mk_routing("PLAN_CREATE", 0)
    route_result = RouteResult(routing=routing, effective_utterance="create")
    plan_result = HandlerResult(task_name="My Plan", task_xml="<Plan/>")
    orchestrator, _, _, _, chatting = make_orchestrator(route_result, plan_result)
    orchestrator.orchestrate("create", "s1")

    chatting_req = chatting.requests[-1]
    assert chatting_req.state_context is not None
    assert chatting_req.state_context.get("task_name") == "My Plan"
    assert chatting_req.state_context.get("task_xml") == "<Plan/>"


def test_orchestrator_applies_session_updates():
    routing = mk_routing("PLAN_CREATE", 0)
    route_result = RouteResult(routing=routing, effective_utterance="create")
    plan_result = HandlerResult(
        session_updates=SessionUpdate(active_task_id="t1", active_version_id="v1")
    )
    orchestrator, _, session_store, _, _ = make_orchestrator(route_result, plan_result)
    orchestrator.orchestrate("create", "s1")

    session = session_store.get_session("s1")
    assert session.active_task_id == "t1"
    assert session.active_version_id == "v1"


def test_orchestrator_records_intent_memory_with_reformulated_utterance():
    routing = mk_routing("CHAT", 0, reformulated="clean")
    route_result = RouteResult(
        routing=routing,
        effective_utterance="clean",
        original_utterance="noisy",
    )
    ctx_store = ContextStore(window_size=4, max_message_chars=600)
    orchestrator, _, _, _, _ = make_orchestrator(
        route_result, context_service=ctx_store,
    )
    orchestrator.orchestrate("noisy", "s1")

    ctx = ctx_store.get_context("s1")
    assert ctx.intent_memory is not None
    assert ctx.intent_memory.last_user_utterance == "clean"
    assert ctx.intent_memory.last_intent == "CHAT"


def test_orchestrator_hydrates_session_from_registry_when_empty():
    routing = mk_routing("CHAT", 0)
    route_result = RouteResult(routing=routing, effective_utterance="hello")
    registry = StubRegistry(
        RegistryApplyResult(active_task_id="t99", active_version_id="v7")
    )
    orchestrator, _, session_store, _, _ = make_orchestrator(
        route_result, registry=registry
    )

    orchestrator.orchestrate("hello", "s1")

    session = session_store.get_session("s1")
    assert session.active_task_id == "t99"
    assert session.active_version_id == "v7"
    assert registry.last_action == "LIST_TASKS"
