"""
Registry Edit Service - Handles the REGISTRY_EDIT intent (stub).

Will perform registry mutations: activate task, switch version,
create new version, etc.

Dependencies (to be wired when implemented):
- expanded registry store (ACTIVATE_TASK, SWITCH_VERSION, CREATE_VERSION)
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler


class RegistryEditService(BaseIntentHandler):
    """Stub handler for REGISTRY_EDIT intent."""

    intent: str = "REGISTRY_EDIT"

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement registry mutation -> session update flow
        return HandlerResult(session_updates=SessionUpdate())
