from __future__ import annotations

from typing import Protocol

from common.types import CommitResult, ValidationResult, XmlEditResult, XmlOp, XmlState


class XmlStateManager(Protocol):
    """Protocol for XML state management.

    Implementations handle loading, committing, applying edit operations,
    and validating XML plan state.
    """

    def load(self, task_id: str | None = None, version_id: str | None = None) -> XmlState:
        ...

    def commit(
        self,
        task_id: str | None,
        base_version_id: str | None,
        ops: list[XmlOp],
        commit_message: str | None = None,
    ) -> CommitResult:
        ...

    def apply_ops(self, xml_str: str, ops: list[XmlOp]) -> XmlEditResult:
        ...

    def validate(self, xml_str: str, schema: str | None = None) -> ValidationResult:
        ...

    def load_schema(self, schema_name: str) -> dict:
        ...

    def sync_schema(self, xml_str: str, schema_name: str) -> dict:
        ...
