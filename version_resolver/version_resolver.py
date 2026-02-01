"""
Version Resolver - First stage LLM call for 2-stage semantic XPath processing.

Responsibilities:
1. Determine version selector type (at/before)
2. Extract semantic query for version matching
3. Classify CRUD operation

Query Syntax Output:
- at([-1]) - Latest version (default)
- at([N]) - Specific version number
- at(sem(content ~= "description")) - Semantic match for specific version
- before(sem(content ~= "description")) - Version before the matched version (for rollback)
"""

import re
import logging
from pathlib import Path
from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from dense_xpath.schema_loader import get_schema_info
from xpath_query_generation import CRUDOperation


logger = logging.getLogger(__name__)


class VersionSelector(Enum):
    """Version selector type."""
    AT = "at"        # Specific version: "in the version of xxx"
    BEFORE = "before"  # Version before: "rollback", "the version before"


@dataclass
class ResolvedVersion:
    """
    Result of version resolution.
    
    Attributes:
        selector_type: at or before
        semantic_query: Semantic description for version matching (None if using index)
        index: Numeric index (-1 for latest, or specific number)
        crud_operation: The CRUD operation type
        raw_response: Raw LLM response for debugging
    """
    selector_type: VersionSelector
    semantic_query: Optional[str]
    index: Optional[int]
    crud_operation: CRUDOperation
    raw_response: str
    token_usage: Optional[Dict[str, int]] = None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "selector_type": self.selector_type.value,
            "semantic_query": self.semantic_query,
            "index": self.index,
            "crud_operation": self.crud_operation.value,
            "raw_response": self.raw_response,
            "token_usage": self.token_usage
        }
    
    def get_version_selector_string(self) -> str:
        """
        Get the version selector string for use in queries.
        
        Returns:
            Version selector string like "at([-1])" or "before(sem(content ~= 'museum'))"
        """
        if self.semantic_query:
            inner = f'sem(content ~= "{self.semantic_query}")'
        else:
            inner = f"[{self.index}]"
        
        return f"{self.selector_type.value}({inner})"


class VersionResolver:
    """
    Resolves version selectors and CRUD operations from natural language queries.
    
    First stage of 2-stage semantic XPath processing:
    1. Version Resolution (this class) - determines which version to operate on
    2. XPath Generation - generates the tree traversal query
    """
    
    # Pattern to parse LLM response
    RESPONSE_PATTERN = re.compile(
        r'(at|before)\s*\(\s*'
        r'(?:'
        r'\[\s*(-?\d+)\s*\]'  # Index: [-1] or [2]
        r'|'
        r'sem\s*\(\s*content\s*~=\s*["\']([^"\']+)["\']\s*\)'  # Semantic: sem(content ~= "...")
        r')\s*\)'
        r'\s*,\s*'
        r'(READ|CREATE|UPDATE|DELETE)',
        re.IGNORECASE
    )
    
    def __init__(self, client=None, schema_name: Optional[str] = None):
        """
        Initialize the version resolver.
        
        Args:
            client: Optional OpenAI client. If not provided, one will be created lazily.
            schema_name: Optional schema name. If None, uses active_schema from config.yaml.
        """
        self._client = client
        self._system_prompt = None
        
        # Get schema info to determine prompt path
        schema_info = get_schema_info(schema_name)
        prompt_file = schema_info.get("version_resolver_prompt", "prompts/version_resolver.txt")
        self._prompt_path = Path(__file__).parent.parent / "storage" / prompt_file
        self._schema_name = schema_info["schema_name"]
    
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
            with open(self._prompt_path, "r") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    def resolve(self, user_query: str) -> ResolvedVersion:
        """
        Resolve version selector and CRUD operation from user query.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            ResolvedVersion with selector type, semantic query or index, and CRUD operation
        """
        prompt = f"User: {user_query}"
        
        result = self.client.complete_with_usage(
            prompt,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=256
        )
        
        raw_response = result.content.strip()
        
        # Clean up response
        if raw_response.lower().startswith("output:"):
            raw_response = raw_response[7:].strip()
        
        resolved_version = self._parse_response(raw_response)
        resolved_version.token_usage = result.usage.to_dict()
        return resolved_version
    
    def _parse_response(self, response: str) -> ResolvedVersion:
        """
        Parse the LLM response into a ResolvedVersion.
        
        Expected format: at([-1]), READ
                        at(sem(content ~= "museum")), DELETE
                        before(sem(content ~= "delete museum")), READ
        
        Args:
            response: Raw LLM response
            
        Returns:
            ResolvedVersion object
        """
        match = self.RESPONSE_PATTERN.search(response)
        
        if match:
            selector_str = match.group(1).lower()
            index_str = match.group(2)
            semantic_str = match.group(3)
            crud_str = match.group(4).upper()
            
            selector_type = VersionSelector.AT if selector_str == "at" else VersionSelector.BEFORE
            
            if index_str:
                index = int(index_str)
                semantic_query = None
            else:
                index = None
                semantic_query = semantic_str
            
            try:
                crud_operation = CRUDOperation(crud_str.capitalize())
            except ValueError:
                crud_operation = CRUDOperation.READ
            
            return ResolvedVersion(
                selector_type=selector_type,
                semantic_query=semantic_query,
                index=index,
                crud_operation=crud_operation,
                raw_response=response
            )
        
        # Fallback: default to latest version and try to infer CRUD from keywords
        crud_operation = self._infer_crud_from_text(response)
        
        return ResolvedVersion(
            selector_type=VersionSelector.AT,
            semantic_query=None,
            index=-1,
            crud_operation=crud_operation,
            raw_response=response
        )
    
    def _infer_crud_from_text(self, text: str) -> CRUDOperation:
        """
        Infer CRUD operation from text using keyword matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            CRUDOperation
        """
        text_lower = text.lower()
        
        # Check for CRUD keywords
        delete_keywords = ["delete", "remove", "drop", "cancel", "eliminate"]
        create_keywords = ["add", "create", "insert", "new", "schedule", "put", "include"]
        update_keywords = ["change", "update", "modify", "edit", "move", "reschedule", "replace"]
        
        for keyword in delete_keywords:
            if keyword in text_lower:
                return CRUDOperation.DELETE
        
        for keyword in create_keywords:
            if keyword in text_lower:
                return CRUDOperation.CREATE
        
        for keyword in update_keywords:
            if keyword in text_lower:
                return CRUDOperation.UPDATE
        
        return CRUDOperation.READ
