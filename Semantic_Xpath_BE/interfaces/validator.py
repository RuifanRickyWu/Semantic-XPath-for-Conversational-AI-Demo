from __future__ import annotations

from typing import List, Protocol

from common.types import EditOp, TaskState, ValidationResult


class Validator(Protocol):
    def validate_ops(self, state: TaskState, ops: List[EditOp]) -> ValidationResult:
        ...

    def validate_state(self, state: TaskState) -> ValidationResult:
        ...
