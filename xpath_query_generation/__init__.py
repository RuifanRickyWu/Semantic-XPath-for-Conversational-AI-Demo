"""
XPath Query Generation module.

Provides unified CRUD + XPath query generation in a single LLM call.
Output format: Operation(/Path/...)

Examples:
- Read(/Itinerary/Version[-1]/Day/POI[atom(content =~ "museum")])
- Delete(/Itinerary/Version[-1]/Day/POI[atom(content =~ "museum")])
- Create(/Itinerary/Version[-1]/Day[@index='1'], Restaurant, sushi restaurant)
- Update(/Itinerary/Version[-1]/Day/POI[...], time_block: 2:00 PM)
"""

from .xpath_query_generator import (
    XPathQueryGenerator,
    CRUDOperation,
    ParsedQuery
)

__all__ = [
    "XPathQueryGenerator",
    "CRUDOperation",
    "ParsedQuery"
]
