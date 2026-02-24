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
from services.intent_handling.base_chat_service import BaseChatService
from services.intent_handling.plan_edit_service import PlanEditService
from services.intent_handling.plan_update_interpreter_service import PlanUpdateInterpreterService
from services.intent_handling.plan_add_interpreter_service import PlanAddInterpreterService
from services.intent_handling.plan_builder_service import PlanBuilderService
from services.intent_handling.plan_create_service import PlanCreateService
from services.intent_handling.plan_qa_service import PlanQAService
from services.intent_handling.registry_delete_service import RegistryDeleteService
from services.intent_handling.registry_edit_service import RegistryEditService
from services.intent_handling.registry_qa_service import RegistryQAService
from services.query_generation import (
    PlanContentQueryGenerationService,
    RegistryQueryGenerationService,
)
from services.result_verification import SemanticXPathResultVerifier
from clients.bart_client import get_bart_client
from services.predicate_scorer import (
    get_scorer as get_predicate_scorer,
    load_config as load_predicate_config,
)
from domain.semantic_xpath.execution import SemanticXPathExecutor
from services.orchestrator_service import OrchestratorService
from services.routting.routting_service import RouttingService
from stores.context_store import ContextStore
from stores.registry_store import RegistryStore
from stores.session_store import SessionStore
from stores.task_state_store import TaskStateStore
from stores.xml_manager import XmlManager


def build_orchestrator() -> OrchestratorService:
    """Create a fully wired OrchestratorService for CLI usage."""
    openai_client = OpenAIClient()
    bart_client = get_bart_client()

    routting_service = RouttingService(client=openai_client)
    chatting_service = ChattingService(client=openai_client)
    plan_builder_service = PlanBuilderService(client=openai_client)
    registry_query_service = RegistryQueryGenerationService(client=openai_client)
    plan_query_service = PlanContentQueryGenerationService(client=openai_client)
    predicate_config = load_predicate_config()
    xpath_executor_config = predicate_config.get("xpath_executor", {})
    score_threshold = float(xpath_executor_config.get("score_threshold", 0.1))

    registry_scorer = get_predicate_scorer(config=predicate_config, client=bart_client)
    registry_executor = SemanticXPathExecutor(
        scorer=registry_scorer,
        top_k=20,
        score_threshold=score_threshold,
    )
    result_verifier = SemanticXPathResultVerifier(client=openai_client)

    session_store = SessionStore()
    context_store = ContextStore()
    xml_manager = XmlManager()
    registry_store = RegistryStore(xml_manager=xml_manager)
    state_store = TaskStateStore(xml_manager=xml_manager, registry_store=registry_store)

    plan_create_service = PlanCreateService(
        registry=registry_store,
        plan_builder=plan_builder_service,
        state_store=state_store,
    )
    chat_service = BaseChatService()
    plan_qa_service = PlanQAService(
        state_store=state_store,
        plan_query_service=plan_query_service,
        executor=registry_executor,
        result_verifier=result_verifier,
    )
    plan_update_interpreter = PlanUpdateInterpreterService(client=openai_client)
    plan_add_interpreter = PlanAddInterpreterService(client=openai_client)
    plan_edit_service = PlanEditService(
        state_store=state_store,
        plan_query_service=plan_query_service,
        executor=registry_executor,
        result_verifier=result_verifier,
        plan_update_interpreter=plan_update_interpreter,
        plan_add_interpreter=plan_add_interpreter,
    )
    registry_qa_service = RegistryQAService(
        registry=registry_store,
        registry_query_service=registry_query_service,
        executor=registry_executor,
        result_verifier=result_verifier,
    )
    registry_edit_service = RegistryEditService(
        registry=registry_store,
        registry_query_service=registry_query_service,
        executor=registry_executor,
        result_verifier=result_verifier,
    )
    registry_delete_service = RegistryDeleteService(
        registry=registry_store,
        registry_query_service=registry_query_service,
        executor=registry_executor,
        result_verifier=result_verifier,
    )

    orchestrator = OrchestratorService(
        routting=routting_service,
        session_service=session_store,
        context_service=context_store,
        plan_create_service=plan_create_service,
        chatting=chatting_service,
        registry=registry_store,
        chat_service=chat_service,
        plan_qa_service=plan_qa_service,
        plan_edit_service=plan_edit_service,
        registry_qa_service=registry_qa_service,
        registry_edit_service=registry_edit_service,
        registry_delete_service=registry_delete_service,
    )
    return orchestrator, state_store, registry_store


def print_turn_response(resp, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(resp), indent=2, ensure_ascii=False))
        return
    print(f"assistant> {resp.assistant_message}")


_QUIT_CMDS = frozenset(("/exit", "/quit", "/q", "/e", "quit", "exit", "q", "e"))
_RESET_CMDS = frozenset(("/reset", "/r", "reset", "r"))


def run_repl(
    orchestrator: OrchestratorService,
    session_id: str,
    as_json: bool,
    state_store=None,
    registry_store=None,
) -> int:
    print("Interactive orchestrator CLI. Type q/e/quit/exit to quit; r/reset to clear all XML and memory; /help for commands.")
    current_session_id = session_id

    while True:
        try:
            user_input = input(f"you[{current_session_id}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in _QUIT_CMDS:
            return 0
        if cmd in _RESET_CMDS:
            orchestrator.session_service.clear_session(current_session_id)
            orchestrator.context_service.clear_session(current_session_id)
            if state_store is not None:
                state_store.clear_all_task_data()
            if registry_store is not None:
                registry_store.clear_all()
            continue
        if cmd == "/help":
            print(
                "Commands: /help, /session <id>, /reset or r, /quit or q\n"
                "  quit/exit/q/e - exit\n"
                "  reset/r - clear all memory, tasks, plans, and XML files"
            )
            continue
        if user_input.lower().startswith("/session "):
            new_session_id = user_input[9:].strip()
            if not new_session_id:
                print("error> session id cannot be empty")
                continue
            current_session_id = new_session_id
            continue

        try:
            resp = orchestrator.orchestrate(user_input, current_session_id)
            print_turn_response(resp, as_json=as_json)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    orchestrator, state_store, registry_store = build_orchestrator()

    if args.message:
        resp = orchestrator.orchestrate(args.message, args.session_id)
        print_turn_response(resp, as_json=args.json)
        return 0

    return run_repl(
        orchestrator=orchestrator,
        session_id=args.session_id,
        as_json=args.json,
        state_store=state_store,
        registry_store=registry_store,
    )


if __name__ == "__main__":
    raise SystemExit(main())
