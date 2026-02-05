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
    """A single step's contribution to the final score."""
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
    """Score fusion trace for a single node."""
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
    """Complete score fusion trace across all nodes and steps."""
    per_node_traces: List[NodeFusionTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"per_node": [n.to_dict() for n in self.per_node_traces]}


@dataclass
class FinalFilteringTrace:
    """Trace of the final TopK and threshold filtering."""
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
            axis_str = f"{axis}::" if axis != "child" else ""
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
            lines.append(f"Global Index: [{self.global_index.get('start', '?')}]")
        
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
    
    elif pred_type == "AGG_EXISTS":
        child_type = pred.get("child_type", "*")
        axis = pred.get("child_axis", "child")
        axis_str = f"{axis}::" if axis != "child" else ""
        lines.append(f"{indent}└── AGG_EXISTS({axis_str}{child_type})")
        if pred.get("child_predicate"):
            lines.extend(_format_predicate_ast(pred["child_predicate"], depth + 1))
    
    elif pred_type == "AGG_PREV":
        child_type = pred.get("child_type", "*")
        axis = pred.get("child_axis", "child")
        axis_str = f"{axis}::" if axis != "child" else ""
        lines.append(f"{indent}└── AGG_PREV({axis_str}{child_type})")
        if pred.get("child_predicate"):
            lines.extend(_format_predicate_ast(pred["child_predicate"], depth + 1))
    
    else:
        lines.append(f"{indent}└── {pred_type}: {pred}")
    
    return lines


@dataclass
class ExecutionResult:
    """Result of executing an XPath query."""
    query: str
    matched_nodes: List[MatchedNode]
    execution_log: List[str] = field(default_factory=list)
    scoring_traces: List[Dict[str, Any]] = field(default_factory=list)
    traversal_steps: List[TraversalStep] = field(default_factory=list)
    execution_time_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    data_file: str = ""
    score_fusion_trace: Optional[ScoreFusionTrace] = None
    final_filtering_trace: Optional[FinalFilteringTrace] = None
    parsed_ast: Optional[ParsedQueryAST] = None
