"""
Base classes for content creation and updates.

Provides common data structures for LLM-based content generation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import xml.etree.ElementTree as ET


@dataclass
class ContentGenerationResult:
    """
    Result of content generation.
    
    Attributes:
        success: Whether generation succeeded
        node_type: Type of node generated
        xml_string: Generated XML string
        xml_element: Parsed XML element (if successful)
        fields: Dictionary of generated field values
        reasoning: LLM's reasoning for content choices
        raw_response: Raw LLM response
    """
    success: bool
    node_type: str = ""
    xml_string: str = ""
    xml_element: Optional[ET.Element] = None
    fields: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    raw_response: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (excludes xml_element)."""
        return {
            "success": self.success,
            "node_type": self.node_type,
            "xml_string": self.xml_string,
            "fields": self.fields,
            "reasoning": self.reasoning
        }


@dataclass
class ContentUpdateResult:
    """
    Result of content update.
    
    Attributes:
        success: Whether update succeeded
        original_fields: Original field values
        updated_fields: New field values
        changes: Mapping of field -> (old_value, new_value)
        xml_string: Updated XML string
        xml_element: Parsed XML element (if successful)
        reasoning: LLM's reasoning for changes
        raw_response: Raw LLM response
    """
    success: bool
    original_fields: Dict[str, Any] = field(default_factory=dict)
    updated_fields: Dict[str, Any] = field(default_factory=dict)
    changes: Dict[str, tuple] = field(default_factory=dict)
    xml_string: str = ""
    xml_element: Optional[ET.Element] = None
    reasoning: str = ""
    raw_response: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (excludes xml_element)."""
        return {
            "success": self.success,
            "original_fields": self.original_fields,
            "updated_fields": self.updated_fields,
            "changes": {k: {"from": v[0], "to": v[1]} for k, v in self.changes.items()},
            "xml_string": self.xml_string,
            "reasoning": self.reasoning
        }


# Schema field definitions for different node types
NODE_SCHEMAS = {
    "POI": {
        "fields": ["name", "time_block", "description", "travel_method", "expected_cost"],
        "list_fields": ["highlights"],
        "required": ["name", "description"]
    },
    "Restaurant": {
        "fields": ["name", "time_block", "description", "travel_method", "expected_cost"],
        "list_fields": ["highlights"],
        "required": ["name", "description"]
    },
    "Day": {
        "fields": [],
        "attributes": ["index"],
        "required": ["index"]
    },
    "Task": {
        "fields": ["title", "description", "priority", "due_date", "status"],
        "list_fields": ["tags"],
        "required": ["title"]
    }
}


def dict_to_xml_element(node_type: str, data: Dict[str, Any]) -> ET.Element:
    """
    Convert a dictionary to an XML element.
    
    Args:
        node_type: Type of node (e.g., "POI", "Restaurant")
        data: Dictionary with field values
        
    Returns:
        XML Element
    """
    element = ET.Element(node_type)
    
    # Handle attributes
    schema = NODE_SCHEMAS.get(node_type, {})
    for attr in schema.get("attributes", []):
        if attr in data:
            element.set(attr, str(data[attr]))
    
    # Handle regular fields
    for field in schema.get("fields", []):
        if field in data and data[field]:
            child = ET.SubElement(element, field)
            child.text = str(data[field])
    
    # Handle list fields (like highlights)
    for list_field in schema.get("list_fields", []):
        if list_field in data and data[list_field]:
            container = ET.SubElement(element, list_field)
            items = data[list_field]
            if isinstance(items, list):
                item_name = list_field.rstrip("s")  # "highlights" -> "highlight"
                for item in items:
                    child = ET.SubElement(container, item_name)
                    child.text = str(item)
    
    # Handle any additional fields not in schema
    known_fields = set(schema.get("fields", []) + 
                       schema.get("list_fields", []) + 
                       schema.get("attributes", []))
    for key, value in data.items():
        if key not in known_fields and value:
            child = ET.SubElement(element, key)
            if isinstance(value, list):
                for item in value:
                    sub = ET.SubElement(child, "item")
                    sub.text = str(item)
            else:
                child.text = str(value)
    
    return element


def xml_element_to_dict(element: ET.Element) -> Dict[str, Any]:
    """
    Convert an XML element to a dictionary.
    
    Args:
        element: XML Element
        
    Returns:
        Dictionary with field values
    """
    result = {"type": element.tag}
    
    # Get attributes
    result.update(element.attrib)
    
    # Get child elements
    for child in element:
        if len(child) > 0:
            # Has nested children (like highlights)
            result[child.tag] = [c.text for c in child if c.text]
        elif child.text:
            result[child.tag] = child.text.strip()
    
    return result
