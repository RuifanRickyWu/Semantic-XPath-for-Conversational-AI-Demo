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
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler


class PlanEditService(BaseIntentHandler):
    """Stub handler for PLAN_EDIT intent."""

    intent: str = "PLAN_EDIT"

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement retriever -> edit_planner -> xml_manager -> validator flow
        return HandlerResult(session_updates=SessionUpdate())
