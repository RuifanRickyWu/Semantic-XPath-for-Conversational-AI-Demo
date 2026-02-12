from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict

class VersionSelector(Enum):
    """Version selector type."""
    AT = "at"        # Specific version
    BEFORE = "before"  # Version before (rollback)

class CRUDOperation(Enum):
    """CRUD operation types."""
    READ = "Read"
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    STATE = "State"

@dataclass
class ResolvedVersion:
    """
    Result of version resolution.

    Attributes:
        selector_type: at or before
        semantic_query: Semantic description for version matching (None if using index)
        index: Numeric index (None if unspecified)
        crud_operation: The CRUD operation type
        raw_response: Raw LLM response for debugging
        task_query: The task-relevant portion of the query (without version selection language)
    """
    selector_type: VersionSelector
    semantic_query: Optional[str]
    index: Optional[int]
    task_selector_type: VersionSelector
    task_semantic_query: Optional[str]
    task_index: Optional[int]
    crud_operation: CRUDOperation
    raw_response: str
    task_query: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None

    def to_dict(self) -> dict:
        return {
            "selector_type": self.selector_type.value,
            "semantic_query": self.semantic_query,
            "index": self.index,
            "task_selector_type": self.task_selector_type.value,
            "task_semantic_query": self.task_semantic_query,
            "task_index": self.task_index,
            "crud_operation": self.crud_operation.value,
            "raw_response": self.raw_response,
            "task_query": self.task_query,
            "token_usage": self.token_usage,
        }

    def get_version_selector_string(self) -> str:
        if self.index is None and not self.semantic_query:
            return "state"
        if self.semantic_query:
            if self.semantic_query.startswith(("/", "//")) or self.semantic_query.startswith(("Task", "Version")):
                inner = self.semantic_query
            else:
                inner = f'sem(content ~= "{self.semantic_query}")'
        else:
            inner = f"[{self.index}]"
        return f"{self.selector_type.value}({inner})"

    def get_task_selector_string(self) -> str:
        if self.task_index is None and not self.task_semantic_query:
            return "state"
        if self.task_semantic_query:
            if self.task_semantic_query.startswith(("/", "//")) or self.task_semantic_query.startswith(("Task", "Version")):
                inner = self.task_semantic_query
            else:
                inner = f'sem(content ~= "{self.task_semantic_query}")'
        else:
            inner = f"[{self.task_index}]"
        return f"{self.task_selector_type.value}({inner})"
