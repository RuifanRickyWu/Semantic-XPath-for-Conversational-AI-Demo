"""
Interactive chat + plan initialization CLI (no CRUD).
"""

from __future__ import annotations

from pipeline_execution.cold_start.chat_plan_router import ChatPlanRouter
from pipeline_execution.cold_start import TaskBootstrapper
from pipeline.semantic_xpath_pipeline.semantic_xpath_data_model import ResultFormatter


def run() -> None:
    print("Chat/Plan CLI. Type 'reset' to clear history. Type 'exit' or 'quit' to stop.")
    router = ChatPlanRouter()
    bootstrapper = TaskBootstrapper()
    formatter = ResultFormatter()

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        if user_input.lower() == "reset":
            result = bootstrapper.reset_all()
            if isinstance(result, dict) and result.get("success"):
                print("Reset complete.")
            else:
                print(result)
            continue

        result = router.route(user_input, emit_user_facing=True)
        if isinstance(result, dict):
            if result.get("mode") == "crud":
                print(formatter.format_result(result))
            else:
                print(result.get("response", ""))
        else:
            print(result)


if __name__ == "__main__":
    run()
