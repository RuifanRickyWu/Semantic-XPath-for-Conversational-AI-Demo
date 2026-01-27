"""
Version Resolver Module - First LLM call in 2-stage semantic XPath processing.

Determines:
1. Version selector type (at/before)
2. Semantic query for version matching (or index for explicit version reference)
3. CRUD operation type (Read/Create/Update/Delete)
"""

from .version_resolver import (
    VersionResolver,
    VersionSelector,
    ResolvedVersion,
)

# Re-export CRUDOperation from xpath_query_generation for convenience
from xpath_query_generation import CRUDOperation

__all__ = [
    "VersionResolver",
    "VersionSelector", 
    "ResolvedVersion",
    "CRUDOperation",
]
