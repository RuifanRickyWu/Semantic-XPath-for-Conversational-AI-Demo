"""
Unit tests for QueryParser - specifically testing OR expression handling.

Bug Description:
    When an OR expression is wrapped in outer parentheses like:
        (atom(content =~ "kid") OR atom(content =~ "child"))
    
    The parser fails to recognize it as an OR expression because:
    1. _split_logical_operator tracks paren_depth
    2. When it encounters '(' at the start, paren_depth becomes 1
    3. The OR operator is found at paren_depth=1, not 0
    4. Therefore, OR is NOT recognized as a split point
    5. The entire expression is returned as a single part
    6. It falls through to the fallback case and is treated as a raw string

Fix Required:
    Add logic in _parse_logical_predicate to strip outer grouping parentheses
    before attempting to parse logical operators.
"""

import unittest
import sys
import os

# Get absolute path to project root and semantic_xpath_execution
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_semantic_xpath_dir = os.path.join(_project_root, 'pipeline_execution', 'semantic_xpath_execution')

# Directly import models (has no external dependencies)
sys.path.insert(0, _semantic_xpath_dir)
from models import IndexRange, QueryStep, AtomicPredicate, CompoundPredicate

# Create a modified parser module that uses absolute imports
# We read the parser.py file and exec it with the models already imported
import re as _re
from typing import List, Optional, Tuple

_parser_code = open(os.path.join(_semantic_xpath_dir, 'parser.py')).read()
# Remove the relative import line since we already have models in scope
_parser_code = _parser_code.replace(
    'from .models import IndexRange, QueryStep, AtomicPredicate, CompoundPredicate',
    '# Models imported externally'
)
exec(_parser_code)
# QueryParser and get_parser are now available


class TestParserORExpression(unittest.TestCase):
    """Test cases for OR expression parsing bug."""
    
    def setUp(self):
        """Create parser instance for each test."""
        self.parser = QueryParser()
    
    # =========================================================================
    # Tests for _split_logical_operator method
    # =========================================================================
    
    def test_split_or_without_outer_parens(self):
        """OR without outer parentheses should split correctly."""
        expr = 'atom(content =~ "kid") OR atom(content =~ "child")'
        parts = self.parser._split_logical_operator(expr, ' OR ')
        
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], 'atom(content =~ "kid")')
        self.assertEqual(parts[1], 'atom(content =~ "child")')
    
    def test_split_or_with_outer_parens_bug(self):
        """
        BUG: OR with outer parentheses fails to split.
        
        This test documents the current broken behavior.
        After fix, this test should be updated to expect 2 parts.
        """
        expr = '(atom(content =~ "kid") OR atom(content =~ "child"))'
        parts = self.parser._split_logical_operator(expr, ' OR ')
        
        # CURRENT BROKEN BEHAVIOR: Returns 1 part (the whole expression)
        # After fix, should return 2 parts
        self.assertEqual(len(parts), 1, 
            "BUG CONFIRMED: Outer parens prevent OR from being recognized as split point")
    
    def test_split_and_without_outer_parens(self):
        """AND without outer parentheses should split correctly."""
        expr = 'atom(content =~ "outdoor") AND atom(content =~ "free")'
        parts = self.parser._split_logical_operator(expr, ' AND ')
        
        self.assertEqual(len(parts), 2)
    
    def test_split_and_with_outer_parens_bug(self):
        """
        BUG: AND with outer parentheses fails to split.
        """
        expr = '(atom(content =~ "outdoor") AND atom(content =~ "free"))'
        parts = self.parser._split_logical_operator(expr, ' AND ')
        
        # CURRENT BROKEN BEHAVIOR
        self.assertEqual(len(parts), 1,
            "BUG CONFIRMED: Outer parens prevent AND from being recognized")
    
    # =========================================================================
    # Tests for _parse_logical_predicate method
    # =========================================================================
    
    def test_parse_or_without_outer_parens(self):
        """OR expression without outer parens parses correctly."""
        expr = 'atom(content =~ "kid") OR atom(content =~ "child")'
        result = self.parser._parse_logical_predicate(expr)
        
        self.assertEqual(result.operator, "OR")
        self.assertEqual(len(result.conditions), 2)
        self.assertEqual(result.conditions[0].operator, "ATOM")
        self.assertEqual(result.conditions[1].operator, "ATOM")
    
    def test_parse_or_with_outer_parens_bug(self):
        """
        BUG: OR expression with outer parens is NOT parsed as OR.
        
        Instead, it falls through to fallback and is treated as raw content.
        """
        expr = '(atom(content =~ "kid") OR atom(content =~ "child"))'
        result = self.parser._parse_logical_predicate(expr)
        
        # CURRENT BROKEN BEHAVIOR: Falls back to ATOM with raw string
        self.assertEqual(result.operator, "ATOM",
            "BUG CONFIRMED: Expression wrongly parsed as ATOM instead of OR")
        
        # The entire expression becomes the atom value (wrong!)
        self.assertEqual(len(result.conditions), 1)
        self.assertIsInstance(result.conditions[0], AtomicPredicate)
        self.assertEqual(result.conditions[0].field, "content")
        self.assertIn("OR", result.conditions[0].value,
            "BUG: The OR keyword ended up in the atom value as raw text")
    
    def test_parse_and_with_outer_parens_bug(self):
        """
        BUG: AND expression with outer parens is NOT parsed as AND.
        """
        expr = '(atom(content =~ "outdoor") AND atom(content =~ "free"))'
        result = self.parser._parse_logical_predicate(expr)
        
        # CURRENT BROKEN BEHAVIOR
        self.assertEqual(result.operator, "ATOM",
            "BUG CONFIRMED: Expression wrongly parsed as ATOM instead of AND")
    
    # =========================================================================
    # Tests for full query parsing
    # =========================================================================
    
    def test_full_query_or_predicate_without_parens(self):
        """Full query with OR predicate (no outer parens) works."""
        query = '/Itinerary/Day/POI[atom(content =~ "kid") OR atom(content =~ "child")]'
        steps, global_idx = self.parser.parse(query)
        
        self.assertEqual(len(steps), 3)
        poi_step = steps[2]
        self.assertEqual(poi_step.node_type, "POI")
        self.assertIsNotNone(poi_step.predicate)
        self.assertEqual(poi_step.predicate.operator, "OR")
    
    def test_full_query_or_predicate_with_parens_bug(self):
        """
        BUG: Full query with OR predicate wrapped in parens fails.
        
        This is common when users want explicit grouping:
        POI[(A OR B) AND C] - the (A OR B) part fails
        """
        query = '/Itinerary/Day/POI[(atom(content =~ "kid") OR atom(content =~ "child"))]'
        steps, global_idx = self.parser.parse(query)
        
        self.assertEqual(len(steps), 3)
        poi_step = steps[2]
        
        # CURRENT BROKEN BEHAVIOR: OR not recognized
        self.assertEqual(poi_step.predicate.operator, "ATOM",
            "BUG CONFIRMED: OR predicate with parens wrongly parsed as ATOM")


class TestParserORExpressionFixed(unittest.TestCase):
    """
    Tests that should pass AFTER the bug is fixed.
    
    Run these to verify the fix works correctly.
    """
    
    def setUp(self):
        self.parser = QueryParser()
    
    @unittest.skip("ENABLE AFTER FIX: Currently fails due to bug")
    def test_split_or_with_outer_parens_fixed(self):
        """After fix: OR with outer parens should split correctly."""
        expr = '(atom(content =~ "kid") OR atom(content =~ "child"))'
        parts = self.parser._split_logical_operator(expr, ' OR ')
        
        # After stripping outer parens, should find 2 parts
        self.assertEqual(len(parts), 2)
    
    @unittest.skip("ENABLE AFTER FIX: Currently fails due to bug")
    def test_parse_or_with_outer_parens_fixed(self):
        """After fix: OR with outer parens parses as OR."""
        expr = '(atom(content =~ "kid") OR atom(content =~ "child"))'
        result = self.parser._parse_logical_predicate(expr)
        
        self.assertEqual(result.operator, "OR")
        self.assertEqual(len(result.conditions), 2)
    
    @unittest.skip("ENABLE AFTER FIX: Currently fails due to bug")
    def test_nested_grouping_fixed(self):
        """After fix: Nested grouping like ((A OR B) AND C) should work."""
        expr = '(atom(content =~ "kid") OR atom(content =~ "child")) AND atom(content =~ "activity")'
        result = self.parser._parse_logical_predicate(expr)
        
        self.assertEqual(result.operator, "AND")
        self.assertEqual(len(result.conditions), 2)
        
        # First condition should be the OR group
        self.assertEqual(result.conditions[0].operator, "OR")


class TestParserBasicFunctionality(unittest.TestCase):
    """Basic parser tests to ensure other functionality works."""
    
    def setUp(self):
        self.parser = QueryParser()
    
    def test_simple_atom(self):
        """Simple atom predicate."""
        result = self.parser._parse_logical_predicate('atom(content =~ "museum")')
        
        self.assertEqual(result.operator, "ATOM")
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0].field, "content")
        self.assertEqual(result.conditions[0].value, "museum")
    
    def test_not_predicate(self):
        """NOT predicate."""
        result = self.parser._parse_logical_predicate('not(atom(content =~ "expensive"))')
        
        self.assertEqual(result.operator, "NOT")
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0].operator, "ATOM")
    
    def test_simple_path(self):
        """Simple path parsing."""
        steps, global_idx = self.parser.parse('/Itinerary/Day/POI')
        
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].node_type, "Itinerary")
        self.assertEqual(steps[1].node_type, "Day")
        self.assertEqual(steps[2].node_type, "POI")
        self.assertIsNone(global_idx)
    
    def test_positional_index(self):
        """Positional index parsing."""
        steps, _ = self.parser.parse('/Itinerary/Day[2]/POI[-1]')
        
        self.assertEqual(steps[1].index.start, 2)
        self.assertEqual(steps[2].index.start, -1)
    
    def test_global_index(self):
        """Global index parsing."""
        steps, global_idx = self.parser.parse('(/Itinerary/Day/POI)[5]')
        
        self.assertIsNotNone(global_idx)
        self.assertEqual(global_idx.start, 5)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
