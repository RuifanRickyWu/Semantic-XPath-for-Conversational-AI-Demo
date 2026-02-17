"""
Semantic XPath Result Verifier - LLM-based verification of retrieved nodes.

Given execution result and request, verifies which nodes are relevant.
Lenient by default; rejects only when there is a clear reason.
Lenient by default; rejects only when there is a clear reason.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.semantic_xpath.execution import ExecutionResult
from services.result_verification.models import VerificationResult


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_PATH = _BASE_DIR / "prompts" / "result_verification" / "result_verifier.txt"


def _summarize_node(entry: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Build a compact summary of a per_node entry for the LLM."""
    node = entry.get("node") or {}
    tree_path_display = entry.get("tree_path_display") or entry.get("tree_path") or []
    attrs = node.get("attributes") or {}
    path_str = ""
    if tree_path_display:
        segs = tree_path_display[:5]
        if segs and isinstance(segs[0], dict):
            parts = [
                seg.get("type", "?") + "[" + str(seg.get("attributes", {})) + "]"
                for seg in segs
            ]
            path_str = " -> ".join(parts)
        else:
            path_str = str(segs)
    return {
        "index": index,
        "type": node.get("type", "?"),
        "attributes": attrs,
        "tree_path_summary": path_str[:120],
        "score": entry.get("score"),
    }


def _parse_llm_response(raw: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, tolerating markdown fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


class SemanticXPathResultVerifier:
    """LLM-based verifier for semantic XPath execution results."""

    def __init__(
        self,
        client: Any,
        prompt_path: Optional[Path] = None,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._prompt_path = prompt_path or _PROMPT_PATH
        self._max_retries = max(1, max_retries)
        self._system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            if self._prompt_path.exists():
                with open(self._prompt_path, "r", encoding="utf-8") as f:
                    self._system_prompt = f.read()
            else:
                self._system_prompt = ""
        return self._system_prompt or ""

    def verify(
        self,
        exec_result: ExecutionResult,
        request: str,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify which retrieved nodes are relevant to the request.
        Lenient by default; only rejects when there is a clear reason.
        """
        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        if not per_node:
            return VerificationResult(verified_nodes=[], rejected_nodes=[])

        nodes_summary = [
            _summarize_node(entry, i) for i, entry in enumerate(per_node)
        ]

        payload = {
            "request": request,
            "intent": intent or "UNKNOWN",
            "nodes": nodes_summary,
            "context": context or {},
        }

        prompt = (
            "Context:\n"
            + json.dumps(payload, indent=2, ensure_ascii=False)
            + "\n\nReturn the verification JSON as specified in the system prompt."
        )

        for _ in range(self._max_retries):
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
            raw = (self._client.chat(messages=messages) or "").strip()
            if not raw:
                continue

            parsed = _parse_llm_response(raw)
            verified_indices = parsed.get("verified_indices")
            rejections = parsed.get("rejections") or []

            if not isinstance(verified_indices, list):
                verified_indices = list(range(len(per_node)))

            rejected_set = {r.get("index") for r in rejections if isinstance(r, dict)}
            rejection_reasons = {r.get("index"): r.get("reason", "") for r in rejections if isinstance(r, dict)}

            verified_nodes: List[Dict[str, Any]] = []
            rejected_nodes: List[Dict[str, Any]] = []

            for i, entry in enumerate(per_node):
                entry_copy = dict(entry)
                if i in rejected_set:
                    entry_copy["reject_reason"] = rejection_reasons.get(i, "Rejected by verifier")
                    rejected_nodes.append(entry_copy)
                elif i in verified_indices:
                    verified_nodes.append(entry_copy)

            if not verified_nodes and not rejected_nodes:
                verified_nodes = list(per_node)

            return VerificationResult(
                verified_nodes=verified_nodes,
                rejected_nodes=rejected_nodes,
            )

        return VerificationResult(verified_nodes=list(per_node), rejected_nodes=[])
