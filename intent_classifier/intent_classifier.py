"""
LLM-based Intent Classifier (DEPRECATED).

This module is deprecated. Intent classification is now integrated directly
into the XPath Query Generator (xpath_query_generation.XPathQueryGenerator),
which outputs CRUD-prefixed queries in a single LLM call.

This class is kept for backward compatibility but is no longer used in the
main pipeline.

See xpath_query_generation.XPathQueryGenerator for the unified approach.
"""

import logging
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base import IntentClassifierBase, ClassifiedIntent, IntentType


logger = logging.getLogger(__name__)


class IntentClassifier(IntentClassifierBase):
    """
    LLM-based intent classifier for CRUD operations (DEPRECATED).
    
    This class is deprecated. Intent classification is now handled by
    xpath_query_generation.XPathQueryGenerator in a single LLM call.
    
    Kept for backward compatibility only.
    """
    
    def __init__(self, client=None):
        """
        Initialize the intent classifier.
        
        Args:
            client: Optional OpenAI client (no longer used).
        """
        logger.warning(
            "IntentClassifier is deprecated. "
            "Use XPathQueryGenerator.generate_and_parse() instead."
        )
    
    def classify(self, user_query: str) -> ClassifiedIntent:
        """
        Classify a user query into a CRUD intent (DEPRECATED).
        
        This method now performs simple keyword-based classification
        as a fallback. The main pipeline uses XPathQueryGenerator instead.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            ClassifiedIntent with operation type and extracted details
        """
        return self._fallback_classify(user_query)
    
    def _fallback_classify(self, query: str) -> ClassifiedIntent:
        """
        Fallback classification using keyword matching.
        """
        query_lower = query.lower()
        
        # Check for delete indicators
        delete_keywords = ["remove", "delete", "drop", "cancel", "eliminate", "get rid of"]
        if any(kw in query_lower for kw in delete_keywords):
            return ClassifiedIntent(
                intent=IntentType.DELETE,
                xpath_hint=query,
                confidence=0.6
            )
        
        # Check for create indicators
        create_keywords = ["add", "create", "insert", "new", "schedule", "put", "include"]
        if any(kw in query_lower for kw in create_keywords):
            return ClassifiedIntent(
                intent=IntentType.CREATE,
                xpath_hint=query,
                confidence=0.6
            )
        
        # Check for update indicators
        update_keywords = ["change", "update", "modify", "edit", "move", "reschedule", "replace", "set"]
        if any(kw in query_lower for kw in update_keywords):
            return ClassifiedIntent(
                intent=IntentType.UPDATE,
                xpath_hint=query,
                confidence=0.6
            )
        
        # Default to READ
        return ClassifiedIntent(
            intent=IntentType.READ,
            xpath_hint=query,
            confidence=0.5
        )
