"""
Retriever Service - Semantic search over plan tree nodes (stub).

Combines structural XPath traversal with embedding-based similarity
to find relevant plan nodes for a given user utterance.

Will use the TAS-B client (clients.tas_b_client.TASBClient) to compute
cosine similarity between user utterance embeddings and plan node text
embeddings.

Protocol: retrieve(req: RetrieveRequest) -> RetrieveResult

Merged from clients/retriever_client.py + services/intent_handling/retriever_service.py.
"""

from __future__ import annotations

from common.types import RetrieveRequest, RetrieveResult


class RetrieverService:
    """Stub retriever service -- not yet implemented."""

    def __init__(self, client=None) -> None:
        self._client = client  # Will be TASBClient

    def retrieve(self, req: RetrieveRequest) -> RetrieveResult:
        raise NotImplementedError(
            "RetrieverService.retrieve() is not yet implemented. "
            "Will combine structural XPath traversal with TAS-B embedding similarity."
        )
