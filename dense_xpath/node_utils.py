"""
Node Utilities - Helper functions for working with XML Element nodes.

Fully dynamic implementation that works with any tree structure.
No hardcoded node type names - uses structural analysis instead.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional

from .models import MatchedNode


class NodeUtils:
    """
    Utility class for XML node operations.
    
    Provides methods for:
    - Getting node descriptions and names
    - Extracting subtree information
    - Converting nodes to dictionaries
    
    All methods are dynamic and work with any tree structure by analyzing
    node structure rather than checking specific node type names.
    """
    
    # Common field names to check (in priority order)
    NAME_FIELDS = ("name", "title", "label")
    DESC_FIELDS = ("description", "desc", "summary", "content")
    
    @staticmethod
    def _get_field_value(node: ET.Element, field_names: Tuple[str, ...]) -> str:
        """Try multiple field names and return the first found value."""
        for field in field_names:
            elem = node.find(field)
            if elem is not None and elem.text:
                return elem.text
        return ""
    
    @staticmethod
    def _is_simple_list(node: ET.Element) -> bool:
        """
        Check if a node is a simple list (like <highlights>).
        
        A simple list has children, but all children are text-only leaf elements.
        Examples: <highlights><highlight>A</highlight><highlight>B</highlight></highlights>
        """
        if len(node) == 0:
            return False
        # All children must be text-only leaves (no grandchildren)
        return all(len(child) == 0 for child in node)
    
    @staticmethod
    def _is_structured_node(node: ET.Element) -> bool:
        """
        Check if a node is a structured node (entity like POI, Restaurant, Task).
        
        Structured nodes are containers or leaf entities that have meaningful children.
        Simple text elements and simple lists (like highlights) are NOT structured.
        """
        # Must have children or index attribute
        if node.get("index") is not None:
            return True
        
        if len(node) == 0:
            return False
        
        # Exclude simple lists (all children are text-only)
        if NodeUtils._is_simple_list(node):
            return False
        
        return True
    
    @staticmethod
    def _is_container_node(node: ET.Element) -> bool:
        """
        Check if a node is a container (has index attribute).
        
        Container nodes group other nodes (like Day, Project, Category).
        They typically have an index attribute for ordering.
        """
        return node.get("index") is not None
    
    @staticmethod
    def get_node_description(node: ET.Element) -> str:
        """
        Get the description of a node.
        
        For container nodes without explicit description, creates summary from children.
        Works with any tree structure by detecting node types dynamically.
        """
        # First, try to find an explicit description field
        desc = NodeUtils._get_field_value(node, NodeUtils.DESC_FIELDS)
        if desc:
            return desc
        
        # For container nodes (nodes with index attr), generate summary from children
        if NodeUtils._is_container_node(node):
            children_names = []
            for child in node:
                if NodeUtils._is_structured_node(child):
                    child_name = NodeUtils._get_field_value(child, NodeUtils.NAME_FIELDS)
                    if child_name:
                        children_names.append(child_name)
            if children_names:
                return f"{node.tag} with: {', '.join(children_names[:3])}"
        
        return ""
    
    @staticmethod
    def get_node_name(node: ET.Element) -> str:
        """
        Get the display name of a node.
        
        For container nodes with index/number attribute, uses "{NodeType} {index}" format.
        For leaf nodes, tries common name fields.
        Works with any tree structure.
        """
        # For container nodes with index or number, use "{Tag} {index}" format
        # Check both 'index' and 'number' attributes (Version uses 'number')
        index = node.get("index") or node.get("number")
        if index is not None:
            return f"{node.tag} {index}"
        
        # For leaf nodes, try common name fields
        name = NodeUtils._get_field_value(node, NodeUtils.NAME_FIELDS)
        if name:
            return name
        
        # Fallback to tag name
        return node.tag
    
    @staticmethod
    def get_subtree_descriptions(node: ET.Element) -> List[Tuple[str, str, str]]:
        """
        Get descriptions from all structured child nodes.
        
        Returns:
            List of (type, name, description) tuples
        """
        results = []
        
        for child in node:
            # Only include structured nodes (not simple text elements)
            if NodeUtils._is_structured_node(child):
                name = NodeUtils._get_field_value(child, NodeUtils.NAME_FIELDS)
                desc = NodeUtils._get_field_value(child, NodeUtils.DESC_FIELDS)
                results.append((child.tag, name, desc))
        
        return results
    
    @staticmethod
    def node_to_dict(node: ET.Element) -> Dict[str, Any]:
        """
        Convert an XML node to a dictionary (node's own data only).
        
        Includes type, attributes, and leaf child elements as fields.
        Handles nested lists (like highlights) automatically.
        """
        result = {
            "type": node.tag,
            "attributes": dict(node.attrib)
        }
        
        for child in node:
            if len(child) == 0:  # Leaf element (simple text)
                result[child.tag] = child.text
            elif all(len(grandchild) == 0 for grandchild in child):
                # Simple list (all grandchildren are text leaves)
                result[child.tag] = [gc.text for gc in child if gc.text]
        
        return result
    
    @staticmethod
    def get_all_children(node: ET.Element) -> List[Dict[str, Any]]:
        """
        Get all structured children of a node as dictionaries.
        
        Works with any tree structure by detecting structured nodes dynamically.
        """
        children = []
        
        for child in node:
            # Only include structured nodes
            if NodeUtils._is_structured_node(child):
                child_dict = {"type": child.tag}
                
                for elem in child:
                    if len(elem) == 0 and elem.text:
                        # Simple text element
                        child_dict[elem.tag] = elem.text
                    elif len(elem) > 0:
                        # Nested list (like highlights)
                        child_dict[elem.tag] = [gc.text for gc in elem if gc.text]
                
                children.append(child_dict)
        
        return children
    
    @classmethod
    def node_to_matched(
        cls, 
        node: ET.Element, 
        tree_path: str, 
        score: float = 1.0
    ) -> MatchedNode:
        """
        Convert an XML node to a MatchedNode with tree context, children, and score.
        """
        node_data = cls.node_to_dict(node)
        children = cls.get_all_children(node)
        
        return MatchedNode(
            node_data=node_data,
            tree_path=tree_path,
            children=children,
            score=score
        )
    
    @classmethod
    def node_to_info_dict(
        cls, 
        node: ET.Element, 
        path: str, 
        score: float
    ) -> Dict[str, Any]:
        """
        Create an info dictionary for tracing/logging.
        """
        return {
            "path": path,
            "name": cls.get_node_name(node),
            "type": node.tag,
            "score": score
        }


# Convenience functions (for backwards compatibility)
get_node_description = NodeUtils.get_node_description
get_node_name = NodeUtils.get_node_name
get_subtree_descriptions = NodeUtils.get_subtree_descriptions
node_to_dict = NodeUtils.node_to_dict
get_all_children = NodeUtils.get_all_children
node_to_matched = NodeUtils.node_to_matched
