"""
Edit Planner Service - GPT-based edit operation generator (stub).

Takes a user utterance, the current plan state, and retrieved nodes,
and produces a list of edit operations (AddNode, DeleteNode, etc.).

Protocol: plan_edits(req: EditPlanRequest) -> EditPlanResult

Dependencies (to be wired when implemented):
- clients.openai_client (OpenAIClient)

Migrated from clients/edit_planner_client.py.
"""

from __future__ import annotations

from common.types import EditPlanRequest, EditPlanResult


class EditPlannerService:
    """Stub edit planner service -- not yet implemented."""

    def __init__(self, client=None) -> None:
        self._client = client  # Will be OpenAIClient

    def plan_edits(self, req: EditPlanRequest) -> EditPlanResult:
        raise NotImplementedError(
            "EditPlannerService.plan_edits() is not yet implemented. "
            "Will use GPT to generate edit operations from user intent + retrieved nodes."
        )
