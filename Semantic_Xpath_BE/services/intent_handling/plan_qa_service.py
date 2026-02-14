"""
Plan QA Service - Handles the PLAN_QA intent (stub).

Will answer questions about plan content using the retriever
to locate relevant nodes and the chatting service to formulate the response.

Dependencies (to be wired when implemented):
- retriever service/client
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler


class PlanQAService(BaseIntentHandler):
    """Stub handler for PLAN_QA intent."""

    intent: str = "PLAN_QA"

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement retriever -> chatting flow
        return HandlerResult(session_updates=SessionUpdate())
