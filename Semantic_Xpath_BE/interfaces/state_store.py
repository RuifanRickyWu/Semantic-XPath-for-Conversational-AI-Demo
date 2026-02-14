from __future__ import annotations

from typing import Protocol

from common.types import CommitRequest, CommitResult, TaskState


class TaskStateStore(Protocol):
    def load(self, task_id: str, version_id: str) -> TaskState:
        ...

    def commit(self, req: CommitRequest) -> CommitResult:
        ...
