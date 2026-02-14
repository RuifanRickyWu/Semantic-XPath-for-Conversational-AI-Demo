"""
Plan Edit Service - Handles the PLAN_EDIT intent (stub).

Will modify plan content using:
  retriever -> edit_planner -> xml_manager -> validator -> state commit

Dependencies (to be wired when implemented):
- retriever service/client
- edit_planner client
- xml_manager service
- validator service
- state store
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_context import IntentContext


class PlanEditService:
    """Stub handler for PLAN_EDIT intent."""

    intent: str = "PLAN_EDIT"

    def handle(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement retriever -> edit_planner -> xml_manager -> validator flow
        if ctx.routing.requires_clarification and ctx.routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=ctx.routing.clarification_question,
            )
        return HandlerResult(session_updates=SessionUpdate())
