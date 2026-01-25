"""
XPath Query Generator - Uses LLM to convert user requests into CRUD XPath queries.

Supports multiple domains (itinerary, todolist, etc.) by loading prompts
dynamically based on the active schema in config.yaml.

Now combines intent classification with xpath generation in a single LLM call.
Output format: Operation(/Path/...)
"""

import re
from pathlib import Path
import sys
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from dense_xpath.schema_loader import get_schema_info


class CRUDOperation(Enum):
    """CRUD operation types."""
    READ = "Read"
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"


@dataclass
class ParsedQuery:
    """
    Parsed CRUD query result.
    
    Attributes:
        operation: The CRUD operation type
        xpath: The XPath query (without operation prefix)
        full_query: The complete query string with operation
        create_info: For CREATE operations, contains (parent_path, node_type, description)
        update_info: For UPDATE operations, contains (node_path, field_changes)
    """
    operation: CRUDOperation
    xpath: str
    full_query: str
    create_info: Optional[Tuple[str, str, str]] = None  # (parent_path, node_type, description)
    update_info: Optional[Tuple[str, Dict[str, Any]]] = None  # (node_path, changes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "operation": self.operation.value,
            "xpath": self.xpath,
            "full_query": self.full_query
        }
        if self.create_info:
            result["create_info"] = {
                "parent_path": self.create_info[0],
                "node_type": self.create_info[1],
                "description": self.create_info[2]
            }
        if self.update_info:
            result["update_info"] = {
                "node_path": self.update_info[0],
                "changes": self.update_info[1]
            }
        return result


class XPathQueryGenerator:
    """
    Converts natural language user requests into CRUD XPath queries using LLM.
    
    Combines intent classification and xpath generation in a single LLM call.
    Output format: Operation(/Path/...)
    
    Supports multiple domains by loading the appropriate prompt based on
    the active schema configuration.
    """
    
    # Pattern to parse CRUD query: Operation(/path...)
    CRUD_PATTERN = re.compile(r'^(Read|Create|Update|Delete)\((.+)\)$', re.DOTALL)
    
    # Pattern for Create: Create(/parent/path, NodeType, description)
    CREATE_PATTERN = re.compile(r'^(.+?),\s*(\w+),\s*(.+)$', re.DOTALL)
    
    # Pattern for Update: Update(/node/path, field: value)
    UPDATE_PATTERN = re.compile(r'^(.+?),\s*(.+)$', re.DOTALL)
    
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
        Convert a user request into a CRUD XPath query.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            CRUD XPath query string in format: Operation(/path/...)
        """
        prompt = f"User: {user_request}"
        
        response = self.client.complete(
            prompt,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=512
        )
        
        # Clean up the response - extract just the query
        query = response.strip()
        
        # Remove any "Output:" prefix if present
        if query.lower().startswith("output:"):
            query = query[7:].strip()
        
        # Remove markdown code block if present
        if query.startswith("```"):
            lines = query.split("\n")
            query = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            query = query.strip()
        
        return query
    
    def generate_and_parse(self, user_request: str) -> ParsedQuery:
        """
        Generate and parse a CRUD query from user request.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            ParsedQuery with operation type and parsed components
        """
        full_query = self.generate(user_request)
        return self.parse_query(full_query)
    
    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse a CRUD query into its components.
        
        Args:
            query: CRUD query string in format Operation(/path/...)
            
        Returns:
            ParsedQuery with parsed components
            
        Raises:
            ValueError: If query format is invalid
        """
        query = query.strip()
        
        # Match the CRUD pattern
        match = self.CRUD_PATTERN.match(query)
        if not match:
            # Default to READ if no operation prefix
            return ParsedQuery(
                operation=CRUDOperation.READ,
                xpath=query,
                full_query=f"Read({query})"
            )
        
        operation_str = match.group(1)
        content = match.group(2).strip()
        
        try:
            operation = CRUDOperation(operation_str)
        except ValueError:
            operation = CRUDOperation.READ
        
        # Parse based on operation type
        if operation == CRUDOperation.CREATE:
            return self._parse_create(content, query)
        elif operation == CRUDOperation.UPDATE:
            return self._parse_update(content, query)
        else:
            # READ or DELETE - just xpath
            return ParsedQuery(
                operation=operation,
                xpath=content,
                full_query=query
            )
    
    def _parse_create(self, content: str, full_query: str) -> ParsedQuery:
        """
        Parse CREATE query content.
        
        Format: /parent/path, NodeType, description
        """
        match = self.CREATE_PATTERN.match(content)
        if match:
            parent_path = match.group(1).strip()
            node_type = match.group(2).strip()
            description = match.group(3).strip()
            
            return ParsedQuery(
                operation=CRUDOperation.CREATE,
                xpath=parent_path,
                full_query=full_query,
                create_info=(parent_path, node_type, description)
            )
        
        # Fallback: treat entire content as xpath
        return ParsedQuery(
            operation=CRUDOperation.CREATE,
            xpath=content,
            full_query=full_query
        )
    
    def _parse_update(self, content: str, full_query: str) -> ParsedQuery:
        """
        Parse UPDATE query content.
        
        Format: /node/path, field: value (or field: value, field2: value2)
        """
        match = self.UPDATE_PATTERN.match(content)
        if match:
            node_path = match.group(1).strip()
            changes_str = match.group(2).strip()
            
            # Parse changes (field: value pairs)
            changes = {}
            for part in changes_str.split(","):
                if ":" in part:
                    key, value = part.split(":", 1)
                    changes[key.strip()] = value.strip()
            
            return ParsedQuery(
                operation=CRUDOperation.UPDATE,
                xpath=node_path,
                full_query=full_query,
                update_info=(node_path, changes)
            )
        
        # Fallback: treat entire content as xpath
        return ParsedQuery(
            operation=CRUDOperation.UPDATE,
            xpath=content,
            full_query=full_query
        )
    
    @staticmethod
    def extract_version_selector(xpath: str) -> Tuple[str, str]:
        """
        Extract version selector from xpath query.
        
        Args:
            xpath: XPath query that may contain Version selector
            
        Returns:
            Tuple of (version_selector, remaining_xpath)
            version_selector is like "[-1]", "[2]", or "[atom(content =~ ...)]"
            If no Version in path, returns ("[-1]", xpath) as default
        """
        # Pattern to find Version[...] in the path
        version_pattern = re.compile(r'/Version(\[[^\]]+\]|\[-?\d+\])')
        
        match = version_pattern.search(xpath)
        if match:
            version_selector = match.group(1)
            # Remove the Version[...] from the path but keep the parts before and after
            before = xpath[:match.start()]
            after = xpath[match.end():]
            remaining_xpath = before + after
            
            # Clean up double slashes
            remaining_xpath = remaining_xpath.replace("//", "/")
            
            return version_selector, remaining_xpath
        
        # No Version selector found, use default [-1]
        return "[-1]", xpath
