"""
Data models for the Dense XPath system.

Contains all dataclasses used throughout the xpath execution pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import xml.etree.ElementTree as ET


# =============================================================================
# Predicate AST Models (Paper Formalization)
# =============================================================================

@dataclass
class AtomicPredicate:
    """
    Atomic predicate φ: atom(content =~ "value")
    
    Paper formalization: Atom(u, φ) evaluates a node's attribute.
    - Local atomic predicates are evaluated from attr(u)
    - The 'content' field aggregates all textual fields of the node
    
    This is the base unit for semantic predicate evaluation.
    """
    field: str  # "content" for aggregated content, or specific field name
    value: str  # The semantic query value, e.g., "museum", "italian"
    
    def __repr__(self):
        return f'atom({self.field} =~ "{self.value}")'
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "atom", "field": self.field, "value": self.value}


# Backward compatibility alias
SemanticCondition = AtomicPredicate


@dataclass
class CompoundPredicate:
    """
    Compound predicate with logical and aggregation operators.
    
    Paper Formalization - Score(u, ψ):
    - ATOM: Atomic predicate Atom(u, φ) - local node content scoring
    - AND: Conjunction ψ₁ ∧ ψ₂ - min{Score(u, ψ₁), Score(u, ψ₂)}
    - OR: Disjunction ψ₁ ∨ ψ₂ - max{Score(u, ψ₁), Score(u, ψ₂)}
    - NOT: Negation ¬ψ - 1 - Score(u, ψ)
    - AGG_EXISTS: Existential aggregation Agg∃ - max over children
    - AGG_PREV: Prevalence aggregation Aggprev - average over children
    
    Key semantic distinction:
    - atom() evaluates the node's OWN content (local)
    - agg_exists()/agg_prev() aggregate scores from CHILDREN (hierarchical)
    """
    operator: str  # "ATOM", "AND", "OR", "NOT", "AGG_EXISTS", "AGG_PREV"
    conditions: List[Union[AtomicPredicate, 'CompoundPredicate']] = field(default_factory=list)
    child_predicate: Optional['CompoundPredicate'] = None  # For AGG_EXISTS/AGG_PREV
    child_type: Optional[str] = None  # Target child node type for hierarchical predicates
    
    def __repr__(self):
        if self.operator == "ATOM":
            return str(self.conditions[0]) if self.conditions else "atom()"
        elif self.operator == "AND":
            return " AND ".join(str(c) for c in self.conditions)
        elif self.operator == "OR":
            return " OR ".join(str(c) for c in self.conditions)
        elif self.operator == "NOT":
            return f"not({self.conditions[0]})" if self.conditions else "not()"
        elif self.operator == "AGG_EXISTS":
            if self.child_type:
                return f"agg_exists({self.child_type}[{self.child_predicate}])"
            return f"agg_exists({self.child_predicate})"
        elif self.operator == "AGG_PREV":
            if self.child_type:
                return f"agg_prev({self.child_type}[{self.child_predicate}])"
            return f"agg_prev({self.child_predicate})"
        return f"{self.operator}({self.conditions})"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"operator": self.operator}
        if self.conditions:
            result["conditions"] = [
                c.to_dict() if hasattr(c, 'to_dict') else str(c) 
                for c in self.conditions
            ]
        if self.child_predicate:
            result["child_predicate"] = self.child_predicate.to_dict()
        if self.child_type:
            result["child_type"] = self.child_type
        return result
    
    def get_all_atomic_values(self) -> List[str]:
        """
        Extract all atomic predicate values for batch scoring.
        
        Paper: Collects all φ values from Atom(u, φ) predicates in the tree.
        """
        values = []
        if self.operator == "ATOM":
            if self.conditions and isinstance(self.conditions[0], AtomicPredicate):
                values.append(self.conditions[0].value)
        elif self.operator in ("AND", "OR"):
            for cond in self.conditions:
                if isinstance(cond, CompoundPredicate):
                    values.extend(cond.get_all_atomic_values())
                elif isinstance(cond, AtomicPredicate):
                    values.append(cond.value)
        elif self.operator == "NOT":
            # Recurse into the negated predicate
            if self.conditions:
                for cond in self.conditions:
                    if isinstance(cond, CompoundPredicate):
                        values.extend(cond.get_all_atomic_values())
                    elif isinstance(cond, AtomicPredicate):
                        values.append(cond.value)
        elif self.operator in ("AGG_EXISTS", "AGG_PREV"):
            if self.child_predicate:
                values.extend(self.child_predicate.get_all_atomic_values())
        return values
    
    # Backward compatibility alias
    get_all_semantic_values = get_all_atomic_values


# =============================================================================
# Index and Position Models
# =============================================================================

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
class NodeItem:
    """
    A node with its traversal context for tracking parent relationships.
    
    Used to preserve parent grouping information during traversal,
    enabling local indexing like Day/POI[2] to return the 2nd POI
    in EACH Day rather than the global 2nd POI.
    """
    node: ET.Element  # The XML element
    path: str  # Tree path, e.g., "Itinerary > Day 1 > POI 2"
    score: float  # Semantic matching score (1.0 if no semantic predicate)
    parent_group_id: int  # ID for grouping by parent node (for local indexing)
    
    def to_tuple(self):
        """Convert to legacy tuple format (node, path, score) for compatibility."""
        return (self.node, self.path, self.score)


@dataclass
class QueryStep:
    """
    Represents a single step in an XPath query.
    
    Each step consists of:
    - node_type: The target node type to match
    - predicate: Optional compound predicate for semantic filtering
    - index: Optional positional index or range
    """
    node_type: str  # e.g., "Itinerary", "Day", "POI", "Restaurant"
    predicate: Optional[CompoundPredicate] = None  # Compound predicate AST
    index: Optional[IndexRange] = None  # positional index or range
    
    # Legacy support: simple string predicate (converted to CompoundPredicate)
    predicate_str: Optional[str] = None  # Original predicate string for display
    
    def __repr__(self):
        parts = [self.node_type]
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
class StepContribution:
    """A single step's contribution to the final score."""
    step_index: int
    predicate_str: str
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "predicate": self.predicate_str,
            "score": self.score
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
            "final_score": self.final_score
        }


@dataclass
class ScoreFusionTrace:
    """Complete score fusion trace across all nodes and steps."""
    per_node_traces: List[NodeFusionTrace] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "per_node": [n.to_dict() for n in self.per_node_traces]
        }


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
            "filtered_nodes": self.filtered_nodes
        }


@dataclass
class ExecutionResult:
    """Result of executing an XPath query."""
    query: str
    matched_nodes: List[MatchedNode]
    execution_log: List[str] = field(default_factory=list)
    scoring_traces: List[Dict[str, Any]] = field(default_factory=list)
    traversal_steps: List[TraversalStep] = field(default_factory=list)
    execution_time_ms: float = 0.0  # Total query execution time in milliseconds
    data_file: str = ""  # Name of the data file used
    
    # Detailed scoring and fusion traces
    score_fusion_trace: Optional[ScoreFusionTrace] = None
    final_filtering_trace: Optional[FinalFilteringTrace] = None


# =============================================================================
# CRUD Operation Models
# =============================================================================

@dataclass
class CRUDExecutionResult:
    """
    Result of executing a CRUD operation.
    
    Extends the basic ExecutionResult with CRUD-specific fields for
    tracking intent classification, reasoning, tree modifications, and versioning.
    """
    # Operation identification
    operation: str  # "READ", "CREATE", "UPDATE", "DELETE"
    user_query: str  # Original natural language query
    full_query: str  # Formatted query, e.g., "Read(/Itinerary/Day/POI[...])"
    
    # Intent classification
    intent_classification: Dict[str, Any] = field(default_factory=dict)
    
    # XPath execution
    xpath_query: str = ""
    execution_result: Optional[ExecutionResult] = None
    
    # LLM reasoning
    reasoner_trace: Dict[str, Any] = field(default_factory=dict)
    
    # For CREATE operations
    insertion_point_trace: Dict[str, Any] = field(default_factory=dict)
    content_generation_trace: Dict[str, Any] = field(default_factory=dict)
    
    # For UPDATE operations
    content_update_trace: Dict[str, Any] = field(default_factory=dict)
    
    # Tree modification results
    modification_trace: Dict[str, Any] = field(default_factory=dict)
    
    # Version management
    tree_version: Optional[int] = None
    tree_path: str = ""
    
    # Status
    success: bool = False
    message: str = ""
    timestamp: str = ""
    
    # Affected nodes
    affected_nodes: List[str] = field(default_factory=list)
    selected_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for tracing."""
        result = {
            "operation": self.operation,
            "user_query": self.user_query,
            "full_query": self.full_query,
            "xpath_query": self.xpath_query,
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp,
            "intent_classification": self.intent_classification,
            "reasoner_trace": self.reasoner_trace,
            "affected_nodes": self.affected_nodes,
            "selected_nodes": self.selected_nodes
        }
        
        # Add operation-specific traces
        if self.operation == "CREATE":
            result["insertion_point_trace"] = self.insertion_point_trace
            result["content_generation_trace"] = self.content_generation_trace
        
        if self.operation == "UPDATE":
            result["content_update_trace"] = self.content_update_trace
        
        if self.operation in ("CREATE", "UPDATE", "DELETE"):
            result["modification_trace"] = self.modification_trace
            result["tree_version"] = self.tree_version
            result["tree_path"] = self.tree_path
        
        return result

