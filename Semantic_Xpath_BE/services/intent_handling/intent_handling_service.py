"""
Shared IntentContext dataclass and intent-handling abstractions.

All intent handler services receive an IntentContext and return a HandlerResult.

Migrated from Semantic_XPath_Demo/refactor/controller_core/intent_handlers.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from common.types import (
    ConversationContext,
    HandlerResult,
    RoutingDecision,
    SessionSnapshot,
    TurnRequest,
    TurnTelemetry,
)


@dataclass
class IntentContext:
    """All data available to an intent handler for a single turn."""
    req: TurnRequest
    session: SessionSnapshot
    routing: RoutingDecision
    telemetry: TurnTelemetry
    memory: ConversationContext | None = None
    context_messages: list[dict[str, str]] | None = None


class IntentHandler(Protocol):
    """Protocol that every intent handler service must satisfy."""
    intent: str

    def handle(self, ctx: IntentContext) -> HandlerResult:
        ...


class BaseIntentHandler(ABC):
    """Common base class for all intent handlers."""

    intent: str

    def handle(self, ctx: IntentContext) -> HandlerResult:
        if ctx.routing.requires_clarification and ctx.routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=ctx.routing.clarification_question,
            )
        return self._handle_impl(ctx)

    @abstractmethod
    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        ...
