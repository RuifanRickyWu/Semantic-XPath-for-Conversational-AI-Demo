"""
Retriever Service - Semantic search over plan tree nodes (stub).

Combines structural XPath traversal with embedding-based similarity
to find relevant plan nodes for a given user utterance.

Will use RetrieverClient for embedding-based retrieval.

Protocol: retrieve(req: RetrieveRequest) -> RetrieveResult
"""

from __future__ import annotations

from common.types import RetrieveRequest, RetrieveResult


class RetrieverService:
    """Stub retriever service -- not yet implemented."""

    def retrieve(self, req: RetrieveRequest) -> RetrieveResult:
        raise NotImplementedError(
            "RetrieverService.retrieve() is not yet implemented. "
            "Will combine structural XPath traversal with TAS-B embedding similarity."
        )
