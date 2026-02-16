"""Entailment-based predicate scorer using NLI model."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BatchScoringResult, PredicateScorer, ScoringResult


class EntailmentPredicateScorer(PredicateScorer):
    """Score node descriptions against predicates using NLI entailment."""

    def __init__(
        self,
        hypothesis_template: str = "This is related to {predicate}.",
        client: Optional[Any] = None,
        traces_path: Optional[Path] = None,
    ) -> None:
        self._hypothesis_template = hypothesis_template
        self._client = client
        self._traces_path = traces_path

    def _get_client(self):
        if self._client is None:
            from clients.bart_client import get_bart_client
            self._client = get_bart_client()
        return self._client

    def score_batch(
        self,
        nodes: List[Dict[str, Any]],
        predicate: str,
    ) -> BatchScoringResult:
        if not nodes:
            return BatchScoringResult(predicate=predicate, results=[])

        descriptions = [
            n.get("description", "") or n.get("name", "") or str(n.get("type", "?"))
            for n in nodes
        ]

        client = self._get_client()
        scores = client.batch_entailment_scores(
            descriptions,
            predicate,
            hypothesis_template=self._hypothesis_template,
        )

        results = []
        for i, node in enumerate(nodes):
            score = scores[i] if i < len(scores) else 0.5
            score = max(0.0, min(1.0, float(score)))
            results.append(
                ScoringResult(
                    node_id=str(node.get("id", i)),
                    node_type=str(node.get("type", "?")),
                    node_description=str(node.get("description", "")),
                    predicate=predicate,
                    score=score,
                )
            )

        return BatchScoringResult(predicate=predicate, results=results)
