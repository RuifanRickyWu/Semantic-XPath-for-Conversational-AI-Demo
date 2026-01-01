"""
Query Parser - Parses XPath-like query strings into structured QueryStep objects.
"""

import re
from typing import List, Optional, Tuple

from .models import IndexRange, QueryStep


class QueryParser:
    """
    Parses XPath-like queries into structured steps.
    
    Supports:
    - Type matching: /Itinerary/Day/POI
    - Positional indexing: Day[1], POI[2], POI[-1], POI[1:3]
    - Semantic predicates: Day[description =~ "artistic"]
    - Global indexing: (/Itinerary/Day/POI)[5] or (/Itinerary/Day/POI)[1:3]
    - Combined: Day[description =~ "artistic"][2]
    """
    
    def parse(self, query: str) -> Tuple[List[QueryStep], Optional[IndexRange]]:
        """
        Parse a query string into steps and optional global index.
        
        Args:
            query: XPath-like query string
            
        Returns:
            Tuple of (list of QueryStep, optional global IndexRange)
        """
        global_index = None
        inner_query = query
        
        # Check for global indexing with "to end" range: (/path)[-2:]
        global_to_end_match = re.match(r'^\((.+)\)\[(-?\d+):\]$', query)
        if global_to_end_match:
            inner_query = global_to_end_match.group(1)
            start = int(global_to_end_match.group(2))
            global_index = IndexRange(start=start, to_end=True)
        else:
            # Check for global indexing with range: (/path)[1:3]
            global_range_match = re.match(r'^\((.+)\)\[(-?\d+):(-?\d+)\]$', query)
            if global_range_match:
                inner_query = global_range_match.group(1)
                start = int(global_range_match.group(2))
                end = int(global_range_match.group(3))
                global_index = IndexRange(start=start, end=end)
            else:
                # Check for global indexing with single index: (/path)[n]
                global_single_match = re.match(r'^\((.+)\)\[(-?\d+)\]$', query)
                if global_single_match:
                    inner_query = global_single_match.group(1)
                    idx = int(global_single_match.group(2))
                    global_index = IndexRange(start=idx)
        
        # Parse the inner query into steps
        steps = self._parse_steps(inner_query)
        
        return steps, global_index
    
    def _parse_steps(self, query: str) -> List[QueryStep]:
        """Parse an XPath query into steps."""
        steps = []
        
        # Remove leading slash
        if query.startswith("/"):
            query = query[1:]
        
        # Split by / but respect brackets
        parts = self._split_path(query)
        
        for part in parts:
            step = self._parse_step(part)
            if step:
                steps.append(step)
        
        return steps
    
    def _split_path(self, query: str) -> List[str]:
        """Split path by / while respecting brackets."""
        parts = []
        current = ""
        bracket_depth = 0
        
        for char in query:
            if char == "[":
                bracket_depth += 1
                current += char
            elif char == "]":
                bracket_depth -= 1
                current += char
            elif char == "/" and bracket_depth == 0:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts
    
    def _parse_index(self, index_str: str) -> Optional[IndexRange]:
        """Parse an index string like '2', '-1', '1:3', or '-2:' (to end)."""
        index_str = index_str.strip()
        
        # Check for range format
        if ':' in index_str:
            parts = index_str.split(':')
            if len(parts) == 2:
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                try:
                    start = int(start_str)
                    
                    # Check if end is empty (to_end syntax like [-2:])
                    if end_str == '':
                        return IndexRange(start=start, to_end=True)
                    else:
                        end = int(end_str)
                        return IndexRange(start=start, end=end)
                except ValueError:
                    return None
        else:
            # Single index
            try:
                return IndexRange(start=int(index_str))
            except ValueError:
                return None
        return None
    
    def _parse_step(self, step_str: str) -> Optional[QueryStep]:
        """Parse a single step like 'Day[description =~ "artistic"][2]' or 'POI[1:3]'."""
        # Extract node type (everything before first [)
        match = re.match(r'^([A-Za-z]+)', step_str)
        if not match:
            return None
        
        node_type = match.group(1)
        remaining = step_str[len(node_type):]
        
        predicate = None
        index = None
        
        # Extract predicates and indexes from brackets
        bracket_pattern = r'\[([^\]]+)\]'
        brackets = re.findall(bracket_pattern, remaining)
        
        for bracket_content in brackets:
            # Check if it's a semantic predicate
            pred_match = re.match(r'description\s*=~\s*["\']([^"\']+)["\']', bracket_content)
            if pred_match:
                predicate = pred_match.group(1)
            else:
                # Try to parse as index or range
                parsed_index = self._parse_index(bracket_content)
                if parsed_index:
                    index = parsed_index
        
        return QueryStep(node_type=node_type, predicate=predicate, index=index)


# Singleton instance for convenience
_parser_instance = None


def get_parser() -> QueryParser:
    """Get singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser()
    return _parser_instance

