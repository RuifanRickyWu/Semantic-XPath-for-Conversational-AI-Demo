"""
Semantic XPath Execution - Core query execution engine with semantic scoring.

Modules:
- execution_models: Data classes for current and legacy-compatible result models
- semantic_xpath_executor: Main executor orchestrating all components
- predicate_handler: Semantic predicate scoring (isinstance dispatch)
- index_handler: Positional index operations
- predicate_scorer: Scoring backends (LLM, entailment, cosine)
"""

# Execution models
from .execution_models import (
    NodeItem,
    MatchedNode,
    TraversalStep,
    PathSegment,
    RetrievalDetail,
    ExecutionResult,
    StepContribution,
    NodeFusionTrace,
    ScoreFusionTrace,
    FinalFilteringTrace,
)

# Components
from .index_handler import IndexHandler
from .predicate_handler import PredicateHandler

# Main executor
from .semantic_xpath_executor import SemanticXPathExecutor

# Re-export parsing types for backward compatibility
from domain.semantic_xpath.parsing import (
    QueryParser,
    get_parser,
    QueryStep,
    IndexRange,
    PredicateNode,
    AtomPredicate,
    AggExistsPredicate,
    AggPrevPredicate,
    AndPredicate,
    OrPredicate,
    NotPredicate,
)

# Re-export node operations for backward compatibility
from domain.semantic_xpath.node_ops import NodeUtils

__all__ = [
    # Execution models
    "NodeItem",
    "MatchedNode",
    "TraversalStep",
    "PathSegment",
    "RetrievalDetail",
    "ExecutionResult",
    "StepContribution",
    "NodeFusionTrace",
    "ScoreFusionTrace",
    "FinalFilteringTrace",
    # Components
    "IndexHandler",
    "PredicateHandler",
    # Main executor
    "SemanticXPathExecutor",
    # Re-exported parsing types
    "QueryParser",
    "get_parser",
    "QueryStep",
    "IndexRange",
    "PredicateNode",
    "AtomPredicate",
    "AggExistsPredicate",
    "AggPrevPredicate",
    "AndPredicate",
    "OrPredicate",
    "NotPredicate",
    # Re-exported node ops
    "NodeUtils",
]
