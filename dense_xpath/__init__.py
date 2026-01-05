"""
Dense XPath - A semantic XPath-like query execution system.

This module provides tools for executing XPath-like queries against XML trees
with support for semantic predicate matching.

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
    IndexRange,
    QueryStep,
    MatchedNode,
    TraversalStep,
    ExecutionResult
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
    list_available_schemas,
    list_available_data_files
)

# Main executor
from .dense_xpath_executor import DenseXPathExecutor

__all__ = [
    # Models
    "IndexRange",
    "QueryStep", 
    "MatchedNode",
    "TraversalStep",
    "ExecutionResult",
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
    "list_available_schemas",
    "list_available_data_files",
    # Main executor
    "DenseXPathExecutor",
]
