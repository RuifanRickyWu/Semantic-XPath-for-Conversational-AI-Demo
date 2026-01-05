"""
XPath Query Generator - Uses LLM to convert user requests into XPath-like queries.

Supports multiple domains (itinerary, todolist, etc.) by loading prompts
dynamically based on the active schema in config.yaml.
"""

from pathlib import Path
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from dense_xpath.schema_loader import get_schema_info


class XPathQueryGenerator:
    """
    Converts natural language user requests into XPath-like queries using LLM.
    
    Supports multiple domains by loading the appropriate prompt based on
    the active schema configuration.
    """
    
    def __init__(self, client=None, schema_name: Optional[str] = None):
        """
        Initialize the query generator.
        
        Args:
            client: Optional OpenAI client. If not provided, one will be created lazily.
            schema_name: Optional schema name (e.g., "itinerary", "todolist").
                        If None, uses active_schema from config.yaml.
        """
        self._client = client
        self._system_prompt = None  # Lazy load
        
        # Get schema info to determine prompt path
        schema_info = get_schema_info(schema_name)
        self._prompt_path = Path(schema_info["prompt_file"])
        self._schema_name = schema_info["schema_name"]
    
    @property
    def client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = get_client()
        return self._client
    
    @property
    def schema_name(self) -> str:
        """Return the active schema name."""
        return self._schema_name
    
    @property
    def system_prompt(self) -> str:
        """Lazy load the system prompt from file."""
        if self._system_prompt is None:
            with open(self._prompt_path, "r") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    def generate(self, user_request: str) -> str:
        """
        Convert a user request into an XPath-like query.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            XPath-like query string
        """
        prompt = f"User: {user_request}"
        
        response = self.client.complete(
            prompt,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=256
        )
        
        # Clean up the response - extract just the query
        query = response.strip()
        
        # Remove any "Output:" prefix if present
        if query.lower().startswith("output:"):
            query = query[7:].strip()
        
        return query
