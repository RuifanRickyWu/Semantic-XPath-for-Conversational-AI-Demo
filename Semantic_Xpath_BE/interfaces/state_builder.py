from __future__ import annotations

from typing import Protocol

from common.types import TaskState


class StateBuilder(Protocol):
    def build_initial_state(
        self,
        utterance: str,
        task_id: str,
        version_id: str,
        context_messages: list[dict[str, str]] | None = None,
    ) -> TaskState:
        ...
