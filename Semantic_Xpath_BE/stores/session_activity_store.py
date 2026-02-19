"""
Session activity tracking for idle-expiration.

Tracks per-session last-seen timestamps in memory and exposes helpers to:
- touch activity on each request
- check idle expiration by threshold seconds
- clear activity state when a session is deleted
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Dict


class SessionActivityStore:
    """In-memory tracker of session last activity timestamps."""

    def __init__(self) -> None:
        self._last_seen: Dict[str, datetime] = {}
        self._lock = Lock()

    def touch(self, session_id: str) -> None:
        sid = (session_id or "default").strip() or "default"
        with self._lock:
            self._last_seen[sid] = datetime.now(timezone.utc)

    def is_expired(self, session_id: str, idle_timeout_seconds: int) -> bool:
        sid = (session_id or "default").strip() or "default"
        with self._lock:
            last = self._last_seen.get(sid)
        if last is None:
            return False
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() > max(0, int(idle_timeout_seconds))

    def get_expired_session_ids(self, idle_timeout_seconds: int) -> list[str]:
        now = datetime.now(timezone.utc)
        ttl = max(0, int(idle_timeout_seconds))
        with self._lock:
            items = list(self._last_seen.items())
        expired: list[str] = []
        for sid, last in items:
            if (now - last).total_seconds() > ttl:
                expired.append(sid)
        return expired

    def get_tracked_session_count(self) -> int:
        with self._lock:
            return len(self._last_seen)

    def clear(self, session_id: str) -> None:
        sid = (session_id or "default").strip() or "default"
        with self._lock:
            self._last_seen.pop(sid, None)
