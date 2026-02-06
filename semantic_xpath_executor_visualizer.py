"""
Executor visualizer for Semantic XPath queries.

Prints:
  - Parsed AST tree (with predicate trees)
  - Per-step matched counts
  - Per-node score breakdowns (explicit predicate scoring)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from pipeline_execution.semantic_xpath_execution import DenseXPathExecutor
from pipeline_execution.semantic_xpath_execution.predicate_scorer.base import (
    PredicateScorer,
    BatchScoringResult,
    ScoringResult,
)


class DummyScorer(PredicateScorer):
    """Simple keyword-based scorer for visualization."""

    def score_batch(self, nodes: List[Dict[str, Any]], predicate: str) -> BatchScoringResult:
        pred = (predicate or "").lower()
        results: List[ScoringResult] = []
        for node in nodes:
            desc = (node.get("description") or "").lower()
            score = 0.9 if pred and pred in desc else 0.1
            results.append(ScoringResult(
                node_id=node.get("id", ""),
                node_type=node.get("type", ""),
                node_description=node.get("description", ""),
                predicate=predicate,
                score=score,
                reasoning="keyword_match" if score > 0.5 else "no_match",
            ))
        return BatchScoringResult(predicate=predicate, results=results)


def _format_scoring_steps(scoring_steps: List[Dict[str, Any]], indent: int = 0) -> List[str]:
    if not scoring_steps:
        return []
    # Keep output brief: show the root computation (last step)
    return _format_scoring_step(scoring_steps[-1], indent)


def _format_scoring_step(step: Dict[str, Any], indent: int) -> List[str]:
    lines: List[str] = []
    pad = " " * indent
    step_type = step.get("type", "unknown")

    if step_type == "atom":
        cond = step.get("condition", {})
        field = cond.get("field", "content")
        op = cond.get("operator", "=~")
        value = cond.get("value", "")
        score = step.get("score", 0.0)
        lines.append(f"{pad}ATOM({field} {op} \"{value}\") = {score:.2f}")
        return lines

    if step_type == "and":
        result = step.get("result", 0.0)
        lines.append(f"{pad}AND result = {result:.2f}")
        for inner in step.get("inner_traces", []):
            if inner:
                lines.extend(_format_scoring_step(inner[-1], indent + 2))
        return lines

    if step_type == "or":
        result = step.get("result", 0.0)
        lines.append(f"{pad}OR result = {result:.2f}")
        for inner in step.get("inner_traces", []):
            if inner:
                lines.extend(_format_scoring_step(inner[-1], indent + 2))
        return lines

    if step_type == "not":
        result = step.get("result", 0.0)
        lines.append(f"{pad}NOT result = {result:.2f}")
        inner = step.get("inner_trace", [])
        if inner:
            lines.extend(_format_scoring_step(inner[-1], indent + 2))
        return lines

    if step_type in ("agg_exists_recursive", "agg_exists"):
        result = step.get("result", 0.0)
        lines.append(f"{pad}AGG_EXISTS result = {result:.2f}")
        child_results = step.get("child_results", [])
        for child in child_results[:3]:
            lines.append(
                f"{pad}  child score={child.get('score', 0.0):.2f} "
                f"size={child.get('subtree_size', 0)}"
            )
        return lines

    if step_type in ("agg_prev_weighted", "agg_prev"):
        result = step.get("result", 0.0)
        lines.append(f"{pad}AGG_PREV result = {result:.2f}")
        child_results = step.get("child_results", [])
        for child in child_results[:3]:
            lines.append(
                f"{pad}  child score={child.get('score', 0.0):.2f} "
                f"size={child.get('subtree_size', 0)}"
            )
        return lines

    lines.append(f"{pad}{step_type}: {step}")
    return lines


def _collect_leaf_predicates(expr: Dict[str, Any]) -> List[Optional[str]]:
    etype = expr.get("type")
    if etype == "leaf":
        test = expr.get("test", {})
        pred = test.get("predicate_str")
        return [pred] if pred else [None]
    if etype in ("and", "or"):
        preds: List[Optional[str]] = []
        for child in expr.get("children", []):
            preds.extend(_collect_leaf_predicates(child))
        return preds
    return []


def _print_step_results(step_trace: Dict[str, Any], step_index: int) -> None:
    step_query = step_trace.get("step_query", f"step_{step_index}")
    nodes_after = step_trace.get("nodes_after", [])
    details = step_trace.get("details", {})
    node_test_expr = details.get("node_test_expr", {})
    expr_type = node_test_expr.get("type")
    leaf_predicates = _collect_leaf_predicates(node_test_expr)

    print(f"\nStep {step_index}: {step_query}")
    print(f"- matched: {len(nodes_after)}")
    if not nodes_after:
        return

    # Build predicate trace map: predicate_str -> node_id -> node_trace
    pred_trace_map: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for trace in details.get("scoring_trace", []):
        pred_label = trace.get("predicate", "predicate")
        for node_score in trace.get("node_scores", []):
            pred_trace_map.setdefault(pred_label, {})[node_score.get("node_id")] = node_score

    max_display = 3
    for node_info in nodes_after[:max_display]:
        node_id = node_info.get("node_id")
        name = node_info.get("name", "?")
        node_type = node_info.get("type", "?")
        score = node_info.get("score", 1.0)
        print(f"  - {node_type} \"{name}\" (score={score:.2f})")

        # If there are no predicates at all, note it.
        if not pred_trace_map:
            print("    predicate: <none>")
            continue

        # Compute and display combination rule if AND/OR
        if expr_type in ("and", "or") and leaf_predicates:
            leaf_scores: List[float] = []
            for pred in leaf_predicates:
                if pred is None:
                    leaf_scores.append(1.0)
                else:
                    node_trace = pred_trace_map.get(pred, {}).get(node_id)
                    leaf_scores.append(node_trace.get("final_score", 0.0) if node_trace else 0.0)
            if leaf_scores:
                if expr_type == "and":
                    combined = min(leaf_scores)
                    print(f"    AND combine = min({', '.join(f'{s:.2f}' for s in leaf_scores)}) = {combined:.2f}")
                else:
                    combined = max(leaf_scores)
                    print(f"    OR combine = max({', '.join(f'{s:.2f}' for s in leaf_scores)}) = {combined:.2f}")

        # Print predicate traces per predicate
        for pred_label, nodes_map in pred_trace_map.items():
            node_trace = nodes_map.get(node_id)
            if not node_trace:
                continue
            print(f"    predicate: {pred_label} (score={node_trace.get('final_score', 0.0):.2f})")
            for line in _format_scoring_steps(node_trace.get("scoring_steps", []), indent=6):
                print(f"{line}")

    if len(nodes_after) > max_display:
        print(f"  ... {len(nodes_after) - max_display} more nodes not shown")


def visualize_queries(tree_path: Path, queries: List[str]) -> None:
    executor = DenseXPathExecutor(
        scorer=DummyScorer(),
        scoring_method="dummy",
        top_k=1000,
        score_threshold=0.0,
        tree_path=tree_path,
    )

    for idx, query in enumerate(queries):
        print("\n" + "=" * 80)
        print(f"Query {idx + 1}")
        print(query)
        print("=" * 80)

        result = executor.execute(query)
        if result.parsed_ast:
            print("\n=== Query AST ===")
            print(result.parsed_ast.to_tree_string())

        print("\n=== Step Results ===")
        for step in result.traversal_steps:
            if step.action in ("root_match", "node_test_expr"):
                _print_step_results(step.to_dict(), step.step_index)

        if result.final_filtering_trace:
            print("\n=== Final Filtering ===")
            print(
                f"before={result.final_filtering_trace.before_filter_count} "
                f"after={result.final_filtering_trace.after_filter_count}"
            )


def main() -> None:
    tree_path = Path("storage/memory/travel/travel_toronto_10day.xml")
    queries = [
        # 1) Global range + OR node tests + desc axis + agg_exists + NOT
        (
            "(/Root/Itinerary_Version[-1]/Itinerary/Day[1]"
            "[agg_exists(desc::(POI OR Restaurant)[content =~ \"view\"]) "
            "AND not(atom(content =~ \"closed\"))]/"
            "(POI[1][atom(content =~ \"museum\")] OR "
            "Restaurant[1][atom(content =~ \"seafood\")]))[1:3]"
        ),
        # 2) Wildcard step + index range + AND/NOT in predicate
        (
            "/Root/Itinerary_Version[-1]/Itinerary/Day[1]/"
            ".[1:3][atom(content =~ \"morning\")]/"
            "POI[1:3][atom(content =~ \"coffee\") AND not(atom(content =~ \"decaf\"))]"
        ),
        # 3) NodeTestExpr AND between wildcard + typed node tests
        (
            "/Root/Itinerary_Version[-1]/Itinerary/Day[1]/"
            "(.[1:3][atom(content =~ \"tour\")] AND "
            "POI[1:3][atom(content =~ \"museum\")])"
        ),
        # 4) Recursive agg_exists -> agg_prev (1 level)
        (
            "/Root/Itinerary_Version[-1]/Itinerary/Day[1]"
            "[agg_exists(desc::(POI OR Restaurant)"
            "[agg_prev(desc::(POI OR Restaurant)"
            "[atom(content =~ \"park\")])])]"
        ),
        # 5) Recursive agg_prev -> agg_exists -> agg_prev (2 levels) + global index
        (
            "(/Root/Itinerary_Version[-1]/Itinerary"
            "[agg_prev(desc::Day"
            "[agg_exists(desc::(POI OR Restaurant)"
            "[agg_prev(desc::(POI OR Restaurant)"
            "[atom(content =~ \"lunch\")])])])]/Day[1:3])[1:3]"
        ),
        # 6) Predicate on Day + predicate on child POI
        (
            "/Root/Itinerary_Version[-1]/Itinerary/"
            "Day[1:3][atom(content =~ \"day\") AND agg_exists(desc::POI"
            "[atom(content =~ \"museum\")])]/"
            "POI[1:3][atom(content =~ \"art\") OR atom(content =~ \"gallery\")]"
        ),
        # 7) desc axis + wildcard matching
        (
            "/Root/Itinerary_Version[-1]/Itinerary/"
            "desc::.[1:3][atom(content =~ \"view\")]/"
            "desc::POI[1:3][atom(content =~ \"park\")]"
        ),
    ]
    visualize_queries(tree_path, queries)


if __name__ == "__main__":
    main()
