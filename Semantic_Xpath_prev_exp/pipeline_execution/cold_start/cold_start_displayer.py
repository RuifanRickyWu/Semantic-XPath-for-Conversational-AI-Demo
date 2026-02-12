"""
Cold start testing displayer.

Generates cold-start artifacts for user-provided requests and prints
only the raw LLM output in a readable format while storing files in cold_start_results/.
"""

from __future__ import annotations

import json
import yaml
from pathlib import Path
from datetime import datetime

from pipeline_execution.cold_start import TaskBootstrapper
from pipeline_execution.cold_start.user_facing_formatter import format_user_facing


BASE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BASE_DIR / "cold_start_results"


def _slugify(text: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    text = "_".join(filter(None, text.split("_")))
    return text[:80] if text else "request"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prompt_request() -> str:
    try:
        return input("> ").strip()
    except EOFError:
        return "exit"


def run() -> None:
    print("Enter a request. Type 'exit' or 'quit' to stop.")
    bootstrapper = TaskBootstrapper()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        request = _prompt_request()
        if not request:
            continue
        if request.lower() in ("exit", "quit"):
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _slugify(request)
        output_dir = RESULTS_DIR / f"{timestamp}_{slug}"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = bootstrapper.generate(request, save=True, activate=False)

        # Always store raw JSON
        _write_text(output_dir / "result.json", json.dumps(result, indent=2))

        llm_output = result.get("llm_output") if isinstance(result, dict) else None
        if llm_output is not None:
            llm_text = yaml.safe_dump(llm_output, sort_keys=False)
            _write_text(output_dir / "llm_output.yaml", llm_text)

        user_facing = result.get("user_facing") if isinstance(result, dict) else None
        if user_facing:
            user_text = format_user_facing(user_facing)
            _write_text(output_dir / "user_facing.txt", user_text)

        # Store key artifacts in results folder for quick inspection
        if isinstance(result, dict):
            if result.get("domain_schema"):
                _write_text(output_dir / "domain_schema.yaml", yaml.safe_dump(result["domain_schema"], sort_keys=False))
            if result.get("task_schema"):
                _write_text(output_dir / "task_schema.yaml", yaml.safe_dump(result["task_schema"], sort_keys=False))
            if result.get("memory_xml"):
                _write_text(output_dir / "memory.xml", result["memory_xml"])

        # Print only the user-facing output (readable, minimal)
        if user_facing:
            print(format_user_facing(user_facing))
        else:
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run()
