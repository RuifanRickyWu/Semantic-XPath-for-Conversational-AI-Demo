"""
Orchestrator Service - Central turn-level orchestrator.

Coordinates the full pipeline for each user message:
  1. Load session
  2. Load conversation context
  3. Route (intent classification)
  4. Sanitize routing
  5. Dispatch to intent handler
  6. Realize response (chatter)
  7. Update session
  8. Record turn in context

Migrated from Semantic_XPath_Demo/refactor/controller_core/controller.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from common.types import (
    HandlerResult,
    IntentMemory,
    RealizeRequest,
    RouteInput,
    RoutingDecision,
    SessionSnapshot,
    SessionUpdate,
    TurnRequest,
    TurnResponse,
    TurnTelemetry,
)
from interfaces import Chatter, Router
from stores.context_store import ContextStore
from services.intent_handling.plan_create_service import PlanCreateService
from stores.session_store import SessionStore


class OrchestratorService:
    """Orchestrates a single conversation turn end-to-end."""

    def __init__(
        self,
        router: Router,
        session_service: SessionStore,
        context_service: ContextStore,
        plan_create_service: PlanCreateService,
        chatter: Chatter,
        grounded_when_state: bool = True,
    ) -> None:
        self.router = router
        self.session_service = session_service
        self.context_service = context_service
        self.plan_create_service = plan_create_service
        self.chatter = chatter
        self.grounded_when_state = grounded_when_state

    def orchestrate(self, message: str, session_id: str) -> TurnResponse:
        """Run the full turn pipeline and return a TurnResponse."""
        req = TurnRequest(
            user_utterance=message,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        telemetry = TurnTelemetry()

        # 1) Load session
        session = self.session_service.get_session(req.session_id)

        # 2) Load conversation context
        context_messages = self.context_service.get_messages(req.session_id)
        memory = self.context_service.get_context(req.session_id)

        # 3) Route
        route_result = self.router.route(
            RouteInput(req.user_utterance, session, context_messages=context_messages)
        )
        routing = self._sanitize_routing(route_result.routing, session, telemetry)

        # Normalize effective utterance
        effective_req = req
        if route_result.effective_utterance != req.user_utterance:
            effective_req = TurnRequest(
                user_utterance=route_result.effective_utterance,
                session_id=req.session_id,
                timestamp=req.timestamp,
                original_user_utterance=route_result.original_utterance,
            )

        # 4) Dispatch to intent handler
        handler_result = self._dispatch(effective_req, routing, context_messages)

        # 5) Realize response
        assistant_message = self._realize_response(
            effective_req, session, routing, handler_result,
            memory=memory, context_messages=context_messages,
        )

        # 6) Apply session updates
        if self._has_session_updates(handler_result.session_updates):
            self.session_service.update_session(
                req.session_id, handler_result.session_updates
            )

        # 7) Record turn in context
        self._record_turn(effective_req, assistant_message, routing)

        return TurnResponse(
            assistant_message=assistant_message,
            routing=routing,
            session_updates=handler_result.session_updates,
            telemetry=telemetry,
        )

    # ------------------------------------------------------------------
    # Intent dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        req: TurnRequest,
        routing: RoutingDecision,
        context_messages: Optional[list[dict[str, str]]],
    ) -> HandlerResult:
        # Handle clarification for any intent
        if routing.requires_clarification and routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=routing.clarification_question,
            )

        if routing.intent == "PLAN_CREATE":
            return self.plan_create_service.handle(
                req, routing, context_messages=context_messages,
            )

        # CHAT and all other intents: no side effects (stubs for future)
        return HandlerResult(session_updates=SessionUpdate())

    # ------------------------------------------------------------------
    # Response realization
    # ------------------------------------------------------------------

    def _realize_response(
        self,
        req: TurnRequest,
        session: SessionSnapshot,
        routing: RoutingDecision,
        handler_result: HandlerResult,
        memory=None,
        context_messages=None,
    ) -> str:
        registry_context = None
        state_context = None

        if handler_result.stop:
            if handler_result.generation_hint:
                state_context = {"clarification_question": handler_result.generation_hint}
        else:
            if routing.intent in ("REGISTRY_QA", "REGISTRY_EDIT"):
                if handler_result.generation_hint:
                    registry_context = {"generation_hint": handler_result.generation_hint}
            else:
                if handler_result.generation_hint:
                    state_context = {"generation_hint": handler_result.generation_hint}
                if routing.intent == "PLAN_CREATE":
                    if state_context is None:
                        state_context = {}
                    if handler_result.task_name:
                        state_context["task_name"] = handler_result.task_name
                    if handler_result.task_xml:
                        state_context["task_xml"] = handler_result.task_xml

        constraints = None
        if routing.intent in ("PLAN_QA", "PLAN_EDIT", "PLAN_CREATE"):
            constraints = {"grounded": self.grounded_when_state}

        return self.chatter.realize(
            RealizeRequest(
                utterance=req.user_utterance,
                routing=routing,
                session=session,
                original_utterance=req.original_user_utterance,
                conversation_context=memory,
                context_messages=context_messages,
                registry_context=registry_context,
                state_context=state_context,
                constraints=constraints,
            )
        )

    # ------------------------------------------------------------------
    # Routing sanitization
    # ------------------------------------------------------------------

    def _sanitize_routing(
        self,
        routing: RoutingDecision,
        session: SessionSnapshot,
        telemetry: TurnTelemetry,
    ) -> RoutingDecision:
        if routing.intent in ("CHAT", "PLAN_CREATE") and routing.registry_op == 1:
            telemetry.events.append("routing_autofix:registry_op_disabled")
            routing.registry_op = 0

        if routing.intent in ("REGISTRY_QA", "REGISTRY_EDIT") and routing.registry_op == 0:
            telemetry.events.append("routing_autofix:force_registry_op")
            routing.registry_op = 1

        if routing.intent in ("PLAN_QA", "PLAN_EDIT") and not (
            session.active_task_id and session.active_version_id
        ):
            if routing.registry_op == 0:
                telemetry.events.append("routing_autofix:force_registry")
            routing.registry_op = 1

        return routing

    # ------------------------------------------------------------------
    # Turn recording
    # ------------------------------------------------------------------

    def _record_turn(
        self, req: TurnRequest, assistant_message: str, routing: RoutingDecision
    ) -> None:
        self.context_service.record_turn(
            req.session_id,
            req.user_utterance,
            assistant_message,
            timestamp=req.timestamp,
        )
        utterance = req.user_utterance
        if not routing.requires_clarification and routing.reformulated_utterance:
            utterance = routing.reformulated_utterance
        self.context_service.update_intent_memory(
            req.session_id,
            IntentMemory(
                last_intent=routing.intent,
                last_intent_label=routing.intent_label,
                last_user_utterance=utterance,
                awaiting_clarification=bool(routing.requires_clarification),
                clarification_question=(
                    routing.clarification_question if routing.requires_clarification else None
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_session_updates(update: SessionUpdate) -> bool:
        return any([
            update.active_task_id is not None,
            update.active_version_id is not None,
            update.focus_path is not None,
            update.last_retrieved_node_ids is not None,
        ])
