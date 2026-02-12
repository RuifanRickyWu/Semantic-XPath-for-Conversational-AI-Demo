"""
Core module - Flask resource and service orchestrator.
"""

from .semantic_xpath_resource import semantic_xpath_bp
from .semantic_xpath_service import SemanticXpathService

__all__ = ["semantic_xpath_bp", "SemanticXpathService"]
