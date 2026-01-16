"""
Query Parser - Parses Semantic XPath query strings into structured QueryStep objects.

New Syntax (v2):
- Index: /Day[@index='2'] - XPath-style attribute index
- Semantic: /POI[sem(content =~ "museum")] - local node scoring
- Existential: /Day[exist(POI[sem(content =~ "museum")])] - Noisy-OR over children
- Prevalence: /Day[mass(POI[sem(content =~ "artistic")])] - Beta-Bernoulli over children
- Logical: sem(X) AND sem(Y), sem(X) OR sem(Y)
- Global index: (/Itinerary/Day/POI)[5] or (/Itinerary/Day/POI)[1:3]
"""

import re
from typing import List, Optional, Tuple

from .models import IndexRange, QueryStep, SemanticCondition, CompoundPredicate


class QueryParser:
    """
    Parses Semantic XPath queries into structured steps.
    
    Supports:
    - Type matching: /Itinerary/Day/POI
    - Attribute index: Day[@index='2']
    - Positional index: POI[2], POI[-1], POI[1:3]
    - Semantic predicates: POI[sem(content =~ "museum")]
    - Aggregation predicates: Day[exist(POI[sem(...)])], Day[mass(POI[sem(...)])]
    - Logical operators: sem(X) AND sem(Y), sem(X) OR sem(Y)
    - Global indexing: (/Itinerary/Day/POI)[5]
    """
    
    def parse(self, query: str) -> Tuple[List[QueryStep], Optional[IndexRange]]:
        """
        Parse a query string into steps and optional global index.
        
        Args:
            query: Semantic XPath query string
            
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
        """Parse a query into steps."""
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
    
    def _parse_step(self, step_str: str) -> Optional[QueryStep]:
        """
        Parse a single step like 'Day[@index='2']' or 'POI[sem(content =~ "museum")]'.
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
        
        # Extract all bracket contents
        brackets = self._extract_brackets(remaining)
        
        for bracket_content in brackets:
            # Check for attribute index: @index='2'
            attr_index_match = re.match(r'^@(\w+)\s*=\s*[\'"](\d+)[\'"]$', bracket_content)
            if attr_index_match:
                idx = int(attr_index_match.group(2))
                index = IndexRange(start=idx)
                continue
            
            # Check for semantic predicates (sem, exist, mass, AND, OR)
            # Use _parse_logical_predicate which handles all combinations
            if any(kw in bracket_content for kw in ['sem(', 'exist(', 'mass(']):
                predicate = self._parse_logical_predicate(bracket_content)
                predicate_str = bracket_content
                continue
            
            # Try to parse as numeric index or range
            parsed_index = self._parse_index(bracket_content)
            if parsed_index:
                index = parsed_index
        
        return QueryStep(
            node_type=node_type,
            predicate=predicate,
            index=index,
            predicate_str=predicate_str
        )
    
    def _parse_aggregation(self, operator: str, inner: str) -> CompoundPredicate:
        """
        Parse exist() or mass() aggregation.
        
        Formats:
        - exist(POI[sem(content =~ "museum")]) - with child type
        - exist(sem(content =~ "museum")) - without child type (applies to all children)
        """
        # Try to match ChildType[predicate] pattern
        child_type_match = re.match(r'^(\w+)\s*\[\s*(.+)\s*\]$', inner, re.DOTALL)
        
        if child_type_match:
            child_type = child_type_match.group(1)
            inner_pred_str = child_type_match.group(2).strip()
            child_predicate = self._parse_logical_predicate(inner_pred_str)
            
            return CompoundPredicate(
                operator=operator,
                conditions=[],
                child_predicate=child_predicate,
                child_type=child_type
            )
        else:
            # No child type - parse inner directly
            child_predicate = self._parse_logical_predicate(inner)
            return CompoundPredicate(
                operator=operator,
                conditions=[],
                child_predicate=child_predicate,
                child_type=None
            )
    
    def _parse_logical_predicate(self, pred_str: str) -> CompoundPredicate:
        """
        Parse a predicate that may contain AND/OR operators.
        
        Handles:
        - sem(content =~ "value")
        - sem(X) AND sem(Y)
        - sem(X) OR sem(Y)
        - exist(ChildType[sem(...)]) AND exist(ChildType[sem(...)])
        - mass(ChildType[sem(...)]) OR mass(ChildType[sem(...)])
        """
        pred_str = pred_str.strip()
        
        # Check for AND (split carefully to avoid breaking on AND inside quotes)
        and_parts = self._split_logical_operator(pred_str, ' AND ')
        if len(and_parts) > 1:
            conditions = [self._parse_logical_predicate(p) for p in and_parts]
            return CompoundPredicate(operator="AND", conditions=conditions)
        
        # Check for OR
        or_parts = self._split_logical_operator(pred_str, ' OR ')
        if len(or_parts) > 1:
            conditions = [self._parse_logical_predicate(p) for p in or_parts]
            return CompoundPredicate(operator="OR", conditions=conditions)
        
        # Check for exist() aggregation
        exist_match = re.match(r'^exist\s*\(\s*(.+)\s*\)$', pred_str, re.DOTALL)
        if exist_match:
            return self._parse_aggregation("EXIST", exist_match.group(1).strip())
        
        # Check for mass() aggregation
        mass_match = re.match(r'^mass\s*\(\s*(.+)\s*\)$', pred_str, re.DOTALL)
        if mass_match:
            return self._parse_aggregation("MASS", mass_match.group(1).strip())
        
        # Single sem() condition
        sem_match = re.match(r'^sem\s*\(\s*(\w+)\s*=~\s*["\']([^"\']+)["\']\s*\)$', pred_str)
        if sem_match:
            field = sem_match.group(1)
            value = sem_match.group(2)
            return CompoundPredicate(
                operator="SEM",
                conditions=[SemanticCondition(field=field, value=value)]
            )
        
        # Fallback: treat as simple value (for backward compatibility during transition)
        return CompoundPredicate(
            operator="SEM",
            conditions=[SemanticCondition(field="content", value=pred_str)]
        )
    
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
    
    def _extract_brackets(self, s: str) -> List[str]:
        """Extract bracket contents, handling nested brackets."""
        brackets = []
        i = 0
        while i < len(s):
            if s[i] == '[':
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
    
    def _split_logical_operator(self, s: str, operator: str) -> List[str]:
        """Split string by logical operator, respecting quotes and parentheses."""
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


# Singleton instance
_parser_instance = None


def get_parser() -> QueryParser:
    """Get singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser()
    return _parser_instance
