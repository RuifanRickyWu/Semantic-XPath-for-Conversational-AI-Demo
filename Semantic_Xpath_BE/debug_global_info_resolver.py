#!/usr/bin/env python3
"""
Interactive debug printer for GlobalInfoResolver.

Usage:
  python debug_global_info_resolver.py
  python debug_global_info_resolver.py --limit 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import xml.etree.ElementTree as ET

from pipeline_execution.semantic_xpath_execution import DenseXPathExecutor
from pipeline_execution.semantic_xpath_util.schema_loader import load_config
from pipeline_execution.task_version_resolver import GlobalInfoResolver
from pipeline_execution.task_version_resolver.version_selector_model import ResolvedVersion
from utils.tree_modification.base import find_node_by_path


def _extract_raw_selectors(raw: str) -> Dict[str, Optional[str]]:
    task_selector_raw = None
    version_selector_raw = None
    operation_raw = None
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("task selector:"):
            task_selector_raw = line.split(":", 1)[1].strip()
        elif lower.startswith("version selector:"):
            version_selector_raw = line.split(":", 1)[1].strip()
        elif lower.startswith("operation:"):
            operation_raw = line.split(":", 1)[1].strip()
        elif lower in ("read", "create", "update", "delete", "state"):
            operation_raw = line
    return {
        "task_selector_raw": task_selector_raw,
        "version_selector_raw": version_selector_raw,
        "operation_raw": operation_raw,
    }


def _score_xpath(
    executor: DenseXPathExecutor,
    xpath: str,
    expected_tag: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        execution = executor.execute(xpath)
    except Exception as exc:
        return [{"error": f"executor.execute failed: {exc}"}]

    if not execution.matched_nodes:
        return []

    root = executor.tree.getroot()
    ranked = sorted(execution.matched_nodes, key=lambda n: n.score, reverse=True)
    for node in ranked:
        elem = find_node_by_path(root, node.tree_path)
        if elem is None:
            continue
        if expected_tag and elem.tag != expected_tag:
            continue
        results.append({
            "score": node.score,
            "tree_path": node.tree_path,
            "tag": elem.tag,
            "number": elem.get("number"),
            "name": elem.get("name"),
        })
        if len(results) >= limit:
            break
    return results


def _print_state(resolver: GlobalInfoResolver, label: str) -> None:
    state = {
        "task_index": resolver.get_state_task_index(),
        "version_index": getattr(resolver, "_state_version_index", None),
    }
    print(f"{label}: {json.dumps(state, ensure_ascii=False)}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _print_version_detail(task_elem: Optional[ET.Element], version_number: Optional[int]) -> None:
    if task_elem is None or version_number is None:
        return
    version_elem = None
    for child in list(task_elem):
        if child.tag == "Version" and child.get("number") == str(version_number):
            version_elem = child
            break
    if version_elem is None:
        return
    desc = (version_elem.findtext("description") or "").strip()
    if desc:
        print(f"Version description: {desc}")


def _print_task_detail(task_elem: Optional[ET.Element]) -> None:
    if task_elem is None:
        return
    number = task_elem.get("number")
    name = (task_elem.get("name") or "").strip()
    title = (task_elem.findtext("title") or "").strip()
    desc = (task_elem.findtext("description") or "").strip()
    print(f"Task element: number={number} name={name} title={title}")
    if desc:
        print(f"Task description: {desc}")


def _print_ordered_numbers(label: str, items: List[ET.Element]) -> None:
    if not items:
        print(f"{label}: []")
        return

    def _num(elem: ET.Element) -> Optional[int]:
        try:
            return int(elem.get("number")) if elem.get("number") is not None else None
        except (TypeError, ValueError):
            return None
    raw = [(_num(e), e.tag) for e in items]
    ordered = sorted(enumerate(items), key=lambda t: (
        0 if _num(t[1]) is not None else 1,
        _num(t[1]) if _num(t[1]) is not None else 0,
        t[0],
    ))
    ordered_nums = [(_num(e), e.tag) for _, e in ordered]
    print(f"{label} raw order: {raw}")
    print(f"{label} ordered by number: {ordered_nums}")


def _print_resolved(version_result: ResolvedVersion) -> None:
    print("Parsed selectors:")
    print(json.dumps(version_result.to_dict(), indent=2, ensure_ascii=False))
    print(f"Task selector string: {version_result.get_task_selector_string()}")
    print(f"Version selector string: {version_result.get_version_selector_string()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive GlobalInfoResolver debug printer")
    parser.add_argument("--limit", type=int, default=5, help="Max matches to print for semantic XPath selectors")
    args = parser.parse_args()

    config = load_config()

    executor = DenseXPathExecutor(config=config)

    base_dir = Path(__file__).resolve().parent
    global_memory_path = base_dir / "storage" / "memory" / "global" / "root_task_version.xml"
    task_memory_dir = base_dir / "storage" / "memory" / "task"
    task_schema_dir = base_dir / "storage" / "schemas" / "task"

    global_schema_path = (config or {}).get("global_schema_path")

    resolver = GlobalInfoResolver(
        executor=executor,
        task_schema_dir=task_schema_dir,
        task_memory_dir=task_memory_dir,
        global_memory_path=global_memory_path,
        traces_path=None,
        schema_name=global_schema_path or "root_task_version",
        client=None,
    )
    resolver.set_tree(executor.tree)

    print("GlobalInfoResolver Debug Printer")
    print("Enter a request. Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_query = input("request> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            break

        if not user_query:
            continue
        if user_query.lower() in ("exit", "quit", ":q"):
            break

        print("=" * 80)
        print(f"User query: {user_query}")
        _print_state(resolver, "State before")

        try:
            version_result = resolver.resolve(user_query)
        except Exception as exc:
            print(f"Resolver error: {exc}")
            continue

        print("Raw LLM response:")
        print(version_result.raw_response)
        raw_parts = _extract_raw_selectors(version_result.raw_response)
        if any(raw_parts.values()):
            print(f"Raw selector fields: {json.dumps(raw_parts, ensure_ascii=False)}")

        _print_resolved(version_result)

        resolver.apply_state_defaults(version_result)
        _print_state(resolver, "State after apply_state_defaults")

        if version_result.task_semantic_query:
            print(f"Task semantic selector: {version_result.task_semantic_query}")
            task_matches = _score_xpath(executor, version_result.task_semantic_query, "Task", args.limit)
            print("Task selector matches:")
            print(json.dumps(task_matches, indent=2, ensure_ascii=False))

        if version_result.semantic_query:
            print(f"Version semantic selector: {version_result.semantic_query}")
            version_matches = _score_xpath(executor, version_result.semantic_query, "Version", args.limit)
            print("Version selector matches:")
            print(json.dumps(version_matches, indent=2, ensure_ascii=False))

        task_context = resolver.resolve_task_context(version_result)
        if task_context:
            print("Resolved task context:")
            print(json.dumps(_json_safe(task_context), indent=2, ensure_ascii=False))

        all_tasks = resolver.load_global_tasks()
        _print_ordered_numbers("Tasks", all_tasks)

        task_elem, task_number, version_number = resolver.resolve_task_version_elements(version_result)
        print(f"Resolved task number: {task_number}")
        print(f"Resolved version number: {version_number}")
        _print_task_detail(task_elem)
        if task_elem is not None:
            versions = [c for c in list(task_elem) if c.tag == "Version"]
            _print_ordered_numbers(f"Versions for task {task_elem.get('number')}", versions)
        _print_version_detail(task_elem, version_number)

        resolver.update_state(task_number, version_number)
        _print_state(resolver, "State after update_state")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
