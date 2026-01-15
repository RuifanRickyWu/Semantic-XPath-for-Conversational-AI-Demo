"""
Query Parser - Parses XPath-like query strings into structured QueryStep objects.

Supports compound predicates with AND/OR operators and hierarchical quantifiers (exists/all).
"""

import re
from typing import List, Optional, Tuple

from .models import IndexRange, QueryStep, AtomicCondition, CompoundPredicate


class QueryParser:
    """
    Parses XPath-like queries into structured steps.
    
    Supports:
    - Type matching: /Itinerary/Day/POI
    - Positional indexing: Day[1], POI[2], POI[-1], POI[1:3]
    - Semantic predicates: Day[description =~ "artistic"]
    - Compound predicates with AND/OR: POI[description =~ "outdoor" AND description =~ "historic"]
    - Hierarchical quantifiers: Day[exists(POI[description =~ "museum"])]
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
        """
        Parse a single step like 'Day[description =~ "artistic"][2]' or 'POI[1:3]'.
        
        Supports:
        - Simple predicates: description =~ "value"
        - AND predicates: description =~ "A" AND description =~ "B"
        - OR predicates: description =~ "A" OR description =~ "B"
        - exists(): exists(description =~ "museum") - at least one child matches
        - all(): all(description =~ "local") - children generally match
        """
        # Extract node type (everything before first [)
        match = re.match(r'^([A-Za-z]+)', step_str)
        if not match:
            return None
        
        node_type = match.group(1)
        remaining = step_str[len(node_type):]
        
        predicate = None
        predicate_str = None
        index = None
        
        # Extract all bracket contents, handling nested brackets
        brackets = self._extract_brackets(remaining)
        
        for bracket_content in brackets:
            # Check if it's a hierarchical quantifier (exists/all)
            # New syntax: exists(description =~ "museum") - applies to all children
            exists_match = re.match(r'^exists\s*\(\s*(.+)\s*\)$', bracket_content)
            all_match = re.match(r'^all\s*\(\s*(.+)\s*\)$', bracket_content)
            
            if exists_match:
                inner_pred_str = exists_match.group(1).strip()
                inner_pred = self._parse_predicate(inner_pred_str)
                predicate = CompoundPredicate(
                    operator="EXISTS",
                    conditions=[],
                    child_predicate=inner_pred,
                    child_type=None  # No specific child type - applies to all children
                )
                predicate_str = bracket_content
            elif all_match:
                inner_pred_str = all_match.group(1).strip()
                inner_pred = self._parse_predicate(inner_pred_str)
                predicate = CompoundPredicate(
                    operator="ALL",
                    conditions=[],
                    child_predicate=inner_pred,
                    child_type=None  # No specific child type - applies to all children
                )
                predicate_str = bracket_content
            # Check if it's a semantic predicate (=~) without quantifier wrapper - REJECT
            elif '=~' in bracket_content:
                raise ValueError(
                    f"Invalid predicate syntax: [{bracket_content}]. "
                    f"Predicates must be wrapped in all() or exists(). "
                    f"Example: [all({bracket_content})] or [exists({bracket_content})]"
                )
            else:
                # Try to parse as index or range
                parsed_index = self._parse_index(bracket_content)
                if parsed_index:
                    index = parsed_index
        
        return QueryStep(
            node_type=node_type, 
            predicate=predicate, 
            index=index,
            predicate_str=predicate_str
        )
    
    def _extract_brackets(self, s: str) -> List[str]:
        """
        Extract bracket contents, handling nested brackets for exists()/all().
        
        Returns a list of bracket contents in order.
        """
        brackets = []
        i = 0
        while i < len(s):
            if s[i] == '[':
                # Find matching closing bracket
                depth = 1
                start = i + 1
                i += 1
                while i < len(s) and depth > 0:
                    if s[i] == '[':
                        depth += 1
                    elif s[i] == ']':
                        depth -= 1
                    i += 1
                brackets.append(s[start:i-1])
            else:
                i += 1
        return brackets
    
    def _parse_predicate(self, predicate_str: str) -> CompoundPredicate:
        """
        Parse a predicate string into a CompoundPredicate AST.
        
        This is used for parsing the INNER content of all()/exists() wrappers.
        
        Handles:
        - Simple: description =~ "value"
        - AND: description =~ "A" AND description =~ "B"
        - OR: description =~ "A" OR description =~ "B"
        - Nested exists/all (recursive)
        """
        predicate_str = predicate_str.strip()
        
        # Check for exists()/all() quantifiers
        # New syntax: exists(inner_predicate) - no child type needed
        exists_match = re.match(r'^exists\s*\(\s*(.+)\s*\)$', predicate_str)
        all_match = re.match(r'^all\s*\(\s*(.+)\s*\)$', predicate_str)
        
        if exists_match:
            inner_pred_str = exists_match.group(1).strip()
            return CompoundPredicate(
                operator="EXISTS",
                conditions=[],
                child_predicate=self._parse_predicate(inner_pred_str),
                child_type=None  # Applies to all children
            )
        
        if all_match:
            inner_pred_str = all_match.group(1).strip()
            return CompoundPredicate(
                operator="ALL",
                conditions=[],
                child_predicate=self._parse_predicate(inner_pred_str),
                child_type=None  # Applies to all children
            )
        
        # Check for AND (split carefully to avoid breaking on AND inside quotes)
        and_parts = self._split_logical_operator(predicate_str, ' AND ')
        if len(and_parts) > 1:
            return CompoundPredicate(
                operator="AND",
                conditions=[self._parse_predicate(p) for p in and_parts]
            )
        
        # Check for OR
        or_parts = self._split_logical_operator(predicate_str, ' OR ')
        if len(or_parts) > 1:
            return CompoundPredicate(
                operator="OR",
                conditions=[self._parse_predicate(p) for p in or_parts]
            )
        
        # Atomic condition
        atomic = self._parse_atomic(predicate_str)
        if atomic:
            return CompoundPredicate(operator="ATOMIC", conditions=[atomic])
        
        # Fallback: treat as simple value
        return CompoundPredicate(
            operator="ATOMIC",
            conditions=[AtomicCondition(field="description", value=predicate_str)]
        )
    
    def _split_logical_operator(self, s: str, operator: str) -> List[str]:
        """
        Split string by logical operator, respecting quotes and parentheses.
        """
        parts = []
        current = ""
        i = 0
        quote_char = None
        paren_depth = 0
        
        while i < len(s):
            # Handle quotes
            if s[i] in ('"', "'") and paren_depth == 0:
                if quote_char is None:
                    quote_char = s[i]
                elif s[i] == quote_char:
                    quote_char = None
                current += s[i]
                i += 1
            # Handle parentheses
            elif s[i] == '(' and quote_char is None:
                paren_depth += 1
                current += s[i]
                i += 1
            elif s[i] == ')' and quote_char is None:
                paren_depth -= 1
                current += s[i]
                i += 1
            # Check for operator
            elif quote_char is None and paren_depth == 0 and s[i:i+len(operator)] == operator:
                parts.append(current.strip())
                current = ""
                i += len(operator)
            else:
                current += s[i]
                i += 1
        
        if current.strip():
            parts.append(current.strip())
        
        return parts
    
    def _parse_atomic(self, predicate_str: str) -> Optional[AtomicCondition]:
        """
        Parse an atomic condition like 'description =~ "museum"' or 'context =~ "home office"'.
        """
        # Match patterns like: field =~ "value" or field =~ 'value'
        match = re.match(r'(\w+)\s*=~\s*["\']([^"\']+)["\']', predicate_str.strip())
        if match:
            field, value = match.groups()
            return AtomicCondition(field=field, value=value)
        return None


# Singleton instance for convenience
_parser_instance = None


def get_parser() -> QueryParser:
    """Get singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser()
    return _parser_instance

