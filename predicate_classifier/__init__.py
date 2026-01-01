import yaml
from pathlib import Path

from .base import PredicateScorer, ScoringResult, BatchScoringResult
from .llm_scorer import LLMPredicateScorer
from .entailment_scorer import EntailmentPredicateScorer
from .cosine_scorer import CosinePredicateScorer


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_scorer(method: str = None, config: dict = None) -> PredicateScorer:
    """
    Factory function to create the appropriate scorer based on config.
    
    Args:
        method: Scoring method ("llm", "entailment", or "cosine"). 
                If None, uses value from config.yaml.
        config: Optional config dict. If not provided, loads from config.yaml.
    
    Returns:
        PredicateScorer instance
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
            "This is related to {predicate}."
        )
        return EntailmentPredicateScorer(hypothesis_template=hypothesis_template)
    elif method == "cosine":
        cosine_config = config.get("cosine", {})
        predicate_template = cosine_config.get(
            "predicate_template",
            "{predicate}"
        )
        return CosinePredicateScorer(predicate_template=predicate_template)
    else:
        # Default to LLM
        return LLMPredicateScorer()


__all__ = [
    "PredicateScorer", 
    "ScoringResult",
    "BatchScoringResult",
    "LLMPredicateScorer", 
    "EntailmentPredicateScorer",
    "CosinePredicateScorer",
    "get_scorer"
]
