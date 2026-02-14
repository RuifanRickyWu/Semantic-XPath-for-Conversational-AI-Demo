"""
CLI interface for OrchestratorService.

Examples:
  python cli_orchestrator.py --message "Hello" --session-id s1
  python cli_orchestrator.py --session-id s1
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure the Semantic_Xpath_BE directory is on the Python path.
sys.path.insert(0, str(Path(__file__).parent))

from clients.openai_client import OpenAIClient
from services.chatting.chatting_service import ChattingService
from services.intent_handling.plan_builder_service import PlanBuilderService
from services.intent_handling.plan_create_service import PlanCreateService
from services.intent_handling.xml_manager_service import XmlManagerService
from services.orchestrator_service import OrchestratorService
from services.routting.routting_service import RouttingService
from stores.context_store import ContextStore
from stores.registry_store import RegistryStore
from stores.session_store import SessionStore
from stores.state_store import StateStore


def build_orchestrator() -> OrchestratorService:
    """Create a fully wired OrchestratorService for CLI usage."""
    openai_client = OpenAIClient()

    routting_service = RouttingService(client=openai_client)
    chatting_service = ChattingService(client=openai_client)
    plan_builder_service = PlanBuilderService(client=openai_client)

    session_store = SessionStore()
    context_store = ContextStore()
    registry_store = RegistryStore()
    state_store = StateStore()
    xml_state_manager = XmlManagerService()

    plan_create_service = PlanCreateService(
        registry=registry_store,
        plan_builder=plan_builder_service,
        state_store=state_store,
        xml_state_manager=xml_state_manager,
    )

    return OrchestratorService(
        routting=routting_service,
        session_service=session_store,
        context_service=context_store,
        plan_create_service=plan_create_service,
        chatting=chatting_service,
    )


def print_turn_response(resp, as_json: bool, show_meta: bool) -> None:
    if as_json:
        print(json.dumps(asdict(resp), indent=2, ensure_ascii=False))
        return

    print(f"assistant> {resp.assistant_message}")
    if not show_meta:
        return
    print(
        "meta> "
        f"intent={resp.routing.intent} "
        f"registry_op={resp.routing.registry_op} "
        f"clarification={bool(resp.routing.requires_clarification)}"
    )
    if resp.session_updates.active_task_id or resp.session_updates.active_version_id:
        print(
            "meta> "
            f"active_task_id={resp.session_updates.active_task_id} "
            f"active_version_id={resp.session_updates.active_version_id}"
        )
    if resp.telemetry and resp.telemetry.events:
        print(f"meta> telemetry_events={resp.telemetry.events}")


def run_repl(
    orchestrator: OrchestratorService,
    session_id: str,
    as_json: bool,
    show_meta: bool,
) -> int:
    print("Interactive orchestrator CLI. Type /help for commands.")
    current_session_id = session_id

    while True:
        try:
            user_input = input(f"you[{current_session_id}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            return 0
        if user_input == "/help":
            print("Commands: /help, /exit, /quit, /session <id>")
            continue
        if user_input.startswith("/session "):
            new_session_id = user_input.replace("/session ", "", 1).strip()
            if not new_session_id:
                print("error> session id cannot be empty")
                continue
            current_session_id = new_session_id
            print(f"meta> switched session_id={current_session_id}")
            continue

        try:
            resp = orchestrator.orchestrate(user_input, current_session_id)
            print_turn_response(resp, as_json=as_json, show_meta=show_meta)
        except Exception as exc:
            print(f"error> {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI for Semantic XPath Orchestrator")
    parser.add_argument(
        "--session-id",
        default="cli-default",
        help="Session ID used for context/state continuity",
    )
    parser.add_argument(
        "--message",
        help="Run one turn and exit. If omitted, runs interactive mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw TurnResponse as JSON",
    )
    parser.add_argument(
        "--no-meta",
        action="store_true",
        help="Hide routing/session metadata in text mode",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    orchestrator = build_orchestrator()

    if args.message:
        resp = orchestrator.orchestrate(args.message, args.session_id)
        print_turn_response(resp, as_json=args.json, show_meta=not args.no_meta)
        return 0

    return run_repl(
        orchestrator=orchestrator,
        session_id=args.session_id,
        as_json=args.json,
        show_meta=not args.no_meta,
    )


if __name__ == "__main__":
    raise SystemExit(main())
