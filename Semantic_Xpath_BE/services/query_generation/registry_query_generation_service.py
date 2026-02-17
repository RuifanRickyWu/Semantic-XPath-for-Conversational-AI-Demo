"""Registry-level semantic XPath query generation service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from services.query_generation.base_query_generation_service import (
    BasePromptQueryGenerationService,
)
from services.query_generation.models import QueryGenerationRequest, QueryGenerationResult


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_PATH = (
    _BASE_DIR
    / "prompts"
    / "query_generation"
    / "registry_query_generator.txt"
)

_TARGET_RE = re.compile(r"TARGET:\s*(tasks|versions)", re.IGNORECASE)
_QUERY_RE = re.compile(r"QUERY:\s*(.+)", re.IGNORECASE | re.DOTALL)


def _parse_target_and_query(raw: str) -> Tuple[Optional[str], str]:
    """Parse TARGET and QUERY from raw LLM output. Returns (target, query)."""
    raw = raw.strip()
    target = None
    query = ""
    for line in raw.splitlines():
        line = line.strip()
        m = _TARGET_RE.match(line)
        if m:
            target = m.group(1).lower()
            continue
        m = _QUERY_RE.match(line)
        if m:
            query = m.group(1).strip()
            break
    return target, query


class RegistryQueryGenerationService(BasePromptQueryGenerationService):
    """Generates semantic XPath queries over registry XML with TARGET (tasks|versions)."""

    scope: str = "registry"

    def __init__(
        self,
        client,
        prompt_path: Optional[Path] = None,
        max_retries: int = 3,
    ) -> None:
        super().__init__(
            client=client,
            prompt_path=prompt_path or _PROMPT_PATH,
            max_retries=max_retries,
        )

    def _build_prompt(self, req: QueryGenerationRequest) -> str:
        from common.utils import safe_json_dumps, strip_none

        payload = strip_none(
            {
                "scope": self.scope,
                "utterance": req.utterance,
                "intent": req.intent,
                "hints": req.hints,
                "active_task_id": req.active_task_id,
                "schema_summary": self._schema_summary(req.loaded_schema),
            }
        )
        return (
            "Context:\n"
            f"{safe_json_dumps(payload)}\n\n"
            "Return TARGET and QUERY as specified in the system prompt."
        )

    def generate(self, req: QueryGenerationRequest) -> QueryGenerationResult:
        utterance = (req.utterance or "").strip()
        if not utterance:
            return QueryGenerationResult(
                xpath_query="",
                parsed_ok=False,
                error="utterance is required.",
                diagnostics={"scope": self.scope},
            )
        if not isinstance(req.loaded_schema, dict):
            return QueryGenerationResult(
                xpath_query="",
                parsed_ok=False,
                error="loaded_schema must be a dict.",
                diagnostics={"scope": self.scope},
            )

        prompt = self._build_prompt(req)
        last_target: Optional[str] = None
        last_query = ""
        last_error = "query generation failed."

        for _ in range(self.max_retries):
            messages = []
            if req.context_messages:
                messages.extend(req.context_messages)
            messages.extend(
                [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
            raw = (self._client.chat(messages=messages) or "").strip()
            target, query = _parse_target_and_query(raw)

            if not query:
                last_query = ""
                last_error = "empty or unparseable query output."
                continue

            parsed_ok, error = self._validate_query(query)
            if parsed_ok:
                valid_target = target if target in ("tasks", "versions") else "tasks"
                return QueryGenerationResult(
                    xpath_query=query,
                    parsed_ok=True,
                    diagnostics={"scope": self.scope},
                    registry_target=valid_target,
                )

            last_target = target
            last_query = query
            last_error = error or "invalid semantic xpath query."

        return QueryGenerationResult(
            xpath_query=last_query,
            parsed_ok=False,
            error=last_error,
            diagnostics={"scope": self.scope},
            registry_target=last_target if last_target in ("tasks", "versions") else None,
        )
