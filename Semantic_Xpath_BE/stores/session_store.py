"""
Session Store - In-memory session state management.

Tracks the active task, version, focus path, and retrieved nodes per session.
"""

from __future__ import annotations

from typing import Dict

from common.types import SessionSnapshot, SessionUpdate


class SessionStore:
    """In-memory session manager keyed by session_id."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionSnapshot] = {}

    def get_session(self, session_id: str) -> SessionSnapshot:
        return self._sessions.get(session_id) or SessionSnapshot()

    def update_session(self, session_id: str, patch: SessionUpdate) -> None:
        current = self._sessions.get(session_id) or SessionSnapshot()
        if patch.active_task_id is not None:
            current.active_task_id = patch.active_task_id
        if patch.active_version_id is not None:
            current.active_version_id = patch.active_version_id
        if patch.focus_path is not None:
            current.focus_path = patch.focus_path
        if patch.last_retrieved_node_ids is not None:
            current.last_retrieved_node_ids = patch.last_retrieved_node_ids
        self._sessions[session_id] = current

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
