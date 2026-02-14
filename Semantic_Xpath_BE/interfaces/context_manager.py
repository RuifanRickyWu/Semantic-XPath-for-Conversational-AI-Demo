from __future__ import annotations

from typing import Protocol

from common.types import ConversationContext, FocusLabels, FocusMemory, IntentMemory


class ConversationContextStore(Protocol):
    def get_context(self, session_id: str) -> ConversationContext:
        ...

    def get_messages(self, session_id: str) -> list[dict[str, str]]:
        ...

    def record_turn(
        self,
        session_id: str,
        user_utterance: str,
        assistant_message: str,
        timestamp: str | None = None,
    ) -> None:
        ...

    def update_focus_labels(self, session_id: str, patch: FocusLabels) -> None:
        ...

    def update_intent_memory(self, session_id: str, patch: IntentMemory) -> None:
        ...
