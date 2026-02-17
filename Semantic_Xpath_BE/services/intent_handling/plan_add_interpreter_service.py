"""
Plan Add Interpreter Service - LLM-based XML fragment adder.

Takes container XML fragment + user add request and returns the container with new item(s) added.
Used by PlanEditService for PLAN_ADD intent. Operates only on container nodes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from common.utils import safe_json_dumps, strip_none


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_PATH = _BASE_DIR / "prompts" / "plan_add" / "plan_add_interpreter.txt"


class PlanAddInterpreterService:
    """Interprets user add requests and produces container XML with new content."""

    def __init__(
        self,
        client,
        prompt_path: Optional[Path] = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._prompt_path = prompt_path or _PROMPT_PATH
        self.max_retries = max(1, int(max_retries))
        self._system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            with open(self._prompt_path, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        return self._system_prompt

    def interpret(
        self,
        xml_fragment: str,
        user_request: str,
        context_messages: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """
        Produce container XML with new item(s) added.

        Args:
            xml_fragment: The container node XML (e.g. Day block).
            user_request: The user's add request.

        Returns:
            Updated container XML string (valid single element).
        """
        payload = strip_none({
            "xml_fragment": xml_fragment,
            "user_request": user_request,
        })
        prompt = (
            "Context:\n"
            f"{safe_json_dumps(payload)}\n\n"
            "Return ONLY valid XML. No code fences, no commentary."
        )

        last_error: Optional[str] = None
        for _ in range(self.max_retries):
            messages = []
            if context_messages:
                messages.extend(context_messages)
            messages.extend([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ])
            raw = (self._client.chat(messages=messages) or "").strip()
            xml_str = self._extract_xml(raw)
            ok, err = self._is_valid_xml(xml_str)
            if ok:
                return xml_str
            last_error = err

        raise ValueError(
            f"Plan add interpreter failed to produce valid XML. Last error: {last_error}"
        )

    @staticmethod
    def _extract_xml(text: str) -> str:
        if not text:
            return text
        fence = re.search(r"```(?:xml)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            return fence.group(1).strip()
        return text.strip()

    @staticmethod
    def _is_valid_xml(xml_str: str) -> tuple[bool, Optional[str]]:
        if not xml_str:
            return False, "empty output"
        try:
            ET.fromstring(xml_str)
        except Exception as exc:
            return False, f"invalid xml: {exc}"
        return True, None
