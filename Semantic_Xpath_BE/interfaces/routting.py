from __future__ import annotations

from typing import Protocol

from common.types import RouteInput, RouteResult


class Routting(Protocol):
    def route(self, input: RouteInput) -> RouteResult:
        ...
