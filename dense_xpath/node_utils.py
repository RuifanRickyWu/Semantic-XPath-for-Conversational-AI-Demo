"""
Node Utilities - Helper functions for working with XML Element nodes.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple

from .models import MatchedNode


class NodeUtils:
    """
    Utility class for XML node operations.
    
    Provides methods for:
    - Getting node descriptions and names
    - Extracting subtree information
    - Converting nodes to dictionaries
    """
    
    @staticmethod
    def get_node_description(node: ET.Element) -> str:
        """
        Get the description of a node.
        
        For Day nodes without explicit description, creates summary from children.
        """
        desc_elem = node.find("description")
        if desc_elem is not None and desc_elem.text:
            return desc_elem.text
        
        # For Day nodes, create a summary from children
        if node.tag == "Day":
            children_descs = []
            for child in node:
                if child.tag in ("POI", "Restaurant"):
                    child_name = child.find("name")
                    if child_name is not None and child_name.text:
                        children_descs.append(child_name.text)
            if children_descs:
                return f"Day with: {', '.join(children_descs[:3])}"
        
        return ""
    
    @staticmethod
    def get_node_name(node: ET.Element) -> str:
        """
        Get the display name of a node.
        
        For Day nodes, uses "Day X" format based on index attribute.
        """
        name_elem = node.find("name")
        if name_elem is not None and name_elem.text:
            return name_elem.text
        
        # For Day nodes, use index
        if node.tag == "Day":
            index = node.get("index", "?")
            return f"Day {index}"
        
        return node.tag
    
    @staticmethod
    def get_subtree_descriptions(node: ET.Element) -> List[Tuple[str, str, str]]:
        """
        Get descriptions from all direct children (POI/Restaurant).
        
        Returns:
            List of (type, name, description) tuples
        """
        results = []
        
        for child in node:
            if child.tag in ("POI", "Restaurant"):
                name = ""
                desc = ""
                name_elem = child.find("name")
                desc_elem = child.find("description")
                if name_elem is not None:
                    name = name_elem.text or ""
                if desc_elem is not None:
                    desc = desc_elem.text or ""
                results.append((child.tag, name, desc))
        
        return results
    
    @staticmethod
    def node_to_dict(node: ET.Element) -> Dict[str, Any]:
        """
        Convert an XML node to a dictionary (node's own data only).
        
        Includes type, attributes, and leaf child elements as fields.
        """
        result = {
            "type": node.tag,
            "attributes": dict(node.attrib)
        }
        
        # Add simple child elements as fields
        for child in node:
            if len(child) == 0:  # Leaf element
                result[child.tag] = child.text
            elif child.tag == "highlights":
                result["highlights"] = [h.text for h in child.findall("highlight")]
        
        return result
    
    @staticmethod
    def get_all_children(node: ET.Element) -> List[Dict[str, Any]]:
        """
        Get all POI/Restaurant children of a node as dictionaries.
        """
        children = []
        for child in node:
            if child.tag in ("POI", "Restaurant"):
                child_dict = {
                    "type": child.tag,
                    "name": "",
                    "description": "",
                    "time_block": "",
                    "expected_cost": "",
                    "highlights": []
                }
                for elem in child:
                    if elem.tag == "highlights":
                        child_dict["highlights"] = [h.text for h in elem.findall("highlight")]
                    elif elem.text:
                        child_dict[elem.tag] = elem.text
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



