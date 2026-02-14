"""
Plan Builder Client - GPT-based initial plan XML generator.

Takes a user utterance and produces a complete XML plan document
with Meta (Title, Summary) and structural content.

Migrated from Semantic_XPath_Demo/refactor/components/plan_builder/gpt_plan_builder.py.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from common.utils import safe_json_dumps, strip_none
from common.types import TaskState, TreeNode


_BASE_DIR = Path(__file__).resolve().parents[1]
_PROMPT_PATH = _BASE_DIR / "storage" / "prompts" / "planner" / "plan_builder.txt"


class PlanBuilderClient:
    """Generates initial plan XML from a user utterance via GPT."""

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

    def build_initial_state(
        self,
        utterance: str,
        task_id: str,
        version_id: str,
        context_messages: list[dict[str, str]] | None = None,
    ) -> TaskState:
        payload = strip_none({
            "task_id": task_id,
            "version_id": version_id,
            "utterance": utterance,
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
                root_node = self._xml_to_tree(xml_str)
                task_name = self._extract_task_name(xml_str, utterance)
                return TaskState(
                    task_id=task_id,
                    version_id=version_id,
                    schema_version="xml/plan/v1",
                    root=root_node,
                    metadata={"xml": xml_str, "task_name": task_name},
                )
            last_error = err

        raise ValueError(f"Plan builder failed to produce valid XML. Last error: {last_error}")

    # ------------------------------------------------------------------
    # XML helpers
    # ------------------------------------------------------------------

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

    def _xml_to_tree(self, xml_str: str) -> TreeNode:
        root = ET.fromstring(xml_str)
        return self._convert_node(root, "")

    def _convert_node(self, el: ET.Element, path: str) -> TreeNode:
        ident = el.attrib.get("id") or el.attrib.get("index")
        node_id = f"{path}/{el.tag}#{ident}" if ident else f"{path}/{el.tag}"
        text = (el.text or "").strip()
        attrs = dict(el.attrib)
        children = []
        for i, child in enumerate(list(el)):
            child_path = f"{node_id}[{i}]"
            children.append(self._convert_node(child, child_path))
        return TreeNode(
            node_id=node_id,
            type=el.tag,
            text=text,
            attrs=attrs,
            children=children,
        )

    @staticmethod
    def _extract_task_name(xml_str: str, fallback: str) -> str:
        try:
            root = ET.fromstring(xml_str)
            title = root.find("./Meta/Title")
            if title is not None and (title.text or "").strip():
                return (title.text or "").strip()
        except Exception:
            pass
        return fallback.strip() or "New plan"
