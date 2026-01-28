"""
Content Creator module for CRUD operations.

DEPRECATED: This module has been replaced by the new CRUD handlers in crud/.
- NodeCreator -> crud.CreateHandler
- NodeUpdater -> crud.UpdateHandler

The new handlers consolidate relevance reasoning with content generation
into single LLM calls, reducing the number of LLM calls per operation.

These classes are kept for backward compatibility but may be removed in
a future version. Please migrate to the new crud handlers.

Provides:
- NodeCreator: Generate new node content using LLM
- NodeUpdater: Update existing node content using LLM
"""

from .base import (
    ContentGenerationResult,
    ContentUpdateResult,
    NODE_SCHEMAS,
    dict_to_xml_element,
    xml_element_to_dict
)
from .node_creator import NodeCreator
from .node_updater import NodeUpdater

__all__ = [
    "ContentGenerationResult",
    "ContentUpdateResult",
    "NODE_SCHEMAS",
    "dict_to_xml_element",
    "xml_element_to_dict",
    "NodeCreator",
    "NodeUpdater"
]
