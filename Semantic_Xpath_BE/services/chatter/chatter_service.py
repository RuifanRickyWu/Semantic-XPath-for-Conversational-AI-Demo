"""
Chatter Service - GPT-based response realizer.

Dispatches to intent-specific chatters to generate user-facing responses:
- CHAT: conversational reply
- PLAN_CREATE: plan summary + next-step question
- Clarification: returns the clarification question directly
- Default: placeholder for unimplemented intents

Migrated from clients/chatter_client.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from common.utils import safe_json_dumps, strip_none
from common.types import RealizeRequest


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_CHAT = _BASE_DIR / "storage" / "prompts" / "chatter" / "chatter_chat.txt"
_PROMPT_PLAN_CREATE = _BASE_DIR / "storage" / "prompts" / "chatter" / "chatter_plan_create.txt"
_PROMPT_DEFAULT = _BASE_DIR / "storage" / "prompts" / "chatter" / "chatter_default.txt"


# ---------------------------------------------------------------------------
# Base prompt chatter
# ---------------------------------------------------------------------------

class _BasePromptChatter:
    def __init__(self, client, prompt_path: Optional[Path] = None, max_retries: int = 3) -> None:
        self._client = client
        self._prompt_path = prompt_path
        self.max_retries = max(1, int(max_retries))
        self._system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            if self._prompt_path is None:
                return ""
            with open(self._prompt_path, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        return self._system_prompt or ""

    def realize(self, req: RealizeRequest) -> str:
        fallback_message = "One moment -- please try again."
        payload = self._build_payload(req)
        prompt = f"Context:\n{safe_json_dumps(payload)}\n\nWrite the assistant response only."

        for _ in range(self.max_retries):
            messages = []
            if req.context_messages:
                messages.extend(req.context_messages)
            messages.extend([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ])
            content = (self._client.chat(messages=messages) or "").strip()
            if content:
                return content
        return fallback_message

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "routing": req.routing,
            "session": req.session,
            "conversation_context": req.conversation_context,
            "registry_context": req.registry_context,
            "state_context": req.state_context,
            "constraints": req.constraints or {},
        })


# ---------------------------------------------------------------------------
# Intent-specific chatters
# ---------------------------------------------------------------------------

class _ChatChatter(_BasePromptChatter):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_CHAT, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "conversation_context": req.conversation_context,
        })


class _PlanCreateChatter(_BasePromptChatter):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_PLAN_CREATE, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        state_ctx = req.state_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "conversation_context": req.conversation_context,
            "task_name": state_ctx.get("task_name"),
            "task_xml": state_ctx.get("task_xml"),
        })


class _ClarificationChatter:
    def realize(self, req: RealizeRequest) -> str:
        for ctx in (req.registry_context, req.state_context):
            if isinstance(ctx, dict):
                question = ctx.get("clarification_question")
                if isinstance(question, str) and question.strip():
                    return question.strip()
        return "One moment -- please try again."


class _DefaultChatter(_BasePromptChatter):
    def __init__(self, client, max_retries: int = 1) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_DEFAULT, max_retries=max_retries)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class ChatterService:
    """Dispatches to the appropriate intent-specific chatter for response generation."""

    def __init__(self, client, max_retries: int = 3) -> None:
        self._client = client
        self._max_retries = max(1, int(max_retries))
        self._chat = _ChatChatter(client=self._client, max_retries=self._max_retries)
        self._plan_create = _PlanCreateChatter(client=self._client, max_retries=self._max_retries)
        self._clarify = _ClarificationChatter()
        self._default = _DefaultChatter(client=self._client, max_retries=1)

    def realize(self, req: RealizeRequest) -> str:
        if self._has_clarification(req):
            return self._clarify.realize(req)
        if req.routing.intent == "CHAT":
            return self._chat.realize(req)
        if req.routing.intent == "PLAN_CREATE":
            return self._plan_create.realize(req)
        return self._default.realize(req)

    @staticmethod
    def _has_clarification(req: RealizeRequest) -> bool:
        for ctx in (req.registry_context, req.state_context):
            if isinstance(ctx, dict) and ctx.get("clarification_question"):
                return True
        return False
