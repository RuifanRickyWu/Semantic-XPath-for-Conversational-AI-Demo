"""
XPath Query Generator - Second stage LLM call for 2-stage semantic XPath processing.

Generates tree-traversal semantic XPath queries from natural language.
Version handling and CRUD classification are done in the first stage (VersionResolver).

This generator focuses purely on:
1. Understanding the tree structure
2. Generating appropriate semantic predicates
3. Reasoning about context vs actual query information
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
from dense_xpath.schema_loader import get_schema_info, get_schema_summary_for_prompt

# Prompts directory
_PROMPTS_DIR = Path(__file__).parent.parent / "storage" / "prompts"


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
    Converts natural language user requests into semantic XPath queries using LLM.
    
    Second stage of 2-stage semantic XPath processing:
    1. Version Resolution (VersionResolver) - determines which version to operate on
    2. XPath Generation (this class) - generates the tree traversal query
    
    This class focuses on tree structure navigation and semantic predicate generation.
    It expects the CRUD operation to be provided externally (from VersionResolver).
    """
    
    # Pattern for Create: /parent/path, NodeType, description
    CREATE_PATTERN = re.compile(r'^(.+?),\s*(\w+),\s*(.+)$', re.DOTALL)
    
    # Pattern for Update: /node/path, field: value
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
        
        # Get schema info for dynamic prompt composition
        self._schema_info = get_schema_info(schema_name)
        self._schema_name = self._schema_info["schema_name"]
    
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
        """Lazy load and compose the system prompt from template and components."""
        if self._system_prompt is None:
            self._system_prompt = self._compose_prompt()
        return self._system_prompt
    
    def _compose_prompt(self) -> str:
        """
        Compose the system prompt dynamically from template and components.
        
        Loads:
        1. Master template (xpath_query_generator.txt)
        2. Grammar file (xpath_grammar.txt)
        3. Scenario-specific examples
        4. Schema structure (generated from schema)
        5. Syntax rules (from schema config)
        
        Returns:
            Fully composed system prompt string
        """
        # Load master template
        template_path = _PROMPTS_DIR / "xpath_query_generator.txt"
        with open(template_path, "r") as f:
            template = f.read()
        
        # Load grammar file
        grammar_path = _PROMPTS_DIR / "xpath_grammar.txt"
        with open(grammar_path, "r") as f:
            grammar = f.read()
        
        # Load scenario-specific examples
        examples_path = Path(self._schema_info["examples_file"])
        with open(examples_path, "r") as f:
            examples = f.read()
        
        # Generate schema structure from schema definition
        schema_structure = get_schema_summary_for_prompt(self._schema_name)
        
        # Get syntax rules from schema config
        syntax_rules = self._schema_info.get("syntax_rules", "").strip()
        
        # Substitute placeholders
        prompt = template.format(
            schema_name=self._schema_name,
            schema_structure=schema_structure,
            grammar=grammar,
            syntax_rules=syntax_rules,
            examples=examples
        )
        
        return prompt
    
    def generate(self, user_request: str, operation: CRUDOperation = None) -> str:
        """
        Convert a user request into a semantic XPath query.
        
        Args:
            user_request: Natural language request from the user
            operation: Pre-determined CRUD operation (from VersionResolver)
            
        Returns:
            XPath query string (path only, no operation prefix)
        """
        # Build prompt with operation hint if provided
        if operation:
            prompt = f"Operation: {operation.value}\nUser: {user_request}"
        else:
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
    
    def generate_and_parse(
        self, 
        user_request: str, 
        operation: CRUDOperation = None
    ) -> ParsedQuery:
        """
        Generate and parse a query from user request.
        
        Args:
            user_request: Natural language request from the user
            operation: Pre-determined CRUD operation (from VersionResolver).
                      If None, will try to infer from the query output.
            
        Returns:
            ParsedQuery with operation type and parsed components
        """
        xpath_query = self.generate(user_request, operation)
        
        # Use provided operation or default to READ
        final_operation = operation if operation else CRUDOperation.READ
        
        return self._parse_xpath(xpath_query, final_operation)
    
    def _parse_xpath(self, xpath: str, operation: CRUDOperation) -> ParsedQuery:
        """
        Parse an xpath query based on operation type.
        
        Args:
            xpath: XPath query string
            operation: CRUD operation type
            
        Returns:
            ParsedQuery with parsed components
        """
        xpath = xpath.strip()
        full_query = f"{operation.value}({xpath})"
        
        if operation == CRUDOperation.CREATE:
            return self._parse_create(xpath, full_query)
        elif operation == CRUDOperation.UPDATE:
            return self._parse_update(xpath, full_query)
        else:
            # READ or DELETE - just xpath
            return ParsedQuery(
                operation=operation,
                xpath=xpath,
                full_query=full_query
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
    
    # Legacy method for backward compatibility
    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse a CRUD query into its components (legacy support).
        
        Args:
            query: CRUD query string in format Operation(/path/...)
            
        Returns:
            ParsedQuery with parsed components
        """
        query = query.strip()
        
        # Pattern to match Operation(/path...)
        crud_pattern = re.compile(r'^(Read|Create|Update|Delete)\((.+)\)$', re.DOTALL)
        match = crud_pattern.match(query)
        
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
        
        return self._parse_xpath(content, operation)
    
    @staticmethod
    def extract_version_selector(xpath: str) -> Tuple[str, str]:
        """
        Extract version selector from xpath query (legacy support).
        
        Args:
            xpath: XPath query that may contain Version/Itinerary_Version selector
            
        Returns:
            Tuple of (version_selector, remaining_xpath)
            version_selector is like "[-1]", "[2]", or "[atom(content =~ ...)]"
            If no Version in path, returns ("[-1]", xpath) as default
        """
        # Pattern to find Version[...] or Itinerary_Version[...] in the path
        version_pattern = re.compile(r'/(Version|Itinerary_Version)(\[[^\]]+\]|\[-?\d+\])')
        
        match = version_pattern.search(xpath)
        if match:
            version_selector = match.group(2)
            # Remove the Version[...] from the path but keep the parts before and after
            before = xpath[:match.start()]
            after = xpath[match.end():]
            remaining_xpath = before + after
            
            # Clean up double slashes
            remaining_xpath = remaining_xpath.replace("//", "/")
            
            return version_selector, remaining_xpath
        
        # No Version selector found, use default [-1]
        return "[-1]", xpath
