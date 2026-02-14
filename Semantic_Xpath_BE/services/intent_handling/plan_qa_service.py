"""
Plan QA Service - Handles the PLAN_QA intent (stub).

Will answer questions about plan content using the retriever
to locate relevant nodes and the chatter to formulate the response.

Dependencies (to be wired when implemented):
- retriever service/client
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_context import IntentContext


class PlanQAService:
    """Stub handler for PLAN_QA intent."""

    intent: str = "PLAN_QA"

    def handle(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement retriever -> chatter flow
        if ctx.routing.requires_clarification and ctx.routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=ctx.routing.clarification_question,
            )
        return HandlerResult(session_updates=SessionUpdate())
