"""
Dense XPath - A semantic XPath-like query execution system.

This module provides tools for executing XPath-like queries against XML trees
with support for semantic predicate matching.

Implements the Semantic XPath framework (v2) with:
- sem(): Local semantic match on node content
- exist(): Existential aggregation (Noisy-OR over children)
- mass(): Prevalence aggregation (Beta-Bernoulli over children)
- AND/OR logical operators
- Bayesian fusion across query steps
- Detailed reasoning traces

Query Syntax:
- /Day[@index='2'] - XPath-style attribute index
- /POI[sem(content =~ "museum")] - local semantic match
- /Day[exist(POI[sem(content =~ "museum")])] - existential over children
- /Day[mass(POI[sem(content =~ "artistic")])] - prevalence over children

Modules:
- models: Data classes for query representation and results
- parser: Query string parsing
- node_utils: XML node utility functions
- index_handler: Positional index operations
- predicate_handler: Semantic predicate scoring
- trace_writer: Logging and trace file writing
- schema_loader: Schema and data file loading
- dense_xpath_executor: Main executor orchestrating all components
"""

# Models
from .models import (
    # Predicate AST
    SemanticCondition,
    CompoundPredicate,
    # Query and Index
    IndexRange,
    NodeItem,
    QueryStep,
    # Results
    MatchedNode,
    TraversalStep,
    ExecutionResult,
    # Fusion traces
    StepContribution,
    NodeFusionTrace,
    BayesianFusionTrace,
    FinalFilteringTrace,
)

# Components
from .parser import QueryParser, get_parser
from .node_utils import NodeUtils
from .index_handler import IndexHandler
from .predicate_handler import PredicateHandler
from .trace_writer import TraceWriter

# Schema loading
from .schema_loader import (
    load_schema,
    get_data_path,
    get_schema_info,
    get_schema_summary_for_prompt,
    list_available_schemas,
    list_available_data_files
)

# Main executor
from .dense_xpath_executor import DenseXPathExecutor

__all__ = [
    # Predicate AST
    "SemanticCondition",
    "CompoundPredicate",
    # Query and Index Models
    "IndexRange",
    "NodeItem",
    "QueryStep", 
    # Result Models
    "MatchedNode",
    "TraversalStep",
    "ExecutionResult",
    # Fusion Trace Models
    "StepContribution",
    "NodeFusionTrace",
    "BayesianFusionTrace",
    "FinalFilteringTrace",
    # Components
    "QueryParser",
    "get_parser",
    "NodeUtils",
    "IndexHandler",
    "PredicateHandler",
    "TraceWriter",
    # Schema loading
    "load_schema",
    "get_data_path",
    "get_schema_info",
    "get_schema_summary_for_prompt",
    "list_available_schemas",
    "list_available_data_files",
    # Main executor
    "DenseXPathExecutor",
]
