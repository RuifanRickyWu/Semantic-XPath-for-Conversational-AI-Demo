"""Shared utility functions."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict


def strip_none(value: Any) -> Any:
    """Recursively strip None values from dicts/dataclasses/lists."""
    if is_dataclass(value):
        return strip_none(asdict(value))
    if isinstance(value, dict):
        return {k: strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [strip_none(v) for v in value if v is not None]
    return value


def safe_json_dumps(payload: Dict[str, Any]) -> str:
    """JSON-serialize a payload with consistent formatting."""
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
