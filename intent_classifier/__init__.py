"""
Intent Classifier module (DEPRECATED).

Intent classification is now integrated into the XPath Query Generator,
which outputs CRUD-prefixed queries in a single LLM call:
- Read(/Itinerary/Version[-1]/Day/POI[...])
- Delete(/Itinerary/Version[-1]/Day/POI[...])
- Create(/Itinerary/Version[-1]/Day[1], Restaurant, ...)
- Update(/Itinerary/Version[-1]/Day/POI[...], field: value)

The base classes are kept for backward compatibility but the IntentClassifier
class is no longer used in the main pipeline.

See xpath_query_generation.XPathQueryGenerator for the unified approach.
"""

from .base import IntentType, ClassifiedIntent, IntentClassifierBase
from .intent_classifier import IntentClassifier

__all__ = [
    "IntentType",
    "ClassifiedIntent", 
    "IntentClassifierBase",
    "IntentClassifier"
]
