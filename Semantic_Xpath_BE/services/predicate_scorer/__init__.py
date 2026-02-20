"""Service-level predicate scorer implementations and factory."""

import yaml
from pathlib import Path

from .base import PredicateScorer, ScoringResult, BatchScoringResult
from .llm_scorer import LLMPredicateScorer
from .entailment_scorer import EntailmentPredicateScorer
from .cosine_scorer import CosinePredicateScorer


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_scorer(method: str = None, config: dict = None, traces_path: Path = None, client=None) -> PredicateScorer:
    """Create the scorer selected by config or explicit method.

    Args:
        client: Pre-loaded scoring client (e.g. BartNLIClient). When provided
                the scorer skips its own lazy-loading and reuses this instance.
    """
    if config is None:
        config = load_config()

    executor_config = config.get("xpath_executor", {})

    if method is None:
        method = executor_config.get("scoring_method", "llm")

    if method == "entailment":
        entailment_config = config.get("entailment", {})
        hypothesis_template = entailment_config.get(
            "hypothesis_template",
            "This is related to {predicate}.",
        )
        return EntailmentPredicateScorer(
            hypothesis_template=hypothesis_template,
            traces_path=traces_path,
            client=client,
        )
    if method == "cosine":
        cosine_config = config.get("cosine", {})
        predicate_template = cosine_config.get(
            "predicate_template",
            "{predicate}",
        )
        return CosinePredicateScorer(
            predicate_template=predicate_template,
            traces_path=traces_path,
        )

    return LLMPredicateScorer(traces_path=traces_path)


__all__ = [
    "PredicateScorer",
    "ScoringResult",
    "BatchScoringResult",
    "LLMPredicateScorer",
    "EntailmentPredicateScorer",
    "CosinePredicateScorer",
    "get_scorer",
]
