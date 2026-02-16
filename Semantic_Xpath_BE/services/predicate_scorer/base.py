"""Base interfaces for service-level predicate scorers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ScoringResult:
    """Result of scoring a single node against a predicate."""

    node_id: str
    node_type: str
    node_description: str
    predicate: str
    score: float
    reasoning: str = ""


@dataclass
class BatchScoringResult:
    """Result of batch scoring multiple nodes against a predicate."""

    predicate: str
    results: List[ScoringResult]
    metadata: Dict[str, Any] = None
    token_usage: Dict[str, int] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PredicateScorer(ABC):
    """Abstract scorer interface used by semantic XPath execution."""

    @abstractmethod
    def score_batch(
        self,
        nodes: List[Dict[str, Any]],
        predicate: str,
    ) -> BatchScoringResult:
        pass

    def score_single(
        self,
        node: Dict[str, Any],
        predicate: str,
    ) -> ScoringResult:
        batch_result = self.score_batch([node], predicate)
        return batch_result.results[0] if batch_result.results else None


__all__ = ["PredicateScorer", "ScoringResult", "BatchScoringResult"]
