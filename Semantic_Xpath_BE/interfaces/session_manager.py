from __future__ import annotations

from typing import Protocol

from common.types import SessionSnapshot, SessionUpdate


class SessionManager(Protocol):
    def get_session(self, session_id: str) -> SessionSnapshot:
        ...

    def update_session(self, session_id: str, patch: SessionUpdate) -> None:
        ...
