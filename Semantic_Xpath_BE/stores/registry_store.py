"""
Registry Store - In-memory task/version registry.

Manages task creation, version switching, and task/version listing.
"""

from __future__ import annotations

from typing import Dict, List

from common.types import RegistryApplyRequest, RegistryApplyResult


class RegistryStore:
    """Simple in-memory task registry."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, object]] = {}
        self._task_counter = 0

    def apply(self, req: RegistryApplyRequest) -> RegistryApplyResult:
        if req.action == "CREATE_TASK":
            self._task_counter += 1
            task_id = f"t{self._task_counter}"
            version_id = "v1"
            self._tasks[task_id] = {
                "active_version_id": version_id,
                "versions": [version_id],
            }
            return RegistryApplyResult(
                active_task_id=task_id,
                active_version_id=version_id,
                created_task_id=task_id,
                created_version_id=version_id,
            )

        if req.action == "SWITCH_VERSION" and req.task_id and req.version_id:
            task = self._tasks.get(req.task_id)
            if task and req.version_id in task["versions"]:
                task["active_version_id"] = req.version_id
            return RegistryApplyResult(
                active_task_id=req.task_id,
                active_version_id=req.version_id,
            )

        return RegistryApplyResult()
