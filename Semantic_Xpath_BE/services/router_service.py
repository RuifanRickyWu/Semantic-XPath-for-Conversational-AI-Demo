"""
Router Service - GPT-based intent classifier for user utterances.

Classifies each utterance into one of the supported intents
(CHAT, PLAN_CREATE, PLAN_QA, PLAN_EDIT, REGISTRY_QA, REGISTRY_EDIT)
and decides whether a registry operation is required.

Migrated from clients/router_client.py.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from common.utils import safe_json_dumps, strip_none
from common.types import RouteInput, RouteResult, RoutingDecision


_BASE_DIR = Path(__file__).resolve().parents[1]
_PROMPT_PATH = _BASE_DIR / "storage" / "prompts" / "router" / "router.txt"

_VALID_INTENTS = {
    "CHAT", "PLAN_QA", "PLAN_EDIT", "PLAN_CREATE", "REGISTRY_QA", "REGISTRY_EDIT",
}


class RouterService:
    """GPT-based intent router."""

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

    def route(self, route_input: RouteInput) -> RouteResult:
        fallback_message = "One moment, please try again."
        utterance = (route_input.utterance or "").strip()

        if not utterance:
            routing = RoutingDecision(
                intent="CHAT",
                registry_op=0,
                intent_label="EMPTY",
                confidence=0.0,
                requires_clarification=True,
                clarification_question=fallback_message,
            )
            return RouteResult(routing=routing, effective_utterance=utterance)

        payload = {
            "utterance": utterance,
            "session": strip_none(asdict(route_input.session)),
        }
        prompt = f"Input:\n{safe_json_dumps(payload)}"

        for _attempt in range(self.max_retries):
            messages = []
            if route_input.context_messages:
                messages.extend(route_input.context_messages)
            messages.extend([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ])
            raw = (self._client.chat(messages=messages) or "").strip()
            try:
                parsed = json.loads(raw)
                routing = self._from_parsed(parsed)
                return self._wrap_result(utterance, routing)
            except (ValueError, json.JSONDecodeError):
                continue

        routing = RoutingDecision(
            intent="CHAT",
            registry_op=0,
            intent_label="RETRY_EXHAUSTED",
            confidence=0.0,
            requires_clarification=True,
            clarification_question=fallback_message,
        )
        return RouteResult(routing=routing, effective_utterance=utterance)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _from_parsed(self, parsed: dict) -> RoutingDecision:
        intent = self._parse_intent(parsed.get("intent"))
        registry_op = self._coerce_bit(parsed.get("registry_op"))

        confidence = parsed.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None

        requires_clarification = parsed.get("requires_clarification")
        rc = requires_clarification if isinstance(requires_clarification, bool) else False

        clarification_question = parsed.get("clarification_question")
        if rc and not clarification_question:
            clarification_question = "Could you clarify what you want to do?"

        reformulated = parsed.get("reformulated_utterance")
        if isinstance(reformulated, str):
            reformulated = reformulated.strip() or None
        else:
            reformulated = None

        return RoutingDecision(
            intent=intent,
            registry_op=registry_op,
            intent_label=parsed.get("intent_label") or intent,
            confidence=confidence,
            requires_clarification=rc,
            clarification_question=clarification_question,
            reformulated_utterance=reformulated,
        )

    @staticmethod
    def _wrap_result(utterance: str, routing: RoutingDecision) -> RouteResult:
        reformulated = routing.reformulated_utterance or ""
        if reformulated and reformulated.strip() and reformulated.strip() != utterance:
            return RouteResult(
                routing=routing,
                effective_utterance=reformulated.strip(),
                original_utterance=utterance,
            )
        return RouteResult(routing=routing, effective_utterance=utterance)

    @staticmethod
    def _coerce_bit(value) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        try:
            return 1 if int(value) == 1 else 0
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_intent(value) -> str:
        if not value:
            return "CHAT"
        intent = str(value).strip().upper()
        if intent in _VALID_INTENTS:
            return intent
        return "CHAT"
