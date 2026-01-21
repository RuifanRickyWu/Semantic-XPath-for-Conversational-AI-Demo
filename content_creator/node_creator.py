"""
Node Creator - LLM-based content generation for new nodes.

Uses an LLM to generate appropriate content for new nodes based on
the user's request and the current tree context.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import xml.etree.ElementTree as ET
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from .base import (
    ContentGenerationResult,
    NODE_SCHEMAS,
    dict_to_xml_element
)


logger = logging.getLogger(__name__)


class NodeCreator:
    """
    LLM-based creator for new node content.
    
    Generates appropriate content for new nodes based on:
    - User's creation request
    - Node type schema
    - Surrounding context (siblings, parent)
    """
    
    PROMPT_PATH = Path(__file__).parent.parent / "storage" / "prompts" / "content_creator.txt"
    TRACES_PATH = Path(__file__).parent.parent / "traces" / "reasoning_traces"
    
    def __init__(self, client=None, save_traces: bool = True):
        """
        Initialize the node creator.
        
        Args:
            client: Optional OpenAI client
            save_traces: Whether to save generation traces
        """
        self._client = client
        self._system_prompt = None
        self.save_traces = save_traces
        
        self.TRACES_PATH.mkdir(parents=True, exist_ok=True)
    
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
            with open(self.PROMPT_PATH, "r") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    def create_node(
        self,
        user_query: str,
        node_type: str,
        context: Dict[str, Any],
        operation_details: Dict[str, Any] = None
    ) -> ContentGenerationResult:
        """
        Generate content for a new node.
        
        Args:
            user_query: The user's creation request
            node_type: Type of node to create (e.g., "POI", "Restaurant")
            context: Surrounding context (siblings, parent info)
            operation_details: Additional details from intent classification
            
        Returns:
            ContentGenerationResult with generated content
        """
        schema = NODE_SCHEMAS.get(node_type, {})
        context_text = self._format_context(node_type, context, operation_details)
        
        prompt = f"""User Request: {user_query}

Node Type: {node_type}
Required Fields: {schema.get('required', [])}
Optional Fields: {schema.get('fields', [])}
List Fields: {schema.get('list_fields', [])}

{context_text}

Generate content for the new {node_type} node.
"""
        
        try:
            response = self.client.complete(
                prompt,
                system_prompt=self.system_prompt,
                temperature=0.3,
                max_tokens=1024
            )
            
            result = self._parse_response(response, node_type)
            
            if self.save_traces:
                self._save_trace(user_query, node_type, context, result, response)
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating node content: {e}")
            return ContentGenerationResult(
                success=False,
                node_type=node_type,
                reasoning=f"Error: {e}",
                raw_response=str(e)
            )
    
    def _format_context(
        self,
        node_type: str,
        context: Dict[str, Any],
        operation_details: Dict[str, Any] = None
    ) -> str:
        """Format context for the prompt."""
        lines = ["=== Context ==="]
        
        # Operation details
        if operation_details:
            new_content = operation_details.get("new_content", "")
            insertion_context = operation_details.get("insertion_context", "")
            if new_content:
                lines.append(f"What to create: {new_content}")
            if insertion_context:
                lines.append(f"Where/When: {insertion_context}")
        
        # Parent info
        parent = context.get("parent", {})
        if parent:
            lines.append(f"\nParent: {parent.get('type', 'Unknown')}")
            if parent.get("index"):
                lines.append(f"Day index: {parent.get('index')}")
        
        # Siblings for context
        siblings = context.get("siblings", [])
        if siblings:
            lines.append(f"\nExisting siblings ({len(siblings)}):")
            for i, sib in enumerate(siblings[:5]):  # Limit to first 5
                sib_type = sib.get("type", "?")
                sib_name = sib.get("name", "")
                sib_time = sib.get("time_block", "")
                lines.append(f"  {i+1}. {sib_type}: {sib_name} ({sib_time})")
        
        return "\n".join(lines)
    
    def _parse_response(
        self,
        response: str,
        node_type: str
    ) -> ContentGenerationResult:
        """Parse LLM response into ContentGenerationResult."""
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                # Extract fields
                fields = parsed.get("fields", parsed)
                reasoning = parsed.get("reasoning", "")
                
                # Generate XML
                element = dict_to_xml_element(node_type, fields)
                xml_string = ET.tostring(element, encoding="unicode")
                
                return ContentGenerationResult(
                    success=True,
                    node_type=node_type,
                    xml_string=xml_string,
                    xml_element=element,
                    fields=fields,
                    reasoning=reasoning,
                    raw_response=response
                )
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse content creation response: {e}")
        
        # Try to extract XML directly
        xml_start = response.find(f"<{node_type}>")
        xml_end = response.find(f"</{node_type}>")
        
        if xml_start >= 0 and xml_end >= 0:
            xml_string = response[xml_start:xml_end + len(f"</{node_type}>")]
            try:
                element = ET.fromstring(xml_string)
                return ContentGenerationResult(
                    success=True,
                    node_type=node_type,
                    xml_string=xml_string,
                    xml_element=element,
                    fields={},
                    reasoning="Extracted from XML in response",
                    raw_response=response
                )
            except ET.ParseError:
                pass
        
        return ContentGenerationResult(
            success=False,
            node_type=node_type,
            reasoning="Failed to parse response",
            raw_response=response
        )
    
    def _save_trace(
        self,
        user_query: str,
        node_type: str,
        context: Dict[str, Any],
        result: ContentGenerationResult,
        raw_response: str
    ):
        """Save generation trace to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trace_file = self.TRACES_PATH / f"content_creation_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            "user_query": user_query,
            "node_type": node_type,
            "context": {
                "parent": context.get("parent", {}),
                "siblings_count": len(context.get("siblings", []))
            },
            "result": result.to_dict(),
            "raw_response": raw_response
        }
        
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved content creation trace to {trace_file}")
