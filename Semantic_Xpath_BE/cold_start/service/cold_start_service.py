"""
Cold Start Service - Service interface for cold start processing.

Provides the ColdStartService class that wraps the ColdStartClient
and exposes a clean `process(query)` method.
"""

from __future__ import annotations

from typing import Any, Dict

from cold_start.client.cold_start_client import ColdStartClient


class ColdStartService:
    """
    Service layer for cold start operations.
    Delegates to ColdStartClient for the actual generation logic.
    """

    def __init__(self):
        self._client = ColdStartClient()

    def process(self, query: str, save: bool = True, activate: bool = False) -> Dict[str, Any]:
        """
        Process a cold start request.

        Args:
            query: The user's natural language request.
            save: Whether to persist generated artifacts to storage.
            activate: Whether to activate the generated schema in config.

        Returns:
            Dict containing success status and all generated artifacts.
        """
        return self._client.generate(
            user_request=query,
            save=save,
            activate=activate,
        )
