from __future__ import annotations

from typing import Protocol

from common.types import RegistryApplyRequest, RegistryApplyResult


class TaskRegistry(Protocol):
    def apply(self, req: RegistryApplyRequest) -> RegistryApplyResult:
        ...
