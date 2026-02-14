"""
Validator Service - Plan state and edit operation validation (stub).

Validates that:
- Edit operations are structurally valid against the current state
- The resulting state after edits is well-formed

Protocol:
- validate_ops(state: TaskState, ops: List[EditOp]) -> ValidationResult
- validate_state(state: TaskState) -> ValidationResult
"""

from __future__ import annotations

from typing import List

from common.types import EditOp, TaskState, ValidationResult


class ValidatorService:
    """Stub validator service -- not yet implemented."""

    def validate_ops(self, state: TaskState, ops: List[EditOp]) -> ValidationResult:
        raise NotImplementedError(
            "ValidatorService.validate_ops() is not yet implemented. "
            "Will validate edit operations against the current plan state."
        )

    def validate_state(self, state: TaskState) -> ValidationResult:
        raise NotImplementedError(
            "ValidatorService.validate_state() is not yet implemented. "
            "Will validate the plan state structure and constraints."
        )
