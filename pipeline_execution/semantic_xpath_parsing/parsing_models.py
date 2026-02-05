"""
Parsing Models - Data classes produced by the query parser.

Contains QueryStep and IndexRange, which are the output of parsing
a Semantic XPath query string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .predicate_ast import PredicateNode


# =============================================================================
# Index and Position Models
# =============================================================================

@dataclass
class IndexRange:
    """Represents an index or index range for positional selection."""
    start: int  # 1-based start index (or single index, or negative for from-end)
    end: Optional[int] = None  # 1-based end index (inclusive)
    to_end: bool = False  # If True, range extends to the end (for [-N:] syntax)

    @property
    def is_range(self) -> bool:
        """Check if this represents a range (vs single index)."""
        return self.end is not None or self.to_end

    def __repr__(self) -> str:
        if self.to_end:
            return f"[{self.start}:]"
        elif self.end is not None:
            return f"[{self.start}:{self.end}]"
        return f"[{self.start}]"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for tracing."""
        result: Dict[str, Any] = {"start": self.start}
        if self.to_end:
            result["type"] = "range_to_end"
            result["to_end"] = True
        elif self.end is not None:
            result["type"] = "range"
            result["end"] = self.end
        else:
            result["type"] = "single"
        return result


# =============================================================================
# Query Step
# =============================================================================

@dataclass
class QueryStep:
    """
    Represents a single step in an XPath query.

    Each step consists of:
    - axis: The traversal axis ("child" for direct children, "desc" for all descendants)
    - node_type: The target node type to match
    - predicate: Optional predicate AST for semantic filtering
    - index: Optional positional index or range
    """
    node_type: str
    predicate: Optional[PredicateNode] = None
    index: Optional[IndexRange] = None
    axis: str = "child"
    predicate_str: Optional[str] = None  # Original predicate string for display

    def __repr__(self) -> str:
        axis_prefix = f"{self.axis}::" if self.axis != "child" else ""
        parts = [f"{axis_prefix}{self.node_type}"]
        if self.predicate:
            parts.append(f'[{self.predicate}]')
        elif self.predicate_str:
            parts.append(f'[description =~ "{self.predicate_str}"]')
        if self.index is not None:
            parts.append(str(self.index))
        return "".join(parts)

    def has_semantic_predicate(self) -> bool:
        """Check if this step has a semantic predicate."""
        return self.predicate is not None
