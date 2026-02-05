"""
Tree Modification module for CRUD operations.

Provides:
- NodeDeleter: Delete nodes from XML trees
- NodeInserter: Insert new nodes into XML trees
- VersionManager: Manage versioned saves of trees
"""

from .base import (
    OperationType,
    OperationResult,
    TreeVersion,
    path_to_xpath,
    find_node_by_path,
    find_parent_and_index
)
from .node_deleter import NodeDeleter
from .node_inserter import NodeInserter
from .version_manager import VersionManager

__all__ = [
    "OperationType",
    "OperationResult",
    "TreeVersion",
    "path_to_xpath",
    "find_node_by_path",
    "find_parent_and_index",
    "NodeDeleter",
    "NodeInserter",
    "VersionManager"
]
