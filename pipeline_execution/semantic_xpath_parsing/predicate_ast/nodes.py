"""
Predicate AST Node Types - Typed hierarchy for semantic XPath predicates.

Paper Formalization - Score(u, ψ):
    AtomPredicate:       Atom(u, φ) - local node content scoring
    AndPredicate:        ψ₁ ∧ ψ₂   - min{Score(u, ψ₁), Score(u, ψ₂)}
    OrPredicate:         ψ₁ ∨ ψ₂   - max{Score(u, ψ₁), Score(u, ψ₂)}
    NotPredicate:        ¬ψ         - 1 - Score(u, ψ)
    AggExistsPredicate:  Agg∃       - max over children/descendants
    AggPrevPredicate:    Aggprev    - average over children/descendants
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class PredicateNode(ABC):
    """Base class for all predicate AST nodes."""

    @abstractmethod
    def get_all_atomic_values(self) -> List[str]:
        """Extract all atomic predicate values for batch scoring."""
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for tracing."""
        ...

    # Backward-compat alias used by some callers
    def get_all_semantic_values(self) -> List[str]:
        return self.get_all_atomic_values()


# =============================================================================
# Base-case predicates
# =============================================================================

@dataclass
class AtomPredicate(PredicateNode):
    """
    atom(field =~ "value") - local semantic match on a node's content.

    Paper: Atom(u, φ) evaluated from attr(u).
    """
    field: str   # "content" for aggregated content, or specific field name
    value: str   # The semantic query value, e.g., "museum"

    def get_all_atomic_values(self) -> List[str]:
        return [self.value]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "atom", "field": self.field, "value": self.value}

    def __repr__(self) -> str:
        return f'atom({self.field} =~ "{self.value}")'


@dataclass
class AggExistsPredicate(PredicateNode):
    """
    agg_exists([axis::]ChildType[inner]) - existential aggregation (max).

    Paper: Agg∃(A) = max A
    """
    inner: PredicateNode
    child_type: Optional[str] = None   # e.g. "POI", None = all children
    child_axis: str = "child"          # "child" | "desc"

    def get_all_atomic_values(self) -> List[str]:
        return self.inner.get_all_atomic_values()

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "operator": "AGG_EXISTS",
            "child_predicate": self.inner.to_dict(),
        }
        if self.child_type:
            result["child_type"] = self.child_type
        if self.child_axis != "child":
            result["child_axis"] = self.child_axis
        return result

    def __repr__(self) -> str:
        axis = f"{self.child_axis}::" if self.child_axis != "child" else ""
        if self.child_type:
            return f"agg_exists({axis}{self.child_type}[{self.inner}])"
        return f"agg_exists({self.inner})"


@dataclass
class AggPrevPredicate(PredicateNode):
    """
    agg_prev([axis::]ChildType[inner]) - prevalence aggregation (avg).

    Paper: Aggprev(A) = (1/|A|)∑A
    """
    inner: PredicateNode
    child_type: Optional[str] = None
    child_axis: str = "child"

    def get_all_atomic_values(self) -> List[str]:
        return self.inner.get_all_atomic_values()

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "operator": "AGG_PREV",
            "child_predicate": self.inner.to_dict(),
        }
        if self.child_type:
            result["child_type"] = self.child_type
        if self.child_axis != "child":
            result["child_axis"] = self.child_axis
        return result

    def __repr__(self) -> str:
        axis = f"{self.child_axis}::" if self.child_axis != "child" else ""
        if self.child_type:
            return f"agg_prev({axis}{self.child_type}[{self.inner}])"
        return f"agg_prev({self.inner})"


# =============================================================================
# Logical combinators (recursive)
# =============================================================================

@dataclass
class AndPredicate(PredicateNode):
    """
    ψ₁ AND ψ₂ AND ... - conjunction.

    Paper: Score(u, ψ₁ ∧ ψ₂) = min{Score(u, ψ₁), Score(u, ψ₂)}
    """
    children: List[PredicateNode] = field(default_factory=list)

    def get_all_atomic_values(self) -> List[str]:
        values: List[str] = []
        for child in self.children:
            values.extend(child.get_all_atomic_values())
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": "AND",
            "conditions": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return " AND ".join(str(c) for c in self.children)


@dataclass
class OrPredicate(PredicateNode):
    """
    ψ₁ OR ψ₂ OR ... - disjunction.

    Paper: Score(u, ψ₁ ∨ ψ₂) = max{Score(u, ψ₁), Score(u, ψ₂)}
    """
    children: List[PredicateNode] = field(default_factory=list)

    def get_all_atomic_values(self) -> List[str]:
        values: List[str] = []
        for child in self.children:
            values.extend(child.get_all_atomic_values())
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": "OR",
            "conditions": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return " OR ".join(str(c) for c in self.children)


@dataclass
class NotPredicate(PredicateNode):
    """
    not(ψ) - negation.

    Paper: Score(u, ¬ψ) = 1 - Score(u, ψ)
    """
    child: PredicateNode = field(default=None)  # type: ignore[assignment]

    def get_all_atomic_values(self) -> List[str]:
        return self.child.get_all_atomic_values() if self.child else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": "NOT",
            "condition": self.child.to_dict() if self.child else {},
        }

    def __repr__(self) -> str:
        return f"not({self.child})"
