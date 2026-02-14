"""
Registry QA Service - Handles the REGISTRY_QA intent (stub).

Will list tasks/versions from the registry and format the results
for the user via the chatter.

Dependencies (to be wired when implemented):
- expanded registry store (LIST_TASKS, LIST_VERSIONS)
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_context import IntentContext


class RegistryQAService:
    """Stub handler for REGISTRY_QA intent."""

    intent: str = "REGISTRY_QA"

    def handle(self, ctx: IntentContext) -> HandlerResult:
        # TODO: implement registry query -> chatter flow
        if ctx.routing.requires_clarification and ctx.routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=ctx.routing.clarification_question,
            )
        return HandlerResult(session_updates=SessionUpdate())
