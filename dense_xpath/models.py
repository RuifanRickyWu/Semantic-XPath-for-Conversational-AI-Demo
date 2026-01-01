"""
Data models for the Dense XPath system.

Contains all dataclasses used throughout the xpath execution pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class IndexRange:
    """Represents an index or index range for positional selection."""
    start: int  # 1-based start index (or single index, or negative for from-end)
    end: Optional[int] = None  # 1-based end index (inclusive), None if single index or to_end
    to_end: bool = False  # If True, range extends to the end (for [-N:] syntax)
    
    @property
    def is_range(self) -> bool:
        """Check if this represents a range (vs single index)."""
        return self.end is not None or self.to_end
    
    def __repr__(self):
        if self.to_end:
            return f"[{self.start}:]"
        elif self.end is not None:
            return f"[{self.start}:{self.end}]"
        return f"[{self.start}]"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for tracing."""
        result = {"start": self.start}
        if self.to_end:
            result["type"] = "range_to_end"
            result["to_end"] = True
        elif self.end is not None:
            result["type"] = "range"
            result["end"] = self.end
        else:
            result["type"] = "single"
        return result


@dataclass
class QueryStep:
    """Represents a single step in an XPath query."""
    node_type: str  # e.g., "Itinerary", "Day", "POI", "Restaurant"
    predicate: Optional[str] = None  # semantic predicate, e.g., "artistic"
    index: Optional[IndexRange] = None  # positional index or range
    
    def __repr__(self):
        parts = [self.node_type]
        if self.predicate:
            parts.append(f'[description =~ "{self.predicate}"]')
        if self.index is not None:
            parts.append(str(self.index))
        return "".join(parts)


@dataclass
class MatchedNode:
    """A matched node with its tree context and score."""
    node_data: Dict[str, Any]  # The node's own data
    tree_path: str  # Path in tree, e.g., "Itinerary > Day 1 > POI 2"
    children: List[Dict[str, Any]] = field(default_factory=list)  # All child nodes
    score: float = 1.0  # Semantic matching score (1.0 if no semantic predicate)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tree_path": self.tree_path,
            "score": self.score,
            "node": self.node_data,
            "children": self.children
        }


@dataclass
class TraversalStep:
    """A single step in the tree traversal for tracing."""
    step_index: int
    step_query: str
    nodes_before: List[Dict[str, Any]]  # Nodes at start of step
    nodes_after: List[Dict[str, Any]]   # Nodes after filtering
    action: str  # "type_match", "semantic_predicate", "positional_index", "global_index"
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_index": self.step_index,
            "step_query": self.step_query,
            "action": self.action,
            "nodes_before_count": len(self.nodes_before),
            "nodes_after_count": len(self.nodes_after),
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
            "details": self.details
        }


@dataclass
class ExecutionResult:
    """Result of executing an XPath query."""
    query: str
    matched_nodes: List[MatchedNode]
    execution_log: List[str] = field(default_factory=list)
    scoring_traces: List[Dict[str, Any]] = field(default_factory=list)
    traversal_steps: List[TraversalStep] = field(default_factory=list)

