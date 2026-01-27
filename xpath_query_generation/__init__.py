"""
XPath Query Generation module.

Second stage of 2-stage semantic XPath processing.
Generates tree-traversal queries from natural language.
Version handling is done separately by VersionResolver.

Examples:
- /Itinerary/Day/POI[atom(content =~ "museum")]
- /Itinerary/Day[@index='1'], Restaurant, sushi restaurant
- /Itinerary/Day/POI[...], time_block: 2:00 PM
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
