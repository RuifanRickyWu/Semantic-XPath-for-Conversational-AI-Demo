"""
Orchestrator Service - Central turn-level orchestrator.

Coordinates the full pipeline for each user message:
  1. Load session
  2. Load conversation context
  3. Route (intent classification)
  4. Sanitize routing
  5. Dispatch to intent handler
  6. Realize response (chatting)
  7. Update session
  8. Record turn in context

Migrated from Semantic_XPath_Demo/refactor/controller_core/controller.py.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from common.types import (
    HandlerResult,
    IntentMemory,
    IntentRequest,
    IntentResult,
    RealizeRequest,
    RegistryApplyRequest,
    RouteInput,
    RoutingDecision,
    SessionSnapshot,
    SessionUpdate,
    TurnRequest,
    TurnResponse,
    TurnTelemetry,
)
from interfaces import Chatting, Routting, TaskRegistry
from services.intent_handling.base_chat_service import BaseChatService
from services.intent_handling.intent_handling_service import IntentContext, IntentHandler
from services.intent_handling.plan_edit_service import PlanEditService
from stores.context_store import ContextStore
from services.intent_handling.plan_create_service import PlanCreateService
from services.intent_handling.plan_qa_service import PlanQAService
from services.intent_handling.registry_delete_service import RegistryDeleteService
from services.intent_handling.registry_edit_service import RegistryEditService
from services.intent_handling.registry_qa_service import RegistryQAService
from stores.session_store import SessionStore


class OrchestratorService:
    """Orchestrates a single conversation turn end-to-end."""

    def __init__(
        self,
        routting: Routting,
        session_service: SessionStore,
        context_service: ContextStore,
        plan_create_service: PlanCreateService,
        chatting: Chatting,
        registry: TaskRegistry | None = None,
        chat_service: IntentHandler | None = None,
        plan_qa_service: IntentHandler | None = None,
        plan_edit_service: IntentHandler | None = None,
        registry_qa_service: IntentHandler | None = None,
        registry_edit_service: IntentHandler | None = None,
        registry_delete_service: IntentHandler | None = None,
        grounded_when_state: bool = True,
    ) -> None:
        self.routting = routting
        self.session_service = session_service
        self.context_service = context_service
        self.registry = registry
        self.chatting = chatting
        self.grounded_when_state = grounded_when_state
        plan_edit = plan_edit_service or PlanEditService()
        self.intent_handlers: dict[str, IntentHandler] = {
            "CHAT": chat_service or BaseChatService(),
            "PLAN_CREATE": plan_create_service,
            "PLAN_QA": plan_qa_service or PlanQAService(),
            "PLAN_ADD": plan_edit,
            "PLAN_UPDATE": plan_edit,
            "PLAN_DELETE": plan_edit,
            "REGISTRY_QA": registry_qa_service or RegistryQAService(),
            "REGISTRY_EDIT": registry_edit_service or RegistryEditService(),
            "REGISTRY_DELETE": registry_delete_service or RegistryDeleteService(),
        }

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
        session = self._hydrate_session_from_registry(req.session_id, session)

        # 2) Load conversation context
        context_messages = self.context_service.get_messages(req.session_id)
        memory = self.context_service.get_context(req.session_id)

        # 3) Route
        route_result = self.routting.route(
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

        # 4) Dispatch to intent handler(s)
        combined = self._dispatch_all(
            effective_req,
            session,
            routing,
            telemetry,
            memory,
            context_messages,
        )

        # 5) Realize response
        assistant_message = self._realize_response(
            effective_req, session, routing, combined,
            memory=memory, context_messages=context_messages,
        )

        # 6) Apply session updates
        if self._has_session_updates(combined.session_updates):
            self.session_service.update_session(
                req.session_id, combined.session_updates
            )

        # 7) Record turn in context
        self._record_turn(effective_req, assistant_message, routing)

        return TurnResponse(
            assistant_message=assistant_message,
            routing=routing,
            session_updates=combined.session_updates,
            telemetry=telemetry,
            intent_results=combined.intent_results,
        )

    # ------------------------------------------------------------------
    # Intent dispatch
    # ------------------------------------------------------------------

    def _dispatch_all(
        self,
        req: TurnRequest,
        session: SessionSnapshot,
        routing: RoutingDecision,
        telemetry: TurnTelemetry,
        memory,
        context_messages: Optional[list[dict[str, str]]],
    ) -> HandlerResult:
        """Dispatch to handlers for each intent, apply updates between calls, combine results."""
        results: list[tuple[str, HandlerResult]] = []
        current_session = session

        for idx, ir in enumerate(routing.intent_requests):
            intent = ir.intent
            handler = self.intent_handlers.get(intent)
            utterance = routing.get_request(idx, req.user_utterance)
            single_routing = RoutingDecision(
                intent_requests=[IntentRequest(intent=intent, request=ir.request)],
                intent_label=routing.intent_label,
                confidence=routing.confidence,
                requires_clarification=routing.requires_clarification,
                clarification_question=routing.clarification_question,
            )

            if handler is None:
                results.append((intent, HandlerResult(session_updates=SessionUpdate())))
                continue
            req_i = TurnRequest(
                user_utterance=utterance,
                session_id=req.session_id,
                timestamp=req.timestamp,
                original_user_utterance=req.original_user_utterance,
                conversation_context=req.conversation_context,
            )

            ctx = IntentContext(
                req=req_i,
                session=current_session,
                routing=single_routing,
                telemetry=telemetry,
                memory=memory,
                context_messages=context_messages,
            )
            hr = handler.handle(ctx)
            results.append((intent, hr))
            current_session = self._apply_session_updates(current_session, hr.session_updates)

        return self._combine_handler_results(results)

    @staticmethod
    def _apply_session_updates(
        snap: SessionSnapshot, update: SessionUpdate
    ) -> SessionSnapshot:
        if not any([
            update.active_task_id is not None,
            update.active_version_id is not None,
            update.focus_path is not None,
            update.last_retrieved_node_ids is not None,
        ]):
            return snap
        return SessionSnapshot(
            active_task_id=update.active_task_id if update.active_task_id is not None else snap.active_task_id,
            active_version_id=update.active_version_id if update.active_version_id is not None else snap.active_version_id,
            focus_path=update.focus_path if update.focus_path is not None else snap.focus_path,
            last_retrieved_node_ids=(
                update.last_retrieved_node_ids
                if update.last_retrieved_node_ids is not None
                else snap.last_retrieved_node_ids
            ),
        )

    def _combine_handler_results(
        self, results: list[tuple[str, HandlerResult]]
    ) -> HandlerResult:
        merged = SessionUpdate()
        intent_results: list[dict] = []

        for intent, hr in results:
            if hr.session_updates.active_task_id is not None:
                merged.active_task_id = hr.session_updates.active_task_id
            if hr.session_updates.active_version_id is not None:
                merged.active_version_id = hr.session_updates.active_version_id
            if hr.session_updates.focus_path is not None:
                merged.focus_path = hr.session_updates.focus_path
            if hr.session_updates.last_retrieved_node_ids is not None:
                merged.last_retrieved_node_ids = hr.session_updates.last_retrieved_node_ids

            ir = hr.intent_result or IntentResult(
                intent=intent,
                generation_hint=hr.generation_hint,
                task_name=hr.task_name,
                task_xml=hr.task_xml,
            )
            intent_results.append(asdict(ir))

        stop = any(hr.stop for _, hr in results)
        generation_hint = results[-1][1].generation_hint if results else None
        task_name = results[-1][1].task_name if results else None
        task_xml = results[-1][1].task_xml if results else None

        return HandlerResult(
            session_updates=merged,
            stop=stop,
            generation_hint=generation_hint,
            task_name=task_name,
            task_xml=task_xml,
            intent_results=intent_results,
        )

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
        intent_results = handler_result.intent_results

        if handler_result.stop:
            if handler_result.generation_hint:
                state_context = {"clarification_question": handler_result.generation_hint}
        else:
            intent = routing.intent
            registry_intents = ("REGISTRY_QA", "REGISTRY_EDIT", "REGISTRY_DELETE")
            plan_intents = ("PLAN_QA", "PLAN_ADD", "PLAN_UPDATE", "PLAN_DELETE", "PLAN_CREATE")
            if intent in registry_intents and handler_result.generation_hint:
                registry_context = {"generation_hint": handler_result.generation_hint}
            if intent in plan_intents:
                if handler_result.generation_hint:
                    state_context = {"generation_hint": handler_result.generation_hint}
                if intent == "PLAN_CREATE":
                    state_context = state_context or {}
                    if handler_result.task_name:
                        state_context["task_name"] = handler_result.task_name
                    if handler_result.task_xml:
                        state_context["task_xml"] = handler_result.task_xml
            if intent_results and len(routing.intents) > 1:
                for ir in intent_results or []:
                    ir = ir or {}
                    i = ir.get("intent", "")
                    hint = ir.get("generation_hint")
                    if hint and i in registry_intents and registry_context is None:
                        registry_context = {"generation_hint": hint}
                    if hint and i in plan_intents:
                        state_context = state_context or {}
                        state_context["generation_hint"] = state_context.get("generation_hint") or hint
                        if ir.get("task_name"):
                            state_context["task_name"] = ir["task_name"]
                        if ir.get("task_xml"):
                            state_context["task_xml"] = ir["task_xml"]

        constraints = None
        if any(i in ("PLAN_QA", "PLAN_ADD", "PLAN_UPDATE", "PLAN_DELETE", "PLAN_CREATE") for i in routing.intents):
            constraints = {"grounded": self.grounded_when_state}

        hint_to_chatter = None
        if state_context and isinstance(state_context, dict):
            hint_to_chatter = state_context.get("generation_hint") or state_context.get("clarification_question")
        if hint_to_chatter is None and registry_context and isinstance(registry_context, dict):
            hint_to_chatter = registry_context.get("generation_hint")
        return self.chatting.realize(
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
                intent_results=intent_results,
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
        return routing

    def _hydrate_session_from_registry(
        self, session_id: str, session: SessionSnapshot
    ) -> SessionSnapshot:
        if self.registry is None:
            return session
        if session.active_task_id and session.active_version_id:
            return session
        registry_result = self.registry.apply(RegistryApplyRequest(action="LIST_TASKS"))
        active_task_id = registry_result.active_task_id
        active_version_id = registry_result.active_version_id
        if not active_task_id or not active_version_id:
            return session
        self.session_service.update_session(
            session_id,
            SessionUpdate(
                active_task_id=active_task_id,
                active_version_id=active_version_id,
            ),
        )
        return self.session_service.get_session(session_id)

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
        if not routing.requires_clarification and routing.intent_requests:
            parts = [ir.request.strip() for ir in routing.intent_requests if ir.request.strip()]
            if parts:
                utterance = "; ".join(parts)
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
