"""
Unit tests for the new tokenizer + recursive-descent predicate parser.

Tests cover:
- Tokenizer correctness
- Basic predicate parsing (atom, not, agg_exists, agg_prev)
- Logical operators (AND, OR) with correct precedence
- Parenthesized grouping (the original bug that motivated the rewrite)
- Nested/complex expressions
- Full XPath query parsing (path + predicates)
"""

import unittest
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline_execution.semantic_xpath_parsing import (
    QueryParser,
    get_parser,
    parse_predicate,
    QueryStep,
    IndexRange,
)
from pipeline_execution.semantic_xpath_parsing.predicate_ast import (
    PredicateNode,
    AtomPredicate,
    AggExistsPredicate,
    AggPrevPredicate,
    AndPredicate,
    OrPredicate,
    NotPredicate,
    tokenize,
    TokenType,
)


# =============================================================================
# Tokenizer Tests
# =============================================================================

class TestTokenizer(unittest.TestCase):

    def test_atom_expression(self):
        tokens = tokenize('atom(content =~ "museum")')
        types = [t.type for t in tokens]
        self.assertEqual(types, [
            TokenType.ATOM, TokenType.LPAREN, TokenType.IDENT,
            TokenType.TILDE_EQ, TokenType.STRING, TokenType.RPAREN,
            TokenType.EOF,
        ])
        self.assertEqual(tokens[2].value, "content")
        self.assertEqual(tokens[4].value, "museum")

    def test_or_expression(self):
        tokens = tokenize('atom(content =~ "kid") OR atom(content =~ "child")')
        types = [t.type for t in tokens]
        self.assertIn(TokenType.OR, types)

    def test_and_expression(self):
        tokens = tokenize('atom(content =~ "outdoor") AND atom(content =~ "free")')
        types = [t.type for t in tokens]
        self.assertIn(TokenType.AND, types)

    def test_agg_exists(self):
        tokens = tokenize('agg_exists(POI[atom(content =~ "museum")])')
        self.assertEqual(tokens[0].type, TokenType.AGG_EXISTS)
        self.assertEqual(tokens[2].type, TokenType.IDENT)
        self.assertEqual(tokens[2].value, "POI")

    def test_not(self):
        tokens = tokenize('not(atom(content =~ "expensive"))')
        self.assertEqual(tokens[0].type, TokenType.NOT)

    def test_coloncolon(self):
        tokens = tokenize('desc::POI')
        self.assertEqual(tokens[0].type, TokenType.IDENT)
        self.assertEqual(tokens[0].value, "desc")
        self.assertEqual(tokens[1].type, TokenType.COLONCOLON)
        self.assertEqual(tokens[2].type, TokenType.IDENT)
        self.assertEqual(tokens[2].value, "POI")

    def test_single_quoted_string(self):
        tokens = tokenize("atom(content =~ 'museum')")
        self.assertEqual(tokens[4].type, TokenType.STRING)
        self.assertEqual(tokens[4].value, "museum")


# =============================================================================
# Predicate Parser Tests - Base Cases
# =============================================================================

class TestPredicateParserBaseCases(unittest.TestCase):

    def test_simple_atom(self):
        result = parse_predicate('atom(content =~ "museum")')
        self.assertIsInstance(result, AtomPredicate)
        self.assertEqual(result.field, "content")
        self.assertEqual(result.value, "museum")

    def test_not_atom(self):
        result = parse_predicate('not(atom(content =~ "expensive"))')
        self.assertIsInstance(result, NotPredicate)
        self.assertIsInstance(result.child, AtomPredicate)
        self.assertEqual(result.child.value, "expensive")

    def test_agg_exists_with_child_type(self):
        result = parse_predicate('agg_exists(POI[atom(content =~ "museum")])')
        self.assertIsInstance(result, AggExistsPredicate)
        self.assertEqual(result.child_type, "POI")
        self.assertEqual(result.child_axis, "child")
        self.assertIsInstance(result.inner, AtomPredicate)
        self.assertEqual(result.inner.value, "museum")

    def test_agg_prev_with_child_type(self):
        result = parse_predicate('agg_prev(POI[atom(content =~ "artistic")])')
        self.assertIsInstance(result, AggPrevPredicate)
        self.assertEqual(result.child_type, "POI")
        self.assertIsInstance(result.inner, AtomPredicate)

    def test_agg_exists_with_desc_axis(self):
        result = parse_predicate('agg_exists(desc::SubTask[atom(content =~ "review")])')
        self.assertIsInstance(result, AggExistsPredicate)
        self.assertEqual(result.child_axis, "desc")
        self.assertEqual(result.child_type, "SubTask")

    def test_agg_exists_without_child_type(self):
        result = parse_predicate('agg_exists(atom(content =~ "museum"))')
        self.assertIsInstance(result, AggExistsPredicate)
        self.assertIsNone(result.child_type)
        self.assertIsInstance(result.inner, AtomPredicate)


# =============================================================================
# Predicate Parser Tests - Logical Operators
# =============================================================================

class TestPredicateParserLogical(unittest.TestCase):

    def test_simple_or(self):
        result = parse_predicate('atom(content =~ "kid") OR atom(content =~ "child")')
        self.assertIsInstance(result, OrPredicate)
        self.assertEqual(len(result.children), 2)
        self.assertIsInstance(result.children[0], AtomPredicate)
        self.assertIsInstance(result.children[1], AtomPredicate)
        self.assertEqual(result.children[0].value, "kid")
        self.assertEqual(result.children[1].value, "child")

    def test_simple_and(self):
        result = parse_predicate('atom(content =~ "outdoor") AND atom(content =~ "free")')
        self.assertIsInstance(result, AndPredicate)
        self.assertEqual(len(result.children), 2)

    def test_or_with_outer_parens(self):
        """This was the original bug - outer parens broke OR parsing."""
        result = parse_predicate('(atom(content =~ "kid") OR atom(content =~ "child"))')
        self.assertIsInstance(result, OrPredicate)
        self.assertEqual(len(result.children), 2)
        self.assertEqual(result.children[0].value, "kid")
        self.assertEqual(result.children[1].value, "child")

    def test_and_with_outer_parens(self):
        result = parse_predicate('(atom(content =~ "outdoor") AND atom(content =~ "free"))')
        self.assertIsInstance(result, AndPredicate)
        self.assertEqual(len(result.children), 2)

    def test_precedence_and_binds_tighter_than_or(self):
        """A OR B AND C should parse as Or(A, And(B, C))."""
        result = parse_predicate(
            'atom(content =~ "a") OR atom(content =~ "b") AND atom(content =~ "c")'
        )
        self.assertIsInstance(result, OrPredicate)
        self.assertEqual(len(result.children), 2)
        self.assertIsInstance(result.children[0], AtomPredicate)
        self.assertIsInstance(result.children[1], AndPredicate)
        self.assertEqual(result.children[1].children[0].value, "b")
        self.assertEqual(result.children[1].children[1].value, "c")

    def test_parens_override_precedence(self):
        """(A OR B) AND C should parse as And(Or(A, B), C)."""
        result = parse_predicate(
            '(atom(content =~ "a") OR atom(content =~ "b")) AND atom(content =~ "c")'
        )
        self.assertIsInstance(result, AndPredicate)
        self.assertEqual(len(result.children), 2)
        self.assertIsInstance(result.children[0], OrPredicate)
        self.assertIsInstance(result.children[1], AtomPredicate)

    def test_not_with_complex_inner(self):
        result = parse_predicate('not(atom(content =~ "a") OR atom(content =~ "b"))')
        self.assertIsInstance(result, NotPredicate)
        self.assertIsInstance(result.child, OrPredicate)
        self.assertEqual(len(result.child.children), 2)

    def test_triple_or(self):
        result = parse_predicate(
            'atom(content =~ "a") OR atom(content =~ "b") OR atom(content =~ "c")'
        )
        self.assertIsInstance(result, OrPredicate)
        self.assertEqual(len(result.children), 3)

    def test_nested_or_and(self):
        """(A OR B) AND not(C OR D)"""
        result = parse_predicate(
            '(atom(content =~ "a") OR atom(content =~ "b")) '
            'AND not(atom(content =~ "c") OR atom(content =~ "d"))'
        )
        self.assertIsInstance(result, AndPredicate)
        self.assertIsInstance(result.children[0], OrPredicate)
        self.assertIsInstance(result.children[1], NotPredicate)
        self.assertIsInstance(result.children[1].child, OrPredicate)


# =============================================================================
# Predicate Parser Tests - Aggregation with Complex Inner
# =============================================================================

class TestPredicateParserAggComplex(unittest.TestCase):

    def test_agg_exists_with_or_inner(self):
        result = parse_predicate(
            'agg_exists(POI[atom(content =~ "kid") OR atom(content =~ "child")])'
        )
        self.assertIsInstance(result, AggExistsPredicate)
        self.assertEqual(result.child_type, "POI")
        self.assertIsInstance(result.inner, OrPredicate)
        self.assertEqual(len(result.inner.children), 2)

    def test_agg_prev_with_and_inner(self):
        result = parse_predicate(
            'agg_prev(Restaurant[atom(content =~ "italian") AND atom(content =~ "casual")])'
        )
        self.assertIsInstance(result, AggPrevPredicate)
        self.assertEqual(result.child_type, "Restaurant")
        self.assertIsInstance(result.inner, AndPredicate)


# =============================================================================
# AST Node Method Tests
# =============================================================================

class TestASTNodeMethods(unittest.TestCase):

    def test_get_all_atomic_values_atom(self):
        node = AtomPredicate(field="content", value="museum")
        self.assertEqual(node.get_all_atomic_values(), ["museum"])

    def test_get_all_atomic_values_or(self):
        node = OrPredicate(children=[
            AtomPredicate(field="content", value="kid"),
            AtomPredicate(field="content", value="child"),
        ])
        self.assertEqual(sorted(node.get_all_atomic_values()), ["child", "kid"])

    def test_get_all_atomic_values_agg(self):
        node = AggExistsPredicate(
            inner=AtomPredicate(field="content", value="museum"),
            child_type="POI",
        )
        self.assertEqual(node.get_all_atomic_values(), ["museum"])

    def test_get_all_atomic_values_nested(self):
        node = AndPredicate(children=[
            OrPredicate(children=[
                AtomPredicate(field="content", value="a"),
                AtomPredicate(field="content", value="b"),
            ]),
            NotPredicate(child=AtomPredicate(field="content", value="c")),
        ])
        self.assertEqual(sorted(node.get_all_atomic_values()), ["a", "b", "c"])

    def test_to_dict_atom(self):
        node = AtomPredicate(field="content", value="museum")
        d = node.to_dict()
        self.assertEqual(d, {"type": "atom", "field": "content", "value": "museum"})

    def test_repr_roundtrip(self):
        """__repr__ should reconstruct valid syntax."""
        node = parse_predicate('atom(content =~ "museum")')
        self.assertEqual(repr(node), 'atom(content =~ "museum")')


# =============================================================================
# Full Query Parser Tests
# =============================================================================

class TestQueryParser(unittest.TestCase):

    def setUp(self):
        self.parser = QueryParser()

    def test_simple_path(self):
        steps, global_idx = self.parser.parse('/Itinerary/Day/POI')
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].node_type, "Itinerary")
        self.assertEqual(steps[1].node_type, "Day")
        self.assertEqual(steps[2].node_type, "POI")
        self.assertIsNone(global_idx)

    def test_positional_index(self):
        steps, _ = self.parser.parse('/Itinerary/Day[2]/POI[-1]')
        self.assertEqual(steps[1].index.start, 2)
        self.assertEqual(steps[2].index.start, -1)

    def test_global_index(self):
        steps, global_idx = self.parser.parse('(/Itinerary/Day/POI)[5]')
        self.assertIsNotNone(global_idx)
        self.assertEqual(global_idx.start, 5)
        self.assertEqual(len(steps), 3)

    def test_atom_predicate(self):
        steps, _ = self.parser.parse('/Itinerary/Day/POI[atom(content =~ "museum")]')
        poi = steps[2]
        self.assertIsInstance(poi.predicate, AtomPredicate)
        self.assertEqual(poi.predicate.value, "museum")

    def test_or_predicate_without_parens(self):
        steps, _ = self.parser.parse(
            '/Itinerary/Day/POI[atom(content =~ "kid") OR atom(content =~ "child")]'
        )
        poi = steps[2]
        self.assertIsInstance(poi.predicate, OrPredicate)
        self.assertEqual(len(poi.predicate.children), 2)

    def test_or_predicate_with_parens(self):
        """Previously broken: outer parens in predicate bracket."""
        steps, _ = self.parser.parse(
            '/Itinerary/Day/POI[(atom(content =~ "kid") OR atom(content =~ "child"))]'
        )
        poi = steps[2]
        self.assertIsInstance(poi.predicate, OrPredicate)
        self.assertEqual(len(poi.predicate.children), 2)

    def test_index_and_predicate(self):
        steps, _ = self.parser.parse(
            '/Itinerary/Day[2][agg_exists(POI[atom(content =~ "museum")])]'
        )
        day = steps[1]
        self.assertEqual(day.index.start, 2)
        self.assertIsInstance(day.predicate, AggExistsPredicate)

    def test_desc_axis(self):
        steps, _ = self.parser.parse('/Itinerary/desc::POI[atom(content =~ "museum")]')
        poi = steps[1]
        self.assertEqual(poi.axis, "desc")
        self.assertEqual(poi.node_type, "POI")

    def test_not_predicate(self):
        steps, _ = self.parser.parse(
            '/Itinerary/Day/Restaurant[not(atom(content =~ "expensive"))]'
        )
        rest = steps[2]
        self.assertIsInstance(rest.predicate, NotPredicate)
        self.assertIsInstance(rest.predicate.child, AtomPredicate)


if __name__ == '__main__':
    unittest.main(verbosity=2)
