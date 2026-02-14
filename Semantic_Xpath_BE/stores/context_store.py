"""
Context Store - In-memory conversation context management.

Manages per-session conversation history window, focus memory, intent memory,
and session notes. Provides formatted message lists for LLM context injection.

Migrated from Semantic_XPath_Demo/refactor/components/context_recorder/context_recorder.py.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional

import yaml

from common.types import (
    ConversationContext,
    ContextTurn,
    FocusLabels,
    FocusMemory,
    IntentMemory,
)


@dataclass
class _SessionContext:
    window: Deque[ContextTurn] = field(default_factory=deque)
    focus: FocusMemory = field(default_factory=FocusMemory)
    focus_labels: FocusLabels = field(default_factory=FocusLabels)
    intent_memory: IntentMemory = field(default_factory=IntentMemory)
    session_notes: Optional[str] = None


class ContextStore:
    """In-memory conversation context recorder and provider."""

    def __init__(
        self,
        window_size: Optional[int] = None,
        max_message_chars: int = 600,
        memory_level: Optional[str] = None,
        config_path: Optional[str | Path] = None,
    ) -> None:
        cfg = self._load_config(config_path)
        self.window_size = max(
            1, int(self._resolve_window_size(window_size, memory_level, cfg))
        )
        self.max_message_chars = max(80, int(max_message_chars))
        self._sessions: Dict[str, _SessionContext] = {}

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_context(self, session_id: str) -> ConversationContext:
        session = self._sessions.get(session_id)
        if session is None:
            return ConversationContext()
        last_turn = session.window[-1] if session.window else None
        return ConversationContext(
            last_user=last_turn.user if last_turn else None,
            last_assistant=last_turn.assistant if last_turn else None,
            window=list(session.window),
            focus=FocusMemory(
                last_task_reference=session.focus.last_task_reference,
                last_version_reference=session.focus.last_version_reference,
                last_target_node_id=session.focus.last_target_node_id,
                last_action=session.focus.last_action,
            ),
            session_notes=session.session_notes,
            intent_memory=IntentMemory(
                last_intent=session.intent_memory.last_intent,
                last_intent_label=session.intent_memory.last_intent_label,
                last_user_utterance=session.intent_memory.last_user_utterance,
                awaiting_clarification=session.intent_memory.awaiting_clarification,
                clarification_question=session.intent_memory.clarification_question,
            ),
        )

    def get_messages(self, session_id: str) -> List[Dict[str, str]]:
        """Build a flat message list suitable for LLM context injection."""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        messages: List[Dict[str, str]] = []
        for turn in session.window:
            if turn.user:
                messages.append(
                    {"role": "user", "content": self._truncate(turn.user)}
                )
            if turn.assistant:
                messages.append(
                    {"role": "assistant", "content": self._truncate(turn.assistant)}
                )

        memory_lines = self._build_memory_lines(session)
        if memory_lines:
            memory_text = " ".join(memory_lines)
            messages.append({"role": "system", "content": f"MEMORY: {memory_text}"})
        return messages

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def record_turn(
        self,
        session_id: str,
        user_utterance: str,
        assistant_message: str,
        timestamp: str | None = None,
    ) -> None:
        session = self._sessions.setdefault(session_id, _SessionContext())
        session.window.append(
            ContextTurn(
                user=user_utterance or "",
                assistant=assistant_message or "",
                timestamp=timestamp,
            )
        )
        while len(session.window) > self.window_size:
            session.window.popleft()

    def update_intent_memory(self, session_id: str, patch: IntentMemory) -> None:
        session = self._sessions.setdefault(session_id, _SessionContext())
        if patch.last_intent is not None:
            session.intent_memory.last_intent = patch.last_intent
        if patch.last_intent_label is not None:
            session.intent_memory.last_intent_label = patch.last_intent_label
        if patch.last_user_utterance is not None:
            session.intent_memory.last_user_utterance = patch.last_user_utterance
        if patch.awaiting_clarification is not None:
            session.intent_memory.awaiting_clarification = patch.awaiting_clarification
        if patch.clarification_question is not None:
            session.intent_memory.clarification_question = patch.clarification_question

    def update_focus_labels(self, session_id: str, patch: FocusLabels) -> None:
        session = self._sessions.setdefault(session_id, _SessionContext())
        if patch.last_task_label is not None:
            session.focus_labels.last_task_label = patch.last_task_label
        if patch.last_version_label is not None:
            session.focus_labels.last_version_label = patch.last_version_label
        if patch.last_target_label is not None:
            session.focus_labels.last_target_label = patch.last_target_label
        if patch.last_action is not None:
            session.focus_labels.last_action = patch.last_action

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_memory_lines(self, session: _SessionContext) -> List[str]:
        lines: List[str] = []
        if session.focus_labels.last_task_label:
            lines.append(f"Last task label: {session.focus_labels.last_task_label}.")
        if session.focus_labels.last_version_label:
            lines.append(f"Last version label: {session.focus_labels.last_version_label}.")
        if session.focus_labels.last_target_label:
            lines.append(f"Last target label: {session.focus_labels.last_target_label}.")
        if session.focus_labels.last_action:
            lines.append(f"Last action: {session.focus_labels.last_action}.")
        if session.intent_memory.last_intent:
            lines.append(f"Last intent: {session.intent_memory.last_intent}.")
        if session.intent_memory.last_intent_label:
            lines.append(f"Last intent label: {session.intent_memory.last_intent_label}.")
        if session.intent_memory.last_user_utterance:
            lines.append(f"Last user utterance: {session.intent_memory.last_user_utterance}.")
        if session.intent_memory.awaiting_clarification is not None:
            flag = "yes" if session.intent_memory.awaiting_clarification else "no"
            lines.append(f"Awaiting clarification: {flag}.")
        if session.intent_memory.clarification_question:
            lines.append(f"Clarification question asked: {session.intent_memory.clarification_question}.")
        if session.session_notes:
            lines.append(f"Session notes: {session.session_notes}.")
        return lines

    def _truncate(self, text: str, limit: Optional[int] = None) -> str:
        if text is None:
            return ""
        limit = limit or self.max_message_chars
        clean = str(text).replace("\r", " ").replace("\n", " ").strip()
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

    def _load_config(self, config_path: Optional[str | Path]) -> dict:
        if config_path is None:
            config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        config_path = Path(config_path)
        if not config_path.exists():
            return {}
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _resolve_window_size(
        self, window_size: Optional[int], memory_level: Optional[str], cfg: dict
    ) -> int:
        if window_size is not None:
            return int(window_size)
        context_cfg = cfg.get("context", {}) if isinstance(cfg, dict) else {}
        level = (memory_level or context_cfg.get("memory_level") or "medium").lower()
        default_sizes = {"low": 2, "medium": 4, "high": 6}
        sizes = context_cfg.get("window_sizes", {}) if isinstance(context_cfg, dict) else {}
        size = sizes.get(level) if isinstance(sizes, dict) else None
        if size is None:
            size = default_sizes.get(level, 4)
        return int(size)
