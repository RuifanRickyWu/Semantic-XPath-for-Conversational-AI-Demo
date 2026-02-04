"""
Experiment Infrastructure - Execute experiments across query sessions.

Contains:
- ExperimentRunner: Semantic XPath based experiment runner
- in_context: In-context LLM evaluation module
"""

from .experiment_runner import ExperimentRunner

__all__ = ["ExperimentRunner"]
