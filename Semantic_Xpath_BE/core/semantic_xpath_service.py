"""
Semantic XPath Service - Orchestrator that delegates to domain-specific services.

Currently supports:
- Cold Start: Generate schemas and memory trees from user requests.
"""

from __future__ import annotations

from typing import Any, Dict

from cold_start.service.cold_start_service import ColdStartService


class SemanticXpathService:
    """
    Main service orchestrator for the Semantic XPath system.
    Receives requests and delegates to the appropriate processor.
    """

    def __init__(self):
        self._cold_start_service = ColdStartService()

    def cold_start(self, query: str, save: bool = True, activate: bool = False) -> Dict[str, Any]:
        """
        Process a cold start request: generate schemas and memory from a user query.

        Args:
            query: The user's natural language request.
            save: Whether to persist artifacts.
            activate: Whether to activate the schema in config.

        Returns:
            Dict with success status and generated artifacts.
        """
        return self._cold_start_service.process(query=query, save=save, activate=activate)
