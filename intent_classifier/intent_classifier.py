"""
LLM-based Intent Classifier.

Uses an LLM to classify natural language queries into CRUD operations
(Create, Read, Update, Delete).
"""

import json
import logging
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from .base import IntentClassifierBase, ClassifiedIntent, IntentType


logger = logging.getLogger(__name__)


class IntentClassifier(IntentClassifierBase):
    """
    LLM-based intent classifier for CRUD operations.
    
    Analyzes user queries to determine:
    1. Operation type (CREATE, READ, UPDATE, DELETE)
    2. XPath hint for query generation
    3. Operation-specific details
    """
    
    PROMPT_PATH = Path(__file__).parent.parent / "storage" / "prompts" / "intent_classifier.txt"
    
    def __init__(self, client=None):
        """
        Initialize the intent classifier.
        
        Args:
            client: Optional OpenAI client. If not provided, one will be created lazily.
        """
        self._client = client
        self._system_prompt = None
    
    @property
    def client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = get_client()
        return self._client
    
    @property
    def system_prompt(self) -> str:
        """Lazy load the system prompt from file."""
        if self._system_prompt is None:
            with open(self.PROMPT_PATH, "r") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    def classify(self, user_query: str) -> ClassifiedIntent:
        """
        Classify a user query into a CRUD intent.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            ClassifiedIntent with operation type and extracted details
        """
        prompt = f"User Query: {user_query}"
        
        try:
            response = self.client.complete(
                prompt,
                system_prompt=self.system_prompt,
                temperature=0.1,
                max_tokens=512
            )
            
            return self._parse_response(response, user_query)
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            # Default to READ on error
            return ClassifiedIntent(
                intent=IntentType.READ,
                xpath_hint=user_query,
                confidence=0.0,
                raw_response=str(e)
            )
    
    def _parse_response(self, response: str, original_query: str) -> ClassifiedIntent:
        """
        Parse LLM response into ClassifiedIntent.
        
        Expected JSON format:
        {
            "intent": "READ|CREATE|UPDATE|DELETE",
            "xpath_hint": "...",
            "operation_details": {...},
            "confidence": 0.95
        }
        """
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                # Parse intent type
                intent_str = parsed.get("intent", "READ").upper()
                try:
                    intent = IntentType(intent_str)
                except ValueError:
                    intent = IntentType.READ
                
                return ClassifiedIntent(
                    intent=intent,
                    xpath_hint=parsed.get("xpath_hint", original_query),
                    operation_details=parsed.get("operation_details", {}),
                    confidence=float(parsed.get("confidence", 0.8)),
                    raw_response=response
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse intent response: {e}")
        
        # Fallback: simple keyword-based classification
        return self._fallback_classify(original_query, response)
    
    def _fallback_classify(self, query: str, raw_response: str) -> ClassifiedIntent:
        """
        Fallback classification using keyword matching.
        
        Used when LLM response parsing fails.
        """
        query_lower = query.lower()
        
        # Check for delete indicators
        delete_keywords = ["remove", "delete", "drop", "cancel", "eliminate", "get rid of"]
        if any(kw in query_lower for kw in delete_keywords):
            return ClassifiedIntent(
                intent=IntentType.DELETE,
                xpath_hint=query,
                confidence=0.6,
                raw_response=raw_response
            )
        
        # Check for create indicators
        create_keywords = ["add", "create", "insert", "new", "schedule", "put", "include"]
        if any(kw in query_lower for kw in create_keywords):
            return ClassifiedIntent(
                intent=IntentType.CREATE,
                xpath_hint=query,
                confidence=0.6,
                raw_response=raw_response
            )
        
        # Check for update indicators
        update_keywords = ["change", "update", "modify", "edit", "move", "reschedule", "replace", "set"]
        if any(kw in query_lower for kw in update_keywords):
            return ClassifiedIntent(
                intent=IntentType.UPDATE,
                xpath_hint=query,
                confidence=0.6,
                raw_response=raw_response
            )
        
        # Default to READ
        return ClassifiedIntent(
            intent=IntentType.READ,
            xpath_hint=query,
            confidence=0.5,
            raw_response=raw_response
        )
