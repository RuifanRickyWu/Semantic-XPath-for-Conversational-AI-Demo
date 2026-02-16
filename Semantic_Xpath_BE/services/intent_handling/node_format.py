"""Shared utilities for formatting node content (no hardcoded field names)."""

from __future__ import annotations

from typing import Any, Dict, List


def extract_node_content(node: Dict[str, Any]) -> str:
    """
    Extract all string content from a node dict.
    No hardcoded field names - uses whatever keys and values exist.
    """
    parts: List[str] = []
    skip = {"type", "attributes"}
    for k, v in node.items():
        if k in skip or v is None:
            continue
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str) and x.strip():
                    parts.append(x.strip())
    attrs = node.get("attributes") or {}
    for v in attrs.values():
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return " | ".join(parts) if parts else ""


def path_to_display_str(path_data: List[Any]) -> str:
    """Convert tree_path_display or path_segments to readable path string."""
    parts = []
    for seg in path_data:
        if isinstance(seg, dict):
            t = seg.get("type", "")
            a = seg.get("attributes") or {}
            idx = a.get("index") or a.get("number")
            parts.append(f"{t} {idx}" if idx is not None and t else (t or ""))
        elif isinstance(seg, (tuple, list)) and len(seg) >= 2:
            parts.append(f"{seg[0]} {seg[1]}")
        elif seg:
            parts.append(str(seg))
    return " > ".join(p for p in parts if p)


def format_per_node_for_hint(per_node: List[Dict[str, Any]]) -> str:
    """
    Light format: path + content for each node.
    No hardcoded field names - uses extract_node_content.
    """
    if not per_node:
        return "No matching content found."

    lines = []
    for i, item in enumerate(per_node):
        node = item.get("node") or {}
        path_data = item.get("tree_path_display") or item.get("tree_path") or []
        context = path_to_display_str(path_data) if path_data else node.get("type", "?")
        text = extract_node_content(node)

        if text:
            snippet = (text[:120] + "…") if len(text) > 120 else text
            lines.append(f"- {context}: {snippet}")
        else:
            attrs = node.get("attributes") or {}
            idx = attrs.get("index") or attrs.get("number") or (i + 1)
            lines.append(f"- {context} ({idx})")

    return "\n".join(lines)
