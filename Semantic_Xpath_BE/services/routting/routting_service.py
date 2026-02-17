"""
Routting Service - GPT-based intent classifier for user utterances.

Classifies each utterance into one of the supported intents
(CHAT, PLAN_CREATE, PLAN_QA, PLAN_ADD, PLAN_UPDATE, PLAN_DELETE, REGISTRY_QA, REGISTRY_EDIT, REGISTRY_DELETE)
and decides whether a registry operation is required.

Migrated from clients/routting_client.py.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from common.utils import safe_json_dumps, strip_none
from common.types import IntentRequest, RouteInput, RouteResult, RoutingDecision


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_PATH = _BASE_DIR / "prompts" / "routting" / "routting.txt"

_VALID_INTENTS = {
    "CHAT", "PLAN_QA", "PLAN_ADD", "PLAN_UPDATE", "PLAN_DELETE", "PLAN_CREATE", "REGISTRY_QA", "REGISTRY_EDIT", "REGISTRY_DELETE",
}


class RouttingService:
    """GPT-based intent routting classifier."""

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
                intent_requests=[IntentRequest(intent="CHAT", request=utterance)],
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
                routing = self._from_parsed(parsed, utterance=utterance)
                return self._wrap_result(utterance, routing)
            except (ValueError, json.JSONDecodeError):
                continue

        routing = RoutingDecision(
            intent_requests=[IntentRequest(intent="CHAT", request=utterance)],
            intent_label="RETRY_EXHAUSTED",
            confidence=0.0,
            requires_clarification=True,
            clarification_question=fallback_message,
        )
        return RouteResult(routing=routing, effective_utterance=utterance)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _from_parsed(self, parsed: dict, utterance: str = "") -> RoutingDecision:
        raw_ir = parsed.get("intent_requests")
        if not isinstance(raw_ir, list) or not raw_ir:
            raise ValueError("intent_requests is required and must be a non-empty array")

        intent_requests = []
        for item in raw_ir:
            if not isinstance(item, dict):
                continue
            intent = self._parse_intent(item.get("intent"))
            req = item.get("request")
            req = req.strip() if isinstance(req, str) else ""
            if not req:
                req = utterance
            intent_requests.append(IntentRequest(intent=intent, request=req))

        if not intent_requests:
            raise ValueError("intent_requests must contain at least one item")

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

        return RoutingDecision(
            intent_requests=intent_requests,
            intent_label=parsed.get("intent_label") or intent_requests[0].intent,
            confidence=confidence,
            requires_clarification=rc,
            clarification_question=clarification_question,
        )

    @staticmethod
    def _wrap_result(utterance: str, routing: RoutingDecision) -> RouteResult:
        if routing.intent_requests and len(routing.intent_requests) == 1:
            r = routing.intent_requests[0].request.strip()
            if r != utterance:
                return RouteResult(
                    routing=routing,
                    effective_utterance=r,
                    original_utterance=utterance,
                )
        return RouteResult(routing=routing, effective_utterance=utterance)

    @staticmethod
    def _parse_intent(value) -> str:
        if not value:
            return "CHAT"
        intent = str(value).strip().upper()
        if intent in _VALID_INTENTS:
            return intent
        return "CHAT"
