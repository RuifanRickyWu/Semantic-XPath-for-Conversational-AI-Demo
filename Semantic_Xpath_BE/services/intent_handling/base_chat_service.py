"""
Base Chat Service - Handles the CHAT intent.

For CHAT, no side effects are required at handler stage.
Response realization is performed by the chatting service.
"""

from __future__ import annotations

from common.types import HandlerResult, SessionUpdate
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler


class BaseChatService(BaseIntentHandler):
    """Handler for CHAT intent with no state mutation."""

    intent: str = "CHAT"

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        return HandlerResult(session_updates=SessionUpdate())
