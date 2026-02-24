"""
Chatting Service - GPT-based response realizer.

Dispatches to intent-specific chatting handlers to generate user-facing responses:
- CHAT: conversational reply
- PLAN_CREATE: plan summary + next-step question
- PLAN_QA: answer plan content questions using retrieved results
- PLAN_DELETE: confirm what was removed from the plan
- PLAN_UPDATE: confirm what was updated in the plan
- PLAN_ADD: confirm what was added to the plan
- REGISTRY_QA: present tasks/versions list with natural lead-in
- REGISTRY_EDIT: confirm task/version switch
- REGISTRY_DELETE: confirm deletion or explain if not yet supported
- Clarification: returns the clarification question directly
- Default: placeholder for unimplemented intents

Migrated from clients/chatting_client.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from common.utils import safe_json_dumps, strip_none
from common.types import RealizeRequest


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_CHAT = _BASE_DIR / "prompts" / "chatting" / "chatting_chat.txt"
_PROMPT_PLAN_CREATE = _BASE_DIR / "prompts" / "chatting" / "chatting_plan_create.txt"
_PROMPT_PLAN_QA = _BASE_DIR / "prompts" / "chatting" / "chatting_plan_qa.txt"
_PROMPT_PLAN_DELETE = _BASE_DIR / "prompts" / "chatting" / "chatting_plan_delete.txt"
_PROMPT_PLAN_UPDATE = _BASE_DIR / "prompts" / "chatting" / "chatting_plan_update.txt"
_PROMPT_PLAN_ADD = _BASE_DIR / "prompts" / "chatting" / "chatting_plan_add.txt"
_PROMPT_REGISTRY_QA = _BASE_DIR / "prompts" / "chatting" / "chatting_registry_qa.txt"
_PROMPT_REGISTRY_EDIT = _BASE_DIR / "prompts" / "chatting" / "chatting_registry_edit.txt"
_PROMPT_REGISTRY_DELETE = _BASE_DIR / "prompts" / "chatting" / "chatting_registry_delete.txt"
_PROMPT_DEFAULT = _BASE_DIR / "prompts" / "chatting" / "chatting_default.txt"


# ---------------------------------------------------------------------------
# Base prompt chatting
# ---------------------------------------------------------------------------

class _BasePromptChatting:
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
            "intent_results": req.intent_results,
        })


# ---------------------------------------------------------------------------
# Intent-specific chatting handlers
# ---------------------------------------------------------------------------

class _ChatChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_CHAT, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "conversation_context": req.conversation_context,
        })


class _PlanCreateChatting(_BasePromptChatting):
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


class _PlanQAChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_PLAN_QA, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        state_ctx = req.state_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "state_context": {
                "generation_hint": state_ctx.get("generation_hint"),
                "per_node_detail": state_ctx.get("per_node_detail"),
                "scoring_trace": state_ctx.get("scoring_trace"),
                "xpath_query": state_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
            "constraints": req.constraints,
        })


class _PlanDeleteChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_PLAN_DELETE, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        state_ctx = req.state_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "state_context": {
                "generation_hint": state_ctx.get("generation_hint"),
                "per_node_detail": state_ctx.get("per_node_detail"),
                "scoring_trace": state_ctx.get("scoring_trace"),
                "xpath_query": state_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
            "constraints": req.constraints,
        })


class _PlanUpdateChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_PLAN_UPDATE, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        state_ctx = req.state_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "state_context": {
                "generation_hint": state_ctx.get("generation_hint"),
                "per_node_detail": state_ctx.get("per_node_detail"),
                "scoring_trace": state_ctx.get("scoring_trace"),
                "xpath_query": state_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
            "constraints": req.constraints,
        })


class _PlanAddChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_PLAN_ADD, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        state_ctx = req.state_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "state_context": {
                "generation_hint": state_ctx.get("generation_hint"),
                "per_node_detail": state_ctx.get("per_node_detail"),
                "scoring_trace": state_ctx.get("scoring_trace"),
                "xpath_query": state_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
            "constraints": req.constraints,
        })


class _RegistryQAChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_REGISTRY_QA, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        registry_ctx = req.registry_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "registry_context": {
                "generation_hint": registry_ctx.get("generation_hint"),
                "per_node_detail": registry_ctx.get("per_node_detail"),
                "scoring_trace": registry_ctx.get("scoring_trace"),
                "xpath_query": registry_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
        })


class _RegistryEditChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_REGISTRY_EDIT, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        registry_ctx = req.registry_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "registry_context": {
                "generation_hint": registry_ctx.get("generation_hint"),
                "per_node_detail": registry_ctx.get("per_node_detail"),
                "scoring_trace": registry_ctx.get("scoring_trace"),
                "xpath_query": registry_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
        })


class _RegistryDeleteChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 3) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_REGISTRY_DELETE, max_retries=max_retries)

    def _build_payload(self, req: RealizeRequest) -> Dict[str, Any]:
        registry_ctx = req.registry_context or {}
        return strip_none({
            "utterance": req.utterance,
            "original_utterance": req.original_utterance,
            "registry_context": {
                "generation_hint": registry_ctx.get("generation_hint"),
                "per_node_detail": registry_ctx.get("per_node_detail"),
                "scoring_trace": registry_ctx.get("scoring_trace"),
                "xpath_query": registry_ctx.get("xpath_query"),
            },
            "session": req.session,
            "conversation_context": req.conversation_context,
        })


class _ClarificationChatting:
    def realize(self, req: RealizeRequest) -> str:
        for ctx in (req.registry_context, req.state_context):
            if isinstance(ctx, dict):
                question = ctx.get("clarification_question")
                if isinstance(question, str) and question.strip():
                    return question.strip()
        return "One moment -- please try again."


class _DefaultChatting(_BasePromptChatting):
    def __init__(self, client, max_retries: int = 1) -> None:
        super().__init__(client=client, prompt_path=_PROMPT_DEFAULT, max_retries=max_retries)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class ChattingService:
    """Dispatches to the appropriate intent-specific chatting handler for response generation."""

    def __init__(self, client, max_retries: int = 3) -> None:
        self._client = client
        self._max_retries = max(1, int(max_retries))
        self._chat = _ChatChatting(client=self._client, max_retries=self._max_retries)
        self._plan_create = _PlanCreateChatting(client=self._client, max_retries=self._max_retries)
        self._plan_qa = _PlanQAChatting(client=self._client, max_retries=self._max_retries)
        self._plan_delete = _PlanDeleteChatting(client=self._client, max_retries=self._max_retries)
        self._plan_update = _PlanUpdateChatting(client=self._client, max_retries=self._max_retries)
        self._plan_add = _PlanAddChatting(client=self._client, max_retries=self._max_retries)
        self._registry_qa = _RegistryQAChatting(client=self._client, max_retries=self._max_retries)
        self._registry_edit = _RegistryEditChatting(client=self._client, max_retries=self._max_retries)
        self._registry_delete = _RegistryDeleteChatting(client=self._client, max_retries=self._max_retries)
        self._clarify = _ClarificationChatting()
        self._default = _DefaultChatting(client=self._client, max_retries=1)

    def realize(self, req: RealizeRequest) -> str:
        if self._has_clarification(req):
            return self._clarify.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "CHAT":
            return self._chat.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "PLAN_CREATE":
            return self._plan_create.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "PLAN_QA":
            return self._plan_qa.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "PLAN_DELETE":
            return self._plan_delete.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "PLAN_UPDATE":
            return self._plan_update.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "PLAN_ADD":
            return self._plan_add.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "REGISTRY_QA":
            return self._registry_qa.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "REGISTRY_EDIT":
            return self._registry_edit.realize(req)
        if len(req.routing.intents) == 1 and req.routing.intent == "REGISTRY_DELETE":
            return self._registry_delete.realize(req)
        return self._default.realize(req)

    @staticmethod
    def _has_clarification(req: RealizeRequest) -> bool:
        for ctx in (req.registry_context, req.state_context):
            if isinstance(ctx, dict) and ctx.get("clarification_question"):
                return True
        return False
