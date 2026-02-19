"""
Session scope helpers.

Provides a request-scoped session id via contextvars so shared services can
resolve the correct per-session storage without changing every call site.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator


_SESSION_ID: ContextVar[str] = ContextVar("semantic_xpath_session_id", default="default")
_SAFE_SESSION_RE = re.compile(r"[^a-zA-Z0-9_-]")


def get_current_session_id() -> str:
    return _SESSION_ID.get() or "default"


def set_current_session_id(session_id: str) -> Token:
    safe = (session_id or "default").strip() or "default"
    return _SESSION_ID.set(safe)


def reset_current_session_id(token: Token) -> None:
    _SESSION_ID.reset(token)


def to_safe_session_folder(session_id: str) -> str:
    raw = (session_id or "default").strip() or "default"
    sanitized = _SAFE_SESSION_RE.sub("_", raw)
    return sanitized[:128] or "default"


@contextmanager
def session_scope(session_id: str) -> Iterator[None]:
    token = set_current_session_id(session_id)
    try:
        yield
    finally:
        reset_current_session_id(token)
