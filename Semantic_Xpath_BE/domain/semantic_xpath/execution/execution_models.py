"""
Execution Models - Data classes used during XPath query execution and results.

Contains models for traversal context, matched nodes, execution results,
and scoring/fusion traces.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET


@dataclass
class NodeItem:
    """
    A node with its traversal context for tracking parent relationships.

    Used to preserve parent grouping information during traversal,
    enabling local indexing like Day/POI[2] to return the 2nd POI
    in EACH Day rather than the global 2nd POI.
    """
    node: ET.Element
    path: str
    score: float
    parent_group_id: int

    def to_tuple(self):
        """Convert to legacy tuple format (node, path, score) for compatibility."""
        return (self.node, self.path, self.score)


@dataclass
class MatchedNode:
    """A matched node with its tree context and score."""
    node_data: Dict[str, Any]
    tree_path: str
    children: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tree_path": self.tree_path,
            "score": self.score,
            "node": self.node_data,
            "children": self.children,
        }


@dataclass
class TraversalStep:
    """A single step in the tree traversal for tracing."""
    step_index: int
    step_query: str
    nodes_before: List[Dict[str, Any]]
    nodes_after: List[Dict[str, Any]]
    action: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_query": self.step_query,
            "action": self.action,
            "nodes_before_count": len(self.nodes_before),
            "nodes_after_count": len(self.nodes_after),
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
            "details": self.details,
        }


@dataclass
class StepContribution:
    """Legacy compatibility model (not used by current result payload)."""
    step_index: int
    predicate_str: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "predicate": self.predicate_str,
            "score": self.score,
        }


@dataclass
class NodeFusionTrace:
    """Legacy compatibility model (not used by current result payload)."""
    node_path: str
    node_type: str
    step_contributions: List[StepContribution] = field(default_factory=list)
    accumulated_product: float = 1.0
    final_score: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_path": self.node_path,
            "node_type": self.node_type,
            "step_contributions": [s.to_dict() for s in self.step_contributions],
            "accumulated_product": self.accumulated_product,
            "final_score": self.final_score,
        }


@dataclass
class ScoreFusionTrace:
    """Legacy compatibility model (not used by current result payload)."""
    per_node_traces: List[NodeFusionTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"per_node": [n.to_dict() for n in self.per_node_traces]}


@dataclass
class FinalFilteringTrace:
    """Legacy compatibility model (not used by current result payload)."""
    before_filter_count: int = 0
    threshold: float = 0.0
    top_k: int = 0
    after_filter_count: int = 0
    filtered_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_filter_count": self.before_filter_count,
            "threshold": self.threshold,
            "top_k": self.top_k,
            "after_filter_count": self.after_filter_count,
            "filtered_nodes": self.filtered_nodes,
        }


@dataclass
class ParsedQueryAST:
    """Parsed AST representation for tracing and debugging."""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    global_index: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "global_index": self.global_index,
        }
    
    def to_tree_string(self, indent: int = 2) -> str:
        """Generate a human-readable tree representation of the AST."""
        lines = ["Query AST:"]
        for i, step in enumerate(self.steps):
            prefix = "├── " if i < len(self.steps) - 1 else "└── "
            axis = step.get("axis", "child")
            axis_val = "child" if axis in (None, "none") else axis
            axis_str = "//" if axis_val == "desc" else ""
            if "node_test_expr" in step:
                lines.append(f"{prefix}Step {i}: {axis_str}{_format_node_test_expr(step['node_test_expr'])}")
                predicates = _collect_predicates_from_node_test_expr(step["node_test_expr"])
                for p_idx, pred in enumerate(predicates):
                    label = "predicate" if len(predicates) == 1 else f"predicate[{p_idx}]"
                    lines.append(f"    │   {label}:")
                    lines.extend(_format_predicate_ast(pred, depth=2))
            else:
                node_type = step.get("node_type", "?")
                lines.append(f"{prefix}Step {i}: {axis_str}{node_type}")
            
            # Index
            if step.get("index"):
                idx = step["index"]
                idx_str = f"[{idx.get('start', '?')}"
                if idx.get("to_end"):
                    idx_str += ":]"
                elif idx.get("end"):
                    idx_str += f":{idx['end']}]"
                else:
                    idx_str += "]"
                lines.append(f"    │   index: {idx_str}")
            
            # Predicate AST
            if step.get("predicate_ast"):
                lines.append(f"    │   predicate:")
                pred_lines = _format_predicate_ast(step["predicate_ast"], depth=2)
                lines.extend(pred_lines)
        
        if self.global_index:
            idx = self.global_index
            idx_str = f"[{idx.get('start', '?')}"
            if idx.get("to_end"):
                idx_str += ":]"
            elif idx.get("end") is not None:
                idx_str += f":{idx['end']}]"
            else:
                idx_str += "]"
            lines.append(f"Global Index: {idx_str}")
        
        return "\n".join(lines)


def _format_predicate_ast(pred: Dict[str, Any], depth: int = 0) -> List[str]:
    """Recursively format a predicate AST node as tree lines."""
    indent = "    " * depth + "│   "
    lines = []
    
    pred_type = pred.get("type") or pred.get("operator", "unknown")
    
    if pred_type == "atom":
        lines.append(f"{indent}└── ATOM({pred.get('field', 'content')} =~ \"{pred.get('value', '')}\")")
    
    elif pred_type == "AND":
        lines.append(f"{indent}└── AND")
        for i, cond in enumerate(pred.get("conditions", [])):
            lines.extend(_format_predicate_ast(cond, depth + 1))
    
    elif pred_type == "OR":
        lines.append(f"{indent}└── OR")
        for cond in pred.get("conditions", []):
            lines.extend(_format_predicate_ast(cond, depth + 1))
    
    elif pred_type == "NOT":
        lines.append(f"{indent}└── NOT")
        if pred.get("condition"):
            lines.extend(_format_predicate_ast(pred["condition"], depth + 1))
    
    elif pred_type == "evidence_agg":
        op = pred.get("operator", "agg_max")
        selector = pred.get("selector")
        if selector:
            axis = selector.get("axis", "child")
            axis_val = "child" if axis in (None, "none") else axis
            axis_str = "//" if axis_val == "desc" else "/"
            test_str = _format_node_test_expr(selector.get("test", {}))
            lines.append(f"{indent}└── {op.upper()}({axis_str}{test_str})")
        else:
            lines.append(f"{indent}└── {op.upper()}()")
        inner = pred.get("inner_predicate")
        if inner:
            lines.extend(_format_predicate_ast(inner, depth + 1))
    
    elif pred_type in ("AGG_EXISTS", "AGG_PREV"):
        selector = pred.get("selector")
        if selector:
            axis = selector.get("axis", "child")
            axis_val = "child" if axis in (None, "none") else axis
            axis_str = "//" if axis_val == "desc" else "/"
            test_str = _format_node_test_expr(selector.get("test", {}))
            lines.append(f"{indent}└── {pred_type}({axis_str}{test_str})")
        else:
            child_type = pred.get("child_type", "*")
            axis = pred.get("child_axis", "child")
            axis_str = "//" if axis == "desc" else "/"
            lines.append(f"{indent}└── {pred_type}({axis_str}{child_type})")
        if pred.get("child_predicate"):
            lines.extend(_format_predicate_ast(pred["child_predicate"], depth + 1))
    
    else:
        lines.append(f"{indent}└── {pred_type}: {pred}")
    
    return lines


def _format_node_test_expr(expr: Dict[str, Any]) -> str:
    if not expr:
        return "?"
    etype = expr.get("type")
    if etype == "leaf":
        return _format_node_test(expr.get("test", {}))
    if etype == "and":
        return " AND ".join(_format_node_test_expr(c) for c in expr.get("children", []))
    if etype == "or":
        return " OR ".join(_format_node_test_expr(c) for c in expr.get("children", []))
    return str(expr)


def _format_node_test(test: Dict[str, Any]) -> str:
    kind = test.get("kind")
    name = test.get("name")
    base = "*" if kind == "wildcard" else (name or "?")
    if test.get("predicate"):
        base += "[predicate]"
    if test.get("index"):
        idx = test["index"]
        idx_str = f"[{idx.get('start', '?')}"
        if idx.get("to_end"):
            idx_str += ":]"
        elif idx.get("end") is not None:
            idx_str += f":{idx['end']}]"
        else:
            idx_str += "]"
        base += idx_str
    return base


def _collect_predicates_from_node_test_expr(expr: Dict[str, Any]) -> List[Dict[str, Any]]:
    preds: List[Dict[str, Any]] = []

    etype = expr.get("type")
    if etype == "leaf":
        test = expr.get("test", {})
        pred = test.get("predicate")
        if pred:
            preds.append(pred)
        return preds
    if etype in ("and", "or"):
        for child in expr.get("children", []):
            preds.extend(_collect_predicates_from_node_test_expr(child))
    return preds


# Path segment: type + full attributes for one step in the tree (root → node).
PathSegment = Dict[str, Any]  # keys: "type", "attributes"


@dataclass
class RetrievalDetail:
    """Complementary information for a retrieval: per-node detail and step trace."""
    per_node: List[Dict[str, Any]] = field(default_factory=list)  # each: tree_path, score, node, children, evidence
    step_scoring_trace: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of executing a semantic XPath query.

    - retrieved_nodes: The retrieved nodes themselves (node payloads only). Use this as the canonical answer set.
    - retrieval_detail: Full complementary info: per-node tree_path (with full parent attributes), score, node, children, evidence; and step_scoring_trace.
    """
    query: str
    retrieved_nodes: List[Dict[str, Any]] = field(default_factory=list)  # node-only dicts (type, attributes, optional children)
    retrieval_detail: RetrievalDetail = field(default_factory=lambda: RetrievalDetail(per_node=[], step_scoring_trace=[]))
