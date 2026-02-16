from pathlib import Path
from typing import Callable, Optional

from .base import PredicateScorer, ScoringResult, BatchScoringResult

ScorerFactory = Callable[[str, dict, Path], PredicateScorer]
_scorer_factory: Optional[ScorerFactory] = None


def register_scorer_factory(factory: ScorerFactory) -> None:
    """Register an external scorer factory for domain executor usage."""
    global _scorer_factory
    _scorer_factory = factory


def get_scorer(method: str = None, config: dict = None, traces_path: Path = None) -> PredicateScorer:
    """
    Resolve a scorer via registered factory, falling back to service defaults.

    Domain keeps only scorer contracts; concrete scorer creation lives in service.
    """
    if _scorer_factory is not None:
        return _scorer_factory(method, config, traces_path)

    from services.predicate_scorer import (
        get_scorer as service_get_scorer,
    )

    return service_get_scorer(method=method, config=config, traces_path=traces_path)


__all__ = [
    "PredicateScorer",
    "ScoringResult",
    "BatchScoringResult",
    "register_scorer_factory",
    "get_scorer",
]
