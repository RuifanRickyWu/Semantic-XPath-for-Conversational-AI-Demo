"""
Intent Router - routes user input to chitchat, plan generation, or CRUD pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from client import get_default_client
from pipeline.semantic_xpath_pipeline.semantic_xpath_pipeline import SemanticXPathPipeline
from pipeline_execution.cold_start import TaskBootstrapper
from pipeline_execution.cold_start.user_facing_formatter import format_user_facing


_BASE_DIR = Path(__file__).resolve().parents[1]
_PROMPT_PATH = _BASE_DIR / "storage" / "prompts" / "intent_router.txt"


class IntentRouter:
    def __init__(
        self,
        pipeline: Optional[SemanticXPathPipeline] = None,
        bootstrapper: Optional[TaskBootstrapper] = None,
        client=None,
    ):
        self.pipeline = pipeline or SemanticXPathPipeline()
        self.bootstrapper = bootstrapper or TaskBootstrapper()
        self._client = client or get_default_client()
        self._system_prompt = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        return self._system_prompt

    def route(self, user_input: str, decision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        user_input = (user_input or "").strip()
        if not user_input:
            return {"success": False, "mode": "error", "error": "Empty input"}

        decision = decision or self.classify(user_input)
        intent = (decision.get("intent") or "").upper()

        if intent == "CHITCHAT":
            response = decision.get("chitchat_response") or ""
            if not response:
                response = "Got it. How can I help you today?"
            return {
                "success": True,
                "mode": "chitchat",
                "response": response,
            }

        if intent == "PLAN":
            plan_request = decision.get("plan_request") or user_input
            result = self.bootstrapper.generate(plan_request, save=True, activate=False)
            user_facing = result.get("user_facing") if isinstance(result, dict) else None
            response = format_user_facing(user_facing) if user_facing else ""
            return {
                "success": bool(result.get("success")) if isinstance(result, dict) else False,
                "mode": "plan",
                "response": response,
                "user_facing": user_facing,
                "result": result,
            }

        # Default: CRUD pipeline
        result = self.pipeline.process_request(user_input)
        if isinstance(result, dict):
            result["mode"] = "crud"
        return result

    def classify(self, user_input: str) -> Dict[str, Any]:
        prompt = f"User: {user_input}"
        result = self._client.complete_with_usage(
            prompt,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=512,
        )
        raw = (result.content or "").strip()

        try:
            return self._extract_json(raw)
        except ValueError:
            return {"intent": "CRUD", "chitchat_response": "", "plan_request": ""}

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            raise ValueError("No JSON object found")
        json_str = text[json_start:json_end]
        return json.loads(json_str)
