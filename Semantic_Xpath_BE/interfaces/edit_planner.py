from __future__ import annotations

from typing import Protocol

from common.types import EditPlanRequest, EditPlanResult


class EditPlanner(Protocol):
    def plan_edits(self, req: EditPlanRequest) -> EditPlanResult:
        ...
