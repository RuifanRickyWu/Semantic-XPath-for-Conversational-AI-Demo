"""
Live router test - calls the actual OpenAI API.

Usage:
    OPENAI_API_KEY=... python tests/run_router_live.py

Adapted from Semantic_XPath_Demo/refactor/tests/run_router_live.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the BE root is on sys.path
BE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BE_ROOT))

from clients.openai_client import OpenAIClient
from services.router_service import RouterService
from common.types import RouteInput, SessionSnapshot


def run_case(router: RouterService, utterance: str, session: SessionSnapshot) -> None:
    result = router.route(RouteInput(utterance, session))
    print("-")
    print("utterance:", utterance)
    print("session:", session)
    print("result:", result.routing)
    if result.original_utterance:
        print("original_utterance:", result.original_utterance)
    if result.effective_utterance != utterance:
        print("effective_utterance:", result.effective_utterance)


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Live router calls will fail.")

    client = OpenAIClient()
    router = RouterService(client=client)

    cases = [
        ("Hello", SessionSnapshot()),
        ("What plans do I have?", SessionSnapshot()),
        ("Switch to version 2", SessionSnapshot()),
        ("Work on my Toronto plan", SessionSnapshot()),
        ("What's on Day 2?", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Where are we eating?", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Make a 4-day Toronto plan", SessionSnapshot()),
        ("Add a museum on Day 3", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Delete that restaurant", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Switch to the other one", SessionSnapshot()),
        ("Create a trip plan for Tokyo", SessionSnapshot()),
        ("Plan a weekend in Paris", SessionSnapshot()),
        ("Add a dinner reservation", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Remove the museum stop", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Swap Day 2 and Day 3", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("List all versions", SessionSnapshot()),
        ("Activate my budget plan", SessionSnapshot()),
        ("Show me Day 1 schedule", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Is Day 3 packed?", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
        ("Where are we staying?", SessionSnapshot(active_task_id="t1", active_version_id="v1")),
    ]

    for utterance, session in cases:
        run_case(router, utterance, session)


if __name__ == "__main__":
    main()
