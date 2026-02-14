"""
Retriever Client - Embedding-based node retrieval (stub).

Will use the TAS-B client to compute cosine similarity between
the user utterance embedding and plan node text embeddings.

Dependencies (to be wired when implemented):
- clients.tas_b_client (TASBClient)
"""

from __future__ import annotations

from common.types import RetrieveRequest, RetrieveResult


class RetrieverClient:
    """Stub retriever client -- not yet implemented."""

    def __init__(self, client=None) -> None:
        self._client = client  # Will be TASBClient

    def retrieve(self, req: RetrieveRequest) -> RetrieveResult:
        raise NotImplementedError(
            "RetrieverClient.retrieve() is not yet implemented. "
            "Will use TAS-B embeddings for cosine similarity retrieval."
        )
