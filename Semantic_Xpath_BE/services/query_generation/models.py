"""Shared request/response models for semantic XPath query generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryGenerationRequest:
    """Request for generating a semantic XPath query."""

    utterance: str
    loaded_schema: Dict[str, Any]
    context_messages: Optional[List[Dict[str, str]]] = None
    intent: Optional[str] = None
    hints: Optional[Dict[str, Any]] = None
    active_task_id: Optional[str] = None  # For registry: scope versions query when task not mentioned


@dataclass
class QueryGenerationResult:
    """Generated semantic XPath query and parser validation status."""

    xpath_query: str
    parsed_ok: bool
    error: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    registry_target: Optional[str] = None  # "tasks" | "versions" for registry scope
