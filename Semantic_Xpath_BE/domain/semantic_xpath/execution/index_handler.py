"""
Index Handler - Applies positional indexing to node lists.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Union

from domain.semantic_xpath.parsing.parsing_models import Index, IndexRange


class IndexHandler:
    """
    Handles positional index operations on node lists.
    
    Supports:
    - Single positive index: [1], [2] (1-based)
    - Negative index: [-1] (last element)
    - Range index: [1:3] (inclusive on both ends)
    - Range to end: [-2:] (last N elements)
    """
    
    @staticmethod
    def apply_index(
        nodes: List[ET.Element],
        index: Union[IndexRange, Index],
        execution_log: List[str] = None
    ) -> List[ET.Element]:
        """
        Apply positional index or range to nodes.
        
        Args:
            nodes: List of XML elements to select from
            index: IndexRange specifying position(s) to select
            execution_log: Deprecated and ignored.
            
        Returns:
            List of selected nodes
        """
        if not nodes:
            return []
        
        if index.to_end:
            return IndexHandler._apply_to_end_index(nodes, index)
        elif index.is_range:
            return IndexHandler._apply_range_index(nodes, index)
        else:
            return IndexHandler._apply_single_index(nodes, index)
    
    @staticmethod
    def _apply_to_end_index(
        nodes: List[ET.Element],
        index: Union[IndexRange, Index],
    ) -> List[ET.Element]:
        """Apply 'to end' indexing like [-2:] (from position to end)."""
        n = len(nodes)
        start_val = index.start
        
        if start_val < 0:
            # Negative index: -2 means "from 2nd to last" = last 2 elements
            # Python: nodes[-2:] gives last 2
            start_idx = n + start_val
            start_idx = max(0, start_idx)  # Clamp to 0
        else:
            # Positive index: 3 means "from 3rd to end" (1-based)
            start_idx = start_val - 1
        
        if start_idx < n:
            return nodes[start_idx:]
        return []
    
    @staticmethod
    def _apply_range_index(
        nodes: List[ET.Element],
        index: Union[IndexRange, Index],
    ) -> List[ET.Element]:
        """Apply range indexing [start:end] (both 1-based, inclusive)."""
        start_idx = index.start - 1  # Convert to 0-based
        end_idx = index.end  # end is inclusive, so we use it directly for slice
        
        # Clamp to valid range
        start_idx = max(0, start_idx)
        end_idx = min(len(nodes), end_idx)
        
        if start_idx < len(nodes):
            return nodes[start_idx:end_idx]
        return []
    
    @staticmethod
    def _apply_single_index(
        nodes: List[ET.Element],
        index: Union[IndexRange, Index],
    ) -> List[ET.Element]:
        """Apply single index (1-based positive, or negative from end)."""
        idx_val = index.start
        n = len(nodes)
        
        if idx_val > 0:
            # Positive: 1-based (1 = first element)
            idx = idx_val - 1
        elif idx_val < 0:
            # Negative: from end (-1 = last, -2 = second from last)
            idx = n + idx_val
        else:
            # Zero index is invalid in 1-based system
            return []
        
        if 0 <= idx < n:
            return [nodes[idx]]
        return []

    @staticmethod
    def apply_relative_index(
        nodes: List[ET.Element],
        offset: int,
        parent_map: Dict[ET.Element, ET.Element],
    ) -> List[Tuple[ET.Element, ET.Element]]:
        """
        For each node in nodes, return (sibling, anchor) when sibling exists.
        offset > 0: next sibling(s) (e.g. +1 = immediate next)
        offset < 0: previous sibling(s) (e.g. -1 = immediate previous)

        Args:
            nodes: Anchor nodes (e.g. nodes matching a predicate)
            offset: Sibling offset (+1, -1, +2, -2, etc.)
            parent_map: Map from child element to parent element

        Returns:
            List of (sibling_node, anchor_node) pairs
        """
        result: List[Tuple[ET.Element, ET.Element]] = []
        for node in nodes:
            parent = parent_map.get(node)
            if parent is None:
                continue
            siblings = list(parent)
            try:
                idx = siblings.index(node)
            except ValueError:
                continue
            target_idx = idx + offset
            if 0 <= target_idx < len(siblings):
                result.append((siblings[target_idx], node))
        return result


# Convenience function
apply_index = IndexHandler.apply_index
