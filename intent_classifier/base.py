"""
Base classes and enums for intent classification.

Defines the IntentType enum and ClassifiedIntent dataclass used throughout
the CRUD operations system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional


class IntentType(Enum):
    """Types of operations that can be performed on the tree."""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class ClassifiedIntent:
    """
    Result of intent classification.
    
    Attributes:
        intent: The classified operation type
        xpath_hint: Extracted hint for XPath query generation (e.g., "museums", "day 2")
        operation_details: Extra information for Create/Update operations
            - For CREATE: new_content hints, insertion context
            - For UPDATE: fields to update, new values
        confidence: Classification confidence score (0.0 to 1.0)
        raw_response: Raw LLM response for debugging
    """
    intent: IntentType
    xpath_hint: str = ""
    operation_details: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_response: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for tracing."""
        return {
            "intent": self.intent.value,
            "xpath_hint": self.xpath_hint,
            "operation_details": self.operation_details,
            "confidence": self.confidence
        }
    
    def format_full_query(self, xpath_query: str) -> str:
        """
        Format the full query with operation prefix.
        
        Example: Read(/Itinerary/Day/POI[sem(content =~ "museum")])
        """
        return f"{self.intent.value.capitalize()}({xpath_query})"


class IntentClassifierBase:
    """Base class for intent classifiers."""
    
    def classify(self, user_query: str) -> ClassifiedIntent:
        """
        Classify a user query into an intent.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            ClassifiedIntent with the detected operation type and details
        """
        raise NotImplementedError("Subclasses must implement classify()")
