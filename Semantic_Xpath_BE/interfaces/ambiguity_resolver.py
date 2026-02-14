from __future__ import annotations

from typing import Protocol

from common.types import AmbiguityResolveRequest, AmbiguityResolveResult


class AmbiguityResolver(Protocol):
    def resolve(self, req: AmbiguityResolveRequest) -> AmbiguityResolveResult:
        ...
