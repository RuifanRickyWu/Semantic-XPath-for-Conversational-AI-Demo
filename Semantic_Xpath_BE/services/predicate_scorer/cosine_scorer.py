"""Cosine similarity-based predicate scorer using embeddings."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BatchScoringResult, PredicateScorer, ScoringResult


class CosinePredicateScorer(PredicateScorer):
    """Score node descriptions against predicates using embedding cosine similarity."""

    def __init__(
        self,
        predicate_template: str = "{predicate}",
        client: Optional[Any] = None,
        traces_path: Optional[Path] = None,
    ) -> None:
        self._predicate_template = predicate_template
        self._client = client
        self._traces_path = traces_path

    def _get_client(self):
        if self._client is None:
            from clients.tas_b_client import get_tas_b_client
            self._client = get_tas_b_client()
        return self._client

    def score_batch(
        self,
        nodes: List[Dict[str, Any]],
        predicate: str,
    ) -> BatchScoringResult:
        if not nodes:
            return BatchScoringResult(predicate=predicate, results=[])

        predicate_text = self._predicate_template.format(predicate=predicate)
        descriptions = [
            n.get("description", "") or n.get("name", "") or str(n.get("type", "?"))
            for n in nodes
        ]

        client = self._get_client()
        results = []
        for i, (node, desc) in enumerate(zip(nodes, descriptions)):
            sim = client.similarity(desc, predicate_text)
            score = (sim + 1.0) / 2.0
            score = max(0.0, min(1.0, float(score)))
            results.append(
                ScoringResult(
                    node_id=str(node.get("id", i)),
                    node_type=str(node.get("type", "?")),
                    node_description=str(desc),
                    predicate=predicate,
                    score=score,
                )
            )

        return BatchScoringResult(predicate=predicate, results=results)
