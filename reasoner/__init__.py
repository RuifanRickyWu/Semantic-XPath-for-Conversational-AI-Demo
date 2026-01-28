"""
Reasoner module for LLM-based node selection and insertion point finding.

DEPRECATED: This module has been replaced by the new CRUD handlers in crud/.
- NodeReasoner -> crud.ReadHandler, crud.DeleteHandler, crud.UpdateHandler
- InsertionReasoner -> crud.CreateHandler

The new handlers consolidate relevance reasoning with task-specific processing
into single LLM calls, reducing the number of LLM calls per operation.

These classes are kept for backward compatibility but may be removed in
a future version. Please migrate to the new crud handlers.

Provides:
- NodeReasoner: Selects relevant nodes from semantic XPath candidates
- InsertionReasoner: Finds optimal insertion points for Create operations
"""

from .base import (
    ReasonerDecision,
    NodeReasoningResult,
    BatchReasoningResult,
    InsertionPoint,
    ReasonerBase
)
from .node_reasoner import NodeReasoner
from .insertion_reasoner import InsertionReasoner

__all__ = [
    "ReasonerDecision",
    "NodeReasoningResult",
    "BatchReasoningResult",
    "InsertionPoint",
    "ReasonerBase",
    "NodeReasoner",
    "InsertionReasoner"
]
