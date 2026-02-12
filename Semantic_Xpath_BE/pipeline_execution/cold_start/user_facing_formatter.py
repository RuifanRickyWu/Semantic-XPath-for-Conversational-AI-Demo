"""
Format user-facing output from cold start.
"""

from __future__ import annotations

from typing import Dict, Union


def format_user_facing(user_facing: Union[Dict, str]) -> str:
    if not user_facing:
        return ""

    if isinstance(user_facing, str):
        return user_facing.strip()

    title = str(user_facing.get("title", "")).strip()
    overview = str(user_facing.get("overview", "")).strip()
    sections = user_facing.get("sections", []) or []

    lines: list[str] = []
    if title:
        lines.append(title)
    if overview:
        lines.append("")
        lines.append(overview)

    for section in sections:
        sec_title = str(section.get("title", "")).strip()
        sec_summary = str(section.get("summary", "")).strip()
        bullets = section.get("bullets", []) or []
        if not sec_title and not sec_summary and not bullets:
            continue
        lines.append("")
        if sec_title:
            lines.append(sec_title)
        if sec_summary:
            lines.append(sec_summary)
        for b in bullets:
            lines.append(f"- {str(b).strip()}")

    return "\n".join(lines).strip()
