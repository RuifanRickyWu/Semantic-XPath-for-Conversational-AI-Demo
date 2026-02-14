from __future__ import annotations

from typing import Protocol

from common.types import CommitResult, ValidationResult, XmlEditResult, XmlOp, XmlState


class TaskStateStore(Protocol):
    def load(self, task_id: str, version_id: str) -> XmlState:
        ...

    def commit(
        self,
        task_id: str,
        base_version_id: str,
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
