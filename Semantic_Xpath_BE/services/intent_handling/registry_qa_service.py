"""
Registry QA Service - Handles the REGISTRY_QA intent (stub).

Will list tasks/versions from the registry and format the results
for the user via the chatting service.

Dependencies (to be wired when implemented):
- expanded registry store (LIST_TASKS, LIST_VERSIONS)
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler


class RegistryQAService(BaseIntentHandler):
    """Stub handler for REGISTRY_QA intent."""

    intent: str = "REGISTRY_QA"

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement registry query -> chatting flow
        return HandlerResult(session_updates=SessionUpdate())
