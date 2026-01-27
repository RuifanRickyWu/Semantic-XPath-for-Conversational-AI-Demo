"""
Base classes for the Reasoner module.

Provides base classes and data structures for LLM-based reasoning
over candidate nodes from semantic XPath results.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ReasonerDecision(Enum):
    """Decision made by the reasoner for a node."""
    RELEVANT = "RELEVANT"
    NOT_RELEVANT = "NOT_RELEVANT"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class NodeReasoningResult:
    """
    Result of reasoning about a single node.
    
    Attributes:
        node_id: Identifier for the node
        node_path: Tree path to the node
        node_data: The node's data dictionary
        decision: Whether the node is relevant
        confidence: Confidence in the decision (0.0 to 1.0)
        reasoning: LLM's reasoning explanation
    """
    node_id: str
    node_path: str
    node_data: Dict[str, Any]
    decision: ReasonerDecision
    confidence: float = 0.0
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.
        
        Note: Uses tree_path and node as keys (not node_path/node_data)
        for compatibility with InsertionReasoner which expects these field names.
        """
        return {
            "node_id": self.node_id,
            "tree_path": self.node_path,  # InsertionReasoner expects tree_path
            "node": self.node_data,        # InsertionReasoner expects node
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class BatchReasoningResult:
    """
    Result of reasoning over a batch of nodes.
    
    Attributes:
        user_query: The original user query
        results: List of reasoning results for each node
        selected_nodes: Nodes that were deemed relevant
        metadata: Additional metadata (timing, batch info, etc.)
    """
    user_query: str
    results: List[NodeReasoningResult] = field(default_factory=list)
    selected_nodes: List[NodeReasoningResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_query": self.user_query,
            "total_candidates": len(self.results),
            "selected_count": len(self.selected_nodes),
            "results": [r.to_dict() for r in self.results],
            "selected_nodes": [n.to_dict() for n in self.selected_nodes],
            "metadata": self.metadata
        }


@dataclass
class InsertionPoint:
    """
    Represents a point in the tree where a new node should be inserted.
    
    Attributes:
        parent_path: Path to the parent node
        position: Index position among siblings (0-based, -1 for append)
        sibling_context: Information about surrounding siblings
        reasoning: LLM's reasoning for choosing this insertion point
    """
    parent_path: str
    position: int = -1  # -1 means append at end
    sibling_context: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "parent_path": self.parent_path,
            "position": self.position,
            "sibling_context": self.sibling_context,
            "reasoning": self.reasoning
        }


class ReasonerBase:
    """Base class for reasoners."""
    
    def reason(self, nodes: List[Dict[str, Any]], user_query: str) -> BatchReasoningResult:
        """
        Apply reasoning to select relevant nodes.
        
        Args:
            nodes: List of candidate nodes from semantic XPath
            user_query: The original user query
            
        Returns:
            BatchReasoningResult with decisions for each node
        """
        raise NotImplementedError("Subclasses must implement reason()")
