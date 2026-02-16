"""Base service for prompt-driven semantic XPath query generation."""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Optional, Protocol, Tuple

from common.utils import safe_json_dumps, strip_none
from domain.semantic_xpath.parsing import (
    NodeTestParseError,
    PredicateParseError,
    QueryParseError,
    QueryParser,
    TokenizeError,
)
from services.query_generation.models import QueryGenerationRequest, QueryGenerationResult


_BASE_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_GRAMMAR_PROMPT_PATH = (
    _BASE_DIR
    / "prompts"
    / "query_generation"
    / "xpath_grammar.txt"
)


class QueryGenerationService(Protocol):
    """Shared interface for semantic XPath query generation services."""

    scope: str

    def generate(self, req: QueryGenerationRequest) -> QueryGenerationResult:
        ...


class BasePromptQueryGenerationService(ABC):
    """Common logic for prompt-based semantic XPath query generators."""

    scope: str = "unknown"

    def __init__(
        self,
        client,
        prompt_path: Path,
        grammar_prompt_path: Optional[Path] = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._prompt_path = prompt_path
        self._grammar_prompt_path = grammar_prompt_path or _DEFAULT_GRAMMAR_PROMPT_PATH
        self.max_retries = max(1, int(max_retries))
        self._system_prompt: Optional[str] = None
        self._parser = QueryParser()

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            with open(self._prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read().strip()
            grammar_ref = ""
            if self._grammar_prompt_path.exists():
                with open(self._grammar_prompt_path, "r", encoding="utf-8") as f:
                    grammar_ref = f.read().strip()

            if grammar_ref:
                self._system_prompt = (
                    f"{base_prompt}\n\n"
                    "Semantic XPath Grammar:\n"
                    f"{grammar_ref}"
                )
            else:
                self._system_prompt = base_prompt
        return self._system_prompt

    def generate(self, req: QueryGenerationRequest) -> QueryGenerationResult:
        utterance = (req.utterance or "").strip()
        if not utterance:
            return QueryGenerationResult(
                xpath_query="",
                parsed_ok=False,
                error="utterance is required.",
            )
        if not isinstance(req.loaded_schema, dict):
            return QueryGenerationResult(
                xpath_query="",
                parsed_ok=False,
                error="loaded_schema must be a dict.",
            )

        prompt = self._build_prompt(req)
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
            query = self._normalize_query(raw)
            if not query:
                last_query = ""
                last_error = "empty query output."
                continue

            parsed_ok, error = self._validate_query(query)
            if parsed_ok:
                return QueryGenerationResult(
                    xpath_query=query,
                    parsed_ok=True,
                    diagnostics={"scope": self.scope},
                )

            last_query = query
            last_error = error or "invalid semantic xpath query."

        return QueryGenerationResult(
            xpath_query=last_query,
            parsed_ok=False,
            error=last_error,
            diagnostics={"scope": self.scope},
        )

    def _build_prompt(self, req: QueryGenerationRequest) -> str:
        payload = strip_none(
            {
                "scope": self.scope,
                "utterance": req.utterance,
                "intent": req.intent,
                "hints": req.hints,
                "schema_summary": self._schema_summary(req.loaded_schema),
            }
        )
        return (
            "Context:\n"
            f"{safe_json_dumps(payload)}\n\n"
            "Return ONLY one semantic XPath query string. "
            "No markdown, no code fences, no commentary."
        )

    def _validate_query(self, query: str) -> Tuple[bool, Optional[str]]:
        try:
            self._parser.parse(query)
            return True, None
        except (QueryParseError, NodeTestParseError, PredicateParseError, TokenizeError, ValueError) as exc:
            return False, str(exc)

    @staticmethod
    def _normalize_query(raw: str) -> str:
        query = raw.strip()
        if query.lower().startswith("output:"):
            query = query[7:].strip()

        if query.startswith("```"):
            lines = query.split("\n")
            if len(lines) >= 2:
                tail_is_fence = lines[-1].strip().startswith("```")
                body = lines[1:-1] if tail_is_fence else lines[1:]
                query = "\n".join(body).strip()

        return query

    @staticmethod
    def _schema_summary(loaded_schema: dict) -> str:
        nodes = loaded_schema.get("nodes")
        if isinstance(nodes, dict):
            lines = []
            for node_name in sorted(nodes.keys()):
                cfg = nodes.get(node_name) or {}
                fields = cfg.get("fields") or []
                children = cfg.get("children") or []
                lines.append(
                    f"- {node_name}: fields={list(fields)}, children={list(children)}"
                )
            return "\n".join(lines)
        return safe_json_dumps(loaded_schema)
