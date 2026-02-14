"""
State Store - In-memory plan state persistence.

Stores TaskState objects keyed by (task_id, version_id).
"""

from __future__ import annotations

from typing import Dict, Tuple

from common.types import CommitRequest, CommitResult, TaskState


class StateStore:
    """Simple in-memory state store for plan XML."""

    def __init__(self) -> None:
        self._states: Dict[Tuple[str, str], TaskState] = {}

    def load(self, task_id: str, version_id: str) -> TaskState:
        state = self._states.get((task_id, version_id))
        if state is None:
            raise FileNotFoundError(f"State not found for {task_id}/{version_id}")
        return state

    def commit(self, req: CommitRequest) -> CommitResult:
        if req.new_state is None:
            return CommitResult(status="FAILED", errors=["new_state required"])
        state = req.new_state
        self._states[(state.task_id, state.version_id)] = state
        return CommitResult(status="OK", new_version_id=state.version_id)
