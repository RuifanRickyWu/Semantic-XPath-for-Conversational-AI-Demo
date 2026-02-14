"""
Tests for ContextStore.

Adapted from Semantic_XPath_Demo/refactor/tests/test_context_recorder.py.
Tests window truncation, message truncation, focus/intent memory, and session notes.
"""

from __future__ import annotations

import pytest

from stores.context_store import ContextStore
from common.types import FocusLabels, FocusMemory, IntentMemory


def test_window_truncation():
    svc = ContextStore(window_size=2, max_message_chars=100)
    svc.record_turn("s1", "u1", "a1")
    svc.record_turn("s1", "u2", "a2")
    svc.record_turn("s1", "u3", "a3")
    ctx = svc.get_context("s1")
    assert ctx.window is not None and len(ctx.window) == 2
    assert ctx.window[-1].user == "u3"


def test_message_truncation():
    svc = ContextStore(window_size=1, max_message_chars=100)
    long_text = "a" * 150
    svc.record_turn("s2", long_text, long_text)
    msgs = svc.get_messages("s2")
    assert len(msgs) >= 2, "should include user and assistant messages"
    user_msg = msgs[0]["content"]
    assert len(user_msg) <= 100
    assert user_msg.endswith("...")


def test_focus_and_intent_memory_sentence():
    svc = ContextStore(window_size=1, max_message_chars=120)
    svc.update_focus_labels(
        "s3",
        FocusLabels(last_task_label="Toronto trip", last_action="plan_edit"),
    )
    svc.update_intent_memory(
        "s3",
        IntentMemory(
            last_intent="PLAN_EDIT",
            last_intent_label="edit_plan",
            last_user_utterance="Add a museum",
            awaiting_clarification=True,
            clarification_question="Which day?",
        ),
    )
    msgs = svc.get_messages("s3")
    assert msgs, "messages should not be empty"
    memory_msg = msgs[-1]
    assert memory_msg["role"] == "system"
    content = memory_msg["content"]
    assert "MEMORY:" in content
    assert "Last task label: Toronto trip." in content
    assert "Last action: plan_edit." in content
    assert "Last intent: PLAN_EDIT." in content
    assert "Awaiting clarification: yes." in content
    assert "Clarification question asked: Which day?." in content


def test_intent_memory_stored_and_retrieved():
    svc = ContextStore()
    svc.update_intent_memory(
        "s4",
        IntentMemory(
            last_intent="CHAT",
            last_intent_label="chat",
            last_user_utterance="hello",
        ),
    )
    ctx = svc.get_context("s4")
    assert ctx.intent_memory is not None
    assert ctx.intent_memory.last_intent == "CHAT"
    assert ctx.intent_memory.last_user_utterance == "hello"


def test_empty_session_returns_empty_context():
    svc = ContextStore()
    ctx = svc.get_context("nonexistent")
    assert ctx.window is None
    assert ctx.focus is None


def test_clear_session():
    svc = ContextStore()
    svc.record_turn("s5", "u1", "a1")
    svc.clear_session("s5")
    ctx = svc.get_context("s5")
    assert ctx.window is None
