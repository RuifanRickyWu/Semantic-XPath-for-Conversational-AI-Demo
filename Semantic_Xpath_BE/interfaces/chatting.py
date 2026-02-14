from __future__ import annotations

from typing import Protocol

from common.types import RealizeRequest


class Chatting(Protocol):
    def realize(self, req: RealizeRequest) -> str:
        ...
