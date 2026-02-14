"""
Ambiguity Resolver Client - GPT-based ambiguous reference resolver (stub).

Resolves vague references in user utterances (e.g. "remove it" -> "remove the museum on Day 2")
by combining conversation context with the current session state.

Protocol: resolve(req: AmbiguityResolveRequest) -> AmbiguityResolveResult

Dependencies (to be wired when implemented):
- clients.openai_client (OpenAIClient)
"""

from __future__ import annotations

from common.types import AmbiguityResolveRequest, AmbiguityResolveResult


class AmbiguityResolverClient:
    """Stub ambiguity resolver client -- not yet implemented."""

    def __init__(self, client=None) -> None:
        self._client = client  # Will be OpenAIClient

    def resolve(self, req: AmbiguityResolveRequest) -> AmbiguityResolveResult:
        raise NotImplementedError(
            "AmbiguityResolverClient.resolve() is not yet implemented. "
            "Will use GPT + conversation context to resolve ambiguous references."
        )
