from __future__ import annotations

from typing import Protocol

from common.types import RetrieveRequest, RetrieveResult


class Retriever(Protocol):
    def retrieve(self, req: RetrieveRequest) -> RetrieveResult:
        ...
