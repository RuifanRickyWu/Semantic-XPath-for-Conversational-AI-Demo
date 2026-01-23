"""
Node Updater - LLM-based content updates for existing nodes.

Uses an LLM to update node content based on the user's modification request.
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
    ContentUpdateResult,
    NODE_SCHEMAS,
    dict_to_xml_element,
    xml_element_to_dict
)


logger = logging.getLogger(__name__)


class NodeUpdater:
    """
    LLM-based updater for existing node content.
    
    Modifies specific fields of a node based on the user's update request
    while preserving unchanged fields.
    """
    
    PROMPT_PATH = Path(__file__).parent.parent / "storage" / "prompts" / "content_updater.txt"
    TRACES_PATH = Path(__file__).parent.parent / "traces" / "reasoning_traces"
    
    def __init__(self, client=None, save_traces: bool = True):
        """
        Initialize the node updater.
        
        Args:
            client: Optional OpenAI client
            save_traces: Whether to save update traces
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
    
    def update_node(
        self,
        user_query: str,
        original_node: ET.Element,
        operation_details: Dict[str, Any] = None
    ) -> ContentUpdateResult:
        """
        Update content of an existing node.
        
        Args:
            user_query: The user's update request
            original_node: The XML element to update
            operation_details: Additional details from intent classification
            
        Returns:
            ContentUpdateResult with updated content
        """
        node_type = original_node.tag
        original_dict = xml_element_to_dict(original_node)
        
        context_text = self._format_context(original_dict, operation_details)
        
        prompt = f"""User Request: {user_query}

{context_text}

Update the node content based on the user's request.
"""
        
        try:
            response = self.client.complete(
                prompt,
                system_prompt=self.system_prompt,
                temperature=0.2,
                max_tokens=1024
            )
            
            result = self._parse_response(response, node_type, original_dict)
            
            if self.save_traces:
                self._save_trace(user_query, node_type, original_dict, result, response)
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating node content: {e}")
            return ContentUpdateResult(
                success=False,
                original_fields=original_dict,
                reasoning=f"Error: {e}",
                raw_response=str(e)
            )
    
    def update_node_from_element(
        self,
        user_query: str,
        element: ET.Element,
        operation_details: Dict[str, Any] = None
    ) -> ContentUpdateResult:
        """
        Update an XML element based on user's request.
        
        Convenience method that takes an Element directly.
        """
        return self.update_node(user_query, element, operation_details)
    
    def _format_context(
        self,
        original_dict: Dict[str, Any],
        operation_details: Dict[str, Any] = None
    ) -> str:
        """Format context for the prompt."""
        lines = ["=== Current Node Content ==="]
        
        node_type = original_dict.get("type", "Unknown")
        lines.append(f"Type: {node_type}")
        
        for key, value in original_dict.items():
            if key == "type":
                continue
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(value)}")
            else:
                lines.append(f"{key}: {value}")
        
        if operation_details:
            lines.append("\n=== Requested Changes ===")
            changes = operation_details.get("changes", {})
            for field, new_value in changes.items():
                lines.append(f"{field}: -> {new_value}")
            
            target = operation_details.get("target", "")
            if target:
                lines.append(f"Target: {target}")
        
        return "\n".join(lines)
    
    def _parse_response(
        self,
        response: str,
        node_type: str,
        original_dict: Dict[str, Any]
    ) -> ContentUpdateResult:
        """Parse LLM response into ContentUpdateResult."""
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                # Extract updated fields
                updated_fields = parsed.get("fields", parsed.get("updated_fields", parsed))
                reasoning = parsed.get("reasoning", "")
                
                # Check if LLM suggests a new type (e.g., POI -> Restaurant)
                final_type = parsed.get("new_type", node_type)
                
                # Merge with original (preserve fields not mentioned)
                merged = dict(original_dict)
                merged.pop("type", None)  # Don't include type in fields
                
                # Track changes
                changes = {}
                for key, new_value in updated_fields.items():
                    if key in merged and merged[key] != new_value:
                        changes[key] = (merged[key], new_value)
                    elif key not in merged:
                        changes[key] = (None, new_value)
                    merged[key] = new_value
                
                # Track type change if applicable
                if final_type != node_type:
                    changes["_node_type"] = (node_type, final_type)
                    reasoning = f"[Type: {node_type} → {final_type}] " + reasoning
                
                # Generate XML with the final type (may be new_type)
                element = dict_to_xml_element(final_type, merged)
                xml_string = ET.tostring(element, encoding="unicode")
                
                return ContentUpdateResult(
                    success=True,
                    original_fields=original_dict,
                    updated_fields=merged,
                    changes=changes,
                    xml_string=xml_string,
                    xml_element=element,
                    reasoning=reasoning,
                    raw_response=response
                )
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse content update response: {e}")
        
        # Try to extract XML directly
        xml_start = response.find(f"<{node_type}>")
        xml_end = response.find(f"</{node_type}>")
        
        if xml_start >= 0 and xml_end >= 0:
            xml_string = response[xml_start:xml_end + len(f"</{node_type}>")]
            try:
                element = ET.fromstring(xml_string)
                updated_dict = xml_element_to_dict(element)
                
                # Track changes
                changes = {}
                for key, new_value in updated_dict.items():
                    if key == "type":
                        continue
                    old_value = original_dict.get(key)
                    if old_value != new_value:
                        changes[key] = (old_value, new_value)
                
                return ContentUpdateResult(
                    success=True,
                    original_fields=original_dict,
                    updated_fields=updated_dict,
                    changes=changes,
                    xml_string=xml_string,
                    xml_element=element,
                    reasoning="Extracted from XML in response",
                    raw_response=response
                )
            except ET.ParseError:
                pass
        
        return ContentUpdateResult(
            success=False,
            original_fields=original_dict,
            reasoning="Failed to parse response",
            raw_response=response
        )
    
    def _save_trace(
        self,
        user_query: str,
        node_type: str,
        original_dict: Dict[str, Any],
        result: ContentUpdateResult,
        raw_response: str
    ):
        """Save update trace to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trace_file = self.TRACES_PATH / f"content_update_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            "user_query": user_query,
            "node_type": node_type,
            "original": original_dict,
            "result": result.to_dict(),
            "raw_response": raw_response
        }
        
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved content update trace to {trace_file}")
