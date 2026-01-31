"""
Tests for NOT and AND operators in the Semantic XPath system.

Tests verify:
1. Parser correctly parses not() and AND predicates
2. Predicate handler scores NOT as (1 - inner_score)
3. Predicate handler scores AND as min(scores) instead of product
4. End-to-end execution with NOT and AND operators
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dense_xpath.parser import QueryParser
from dense_xpath.models import CompoundPredicate, AtomicPredicate
from dense_xpath.predicate_handler import PredicateHandler
from predicate_classifier import CosinePredicateScorer
import xml.etree.ElementTree as ET
import yaml


class TestNotAndParsing:
    """Tests for parsing NOT and AND operators."""
    
    def __init__(self):
        self.parser = QueryParser()
    
    def test_parse_not_operator(self):
        """Test: Parse not(atom(...)) syntax."""
        query = "/Itinerary/Day/POI[not(atom(content =~ \"work related\"))]"
        steps, global_idx = self.parser.parse(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Parse NOT Operator")
        print(f"Input: {query}")
        
        assert len(steps) == 3, f"Expected 3 steps, got {len(steps)}"
        poi_step = steps[2]
        assert poi_step.predicate is not None, "POI step should have predicate"
        assert poi_step.predicate.operator == "NOT", f"Expected NOT operator, got {poi_step.predicate.operator}"
        
        # Check inner predicate is ATOM
        inner = poi_step.predicate.conditions[0]
        assert inner.operator == "ATOM", f"Inner should be ATOM, got {inner.operator}"
        assert inner.conditions[0].value == "work related", f"Value should be 'work related'"
        
        print(f"Parsed predicate: {poi_step.predicate}")
        print("✅ PASSED: NOT operator parsed correctly")
        return poi_step.predicate
    
    def test_parse_nested_not(self):
        """Test: Parse nested not(agg_exists(...)) syntax."""
        query = "/Itinerary/Day[not(agg_exists(POI[atom(content =~ \"expensive\")]))]"
        steps, global_idx = self.parser.parse(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Parse Nested NOT with Aggregation")
        print(f"Input: {query}")
        
        day_step = steps[1]
        assert day_step.predicate.operator == "NOT", f"Expected NOT, got {day_step.predicate.operator}"
        
        inner = day_step.predicate.conditions[0]
        assert inner.operator == "AGG_EXISTS", f"Inner should be AGG_EXISTS, got {inner.operator}"
        
        print(f"Parsed predicate: {day_step.predicate}")
        print("✅ PASSED: Nested NOT with aggregation parsed correctly")
        return day_step.predicate
    
    def test_parse_and_operator(self):
        """Test: Parse AND operator."""
        query = "/Itinerary/Day/POI[atom(content =~ \"museum\") AND atom(content =~ \"art\")]"
        steps, global_idx = self.parser.parse(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Parse AND Operator")
        print(f"Input: {query}")
        
        poi_step = steps[2]
        assert poi_step.predicate.operator == "AND", f"Expected AND, got {poi_step.predicate.operator}"
        assert len(poi_step.predicate.conditions) == 2, "AND should have 2 conditions"
        
        print(f"Parsed predicate: {poi_step.predicate}")
        print("✅ PASSED: AND operator parsed correctly")
        return poi_step.predicate
    
    def test_parse_combined_and_not(self):
        """Test: Parse AND combined with NOT."""
        query = "/Itinerary/Day/POI[atom(content =~ \"museum\") AND not(atom(content =~ \"expensive\"))]"
        steps, global_idx = self.parser.parse(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Parse AND Combined with NOT")
        print(f"Input: {query}")
        
        poi_step = steps[2]
        assert poi_step.predicate.operator == "AND", f"Expected AND, got {poi_step.predicate.operator}"
        
        # Second condition should be NOT
        second_cond = poi_step.predicate.conditions[1]
        assert second_cond.operator == "NOT", f"Second condition should be NOT, got {second_cond.operator}"
        
        print(f"Parsed predicate: {poi_step.predicate}")
        print("✅ PASSED: AND combined with NOT parsed correctly")
        return poi_step.predicate
    
    def test_get_all_atomic_values_with_not(self):
        """Test: get_all_atomic_values extracts values from NOT predicates."""
        query = "/Itinerary/Day/POI[not(atom(content =~ \"work related\"))]"
        steps, _ = self.parser.parse(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Extract Atomic Values from NOT")
        
        poi_step = steps[2]
        values = poi_step.predicate.get_all_atomic_values()
        
        assert "work related" in values, f"Should extract 'work related', got {values}"
        
        print(f"Extracted values: {values}")
        print("✅ PASSED: Atomic values extracted from NOT predicate")
        return values


class TestNotAndScoring:
    """Tests for scoring NOT and AND operators."""
    
    def __init__(self):
        # Load schema
        schema_path = Path(__file__).parent.parent / "storage" / "schemas" / "itinerary.yaml"
        with open(schema_path) as f:
            self.schema = yaml.safe_load(f)
        
        # Initialize scorer and handler
        self.scorer = CosinePredicateScorer()
        self.handler = PredicateHandler(
            scorer=self.scorer,
            top_k=10,
            score_threshold=0.0,
            schema=self.schema
        )
        
        # Load sample XML
        xml_path = Path(__file__).parent.parent / "storage" / "memory" / "travel" / "travel_memory_3day.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Get the Itinerary element
        self.itinerary = root.find(".//Itinerary")
        self.pois = list(self.itinerary.iter("POI"))
    
    def test_not_score_inversion(self):
        """Test: NOT operator inverts scores (1 - score)."""
        print(f"\n{'='*60}")
        print(f"Test: NOT Score Inversion")
        
        # Create atomic predicate for "museum"
        atom_pred = CompoundPredicate(
            operator="ATOM",
            conditions=[AtomicPredicate(field="content", value="museum")]
        )
        
        # Create NOT predicate
        not_pred = CompoundPredicate(
            operator="NOT",
            conditions=[atom_pred]
        )
        
        # Score a POI that IS a museum (Art Gallery of Ontario)
        museum_poi = None
        for poi in self.pois:
            name_elem = poi.find("name")
            if name_elem is not None and "Art Gallery" in name_elem.text:
                museum_poi = poi
                break
        
        if museum_poi is None:
            museum_poi = self.pois[0]  # fallback
        
        # Apply scoring for atomic predicate
        _, atom_scores, _ = self.handler.apply_semantic_predicate(
            [museum_poi], atom_pred, []
        )
        atom_score = atom_scores[id(museum_poi)]
        
        # Clear cache and apply scoring for NOT predicate
        self.handler._score_cache.clear()
        _, not_scores, _ = self.handler.apply_semantic_predicate(
            [museum_poi], not_pred, []
        )
        not_score = not_scores[id(museum_poi)]
        
        print(f"POI: {museum_poi.find('name').text}")
        print(f"Atom score (museum): {atom_score:.4f}")
        print(f"NOT score: {not_score:.4f}")
        print(f"Expected NOT score: {1 - atom_score:.4f}")
        
        # NOT score should be approximately 1 - atom_score
        # (accounting for EPSILON clamping)
        expected = 1 - atom_score
        tolerance = 0.01
        assert abs(not_score - expected) < tolerance, \
            f"NOT score {not_score} should be ~{expected}"
        
        print("✅ PASSED: NOT correctly inverts scores")
        return atom_score, not_score
    
    def test_and_min_scoring(self):
        """Test: AND operator uses min() instead of product."""
        print(f"\n{'='*60}")
        print(f"Test: AND Uses Min Scoring")
        
        # Create two atomic predicates with different scores
        atom1 = CompoundPredicate(
            operator="ATOM",
            conditions=[AtomicPredicate(field="content", value="art")]
        )
        atom2 = CompoundPredicate(
            operator="ATOM",
            conditions=[AtomicPredicate(field="content", value="museum")]
        )
        
        # Create AND predicate
        and_pred = CompoundPredicate(
            operator="AND",
            conditions=[atom1, atom2]
        )
        
        # Use Art Gallery of Ontario
        test_poi = None
        for poi in self.pois:
            name_elem = poi.find("name")
            if name_elem is not None and "Art Gallery" in name_elem.text:
                test_poi = poi
                break
        
        if test_poi is None:
            test_poi = self.pois[0]
        
        # Get individual scores
        self.handler._score_cache.clear()
        _, scores1, _ = self.handler.apply_semantic_predicate([test_poi], atom1, [])
        score1 = scores1[id(test_poi)]
        
        self.handler._score_cache.clear()
        _, scores2, _ = self.handler.apply_semantic_predicate([test_poi], atom2, [])
        score2 = scores2[id(test_poi)]
        
        # Get AND score
        self.handler._score_cache.clear()
        _, and_scores, _ = self.handler.apply_semantic_predicate([test_poi], and_pred, [])
        and_score = and_scores[id(test_poi)]
        
        expected_min = min(score1, score2)
        expected_product = score1 * score2
        
        print(f"POI: {test_poi.find('name').text}")
        print(f"Score for 'art': {score1:.4f}")
        print(f"Score for 'museum': {score2:.4f}")
        print(f"AND score: {and_score:.4f}")
        print(f"Expected min: {expected_min:.4f}")
        print(f"Old product would be: {expected_product:.4f}")
        
        # AND should use min, not product
        tolerance = 0.01
        assert abs(and_score - expected_min) < tolerance, \
            f"AND score {and_score} should be min({score1}, {score2}) = {expected_min}"
        
        print("✅ PASSED: AND uses min() scoring")
        return score1, score2, and_score
    
    def test_and_not_combined_scoring(self):
        """Test: AND combined with NOT scores correctly."""
        print(f"\n{'='*60}")
        print(f"Test: AND with NOT Combined Scoring")
        
        # atom(content =~ "museum") AND not(atom(content =~ "expensive"))
        atom_museum = CompoundPredicate(
            operator="ATOM",
            conditions=[AtomicPredicate(field="content", value="museum")]
        )
        atom_expensive = CompoundPredicate(
            operator="ATOM",
            conditions=[AtomicPredicate(field="content", value="expensive")]
        )
        not_expensive = CompoundPredicate(
            operator="NOT",
            conditions=[atom_expensive]
        )
        and_pred = CompoundPredicate(
            operator="AND",
            conditions=[atom_museum, not_expensive]
        )
        
        # Test on Royal Ontario Museum
        test_poi = None
        for poi in self.pois:
            name_elem = poi.find("name")
            if name_elem is not None and "Royal Ontario Museum" in name_elem.text:
                test_poi = poi
                break
        
        if test_poi is None:
            test_poi = self.pois[0]
        
        # Get individual scores
        self.handler._score_cache.clear()
        _, museum_scores, _ = self.handler.apply_semantic_predicate([test_poi], atom_museum, [])
        museum_score = museum_scores[id(test_poi)]
        
        self.handler._score_cache.clear()
        _, expensive_scores, _ = self.handler.apply_semantic_predicate([test_poi], atom_expensive, [])
        expensive_score = expensive_scores[id(test_poi)]
        not_expensive_score = 1 - expensive_score
        
        # Get combined AND score
        self.handler._score_cache.clear()
        _, and_scores, _ = self.handler.apply_semantic_predicate([test_poi], and_pred, [])
        combined_score = and_scores[id(test_poi)]
        
        expected = min(museum_score, not_expensive_score)
        
        print(f"POI: {test_poi.find('name').text}")
        print(f"Museum score: {museum_score:.4f}")
        print(f"Expensive score: {expensive_score:.4f}")
        print(f"NOT expensive score: {not_expensive_score:.4f}")
        print(f"Combined AND score: {combined_score:.4f}")
        print(f"Expected min: {expected:.4f}")
        
        tolerance = 0.02
        assert abs(combined_score - expected) < tolerance, \
            f"Combined score {combined_score} should be ~{expected}"
        
        print("✅ PASSED: AND with NOT combined scoring works correctly")
        return combined_score


class TestEndToEndNotAnd:
    """End-to-end tests for NOT and AND operators."""
    
    def __init__(self):
        from dense_xpath import DenseXPathExecutor
        
        self.executor = DenseXPathExecutor(
            scoring_method="cosine",
            top_k=10,
            score_threshold=0.0,
            data_name="travel_memory_3day"
        )
    
    def test_execute_not_query(self):
        """Test: Execute query with NOT operator."""
        print(f"\n{'='*60}")
        print(f"Test: Execute NOT Query End-to-End")
        
        # POIs that are NOT expensive
        # Note: Query must traverse the versioned structure: Root > Itinerary_Version > Itinerary > Day > POI
        query = "/Root/Itinerary_Version/Itinerary/Day/POI[not(atom(content =~ \"expensive\"))]"
        
        print(f"Query: {query}")
        
        result = self.executor.execute(query)
        
        print(f"Found {len(result.matched_nodes)} nodes")
        for node in result.matched_nodes[:3]:
            print(f"  - {node.tree_path} (score: {node.score:.4f})")
        
        assert len(result.matched_nodes) > 0, "Should find some POIs"
        print("✅ PASSED: NOT query executes successfully")
        return result
    
    def test_execute_and_query(self):
        """Test: Execute query with AND operator."""
        print(f"\n{'='*60}")
        print(f"Test: Execute AND Query End-to-End")
        
        # POIs that are art AND gallery
        query = "/Root/Itinerary_Version/Itinerary/Day/POI[atom(content =~ \"art\") AND atom(content =~ \"gallery\")]"
        
        print(f"Query: {query}")
        
        result = self.executor.execute(query)
        
        print(f"Found {len(result.matched_nodes)} nodes")
        for node in result.matched_nodes[:3]:
            print(f"  - {node.tree_path} (score: {node.score:.4f})")
        
        assert len(result.matched_nodes) > 0, "Should find some POIs"
        print("✅ PASSED: AND query executes successfully")
        return result
    
    def test_execute_and_not_combined(self):
        """Test: Execute query with AND and NOT combined."""
        print(f"\n{'='*60}")
        print(f"Test: Execute AND + NOT Combined Query")
        
        # Museums that are NOT expensive
        query = "/Root/Itinerary_Version/Itinerary/Day/POI[atom(content =~ \"museum\") AND not(atom(content =~ \"expensive\"))]"
        
        print(f"Query: {query}")
        
        result = self.executor.execute(query)
        
        print(f"Found {len(result.matched_nodes)} nodes")
        for node in result.matched_nodes[:3]:
            print(f"  - {node.tree_path} (score: {node.score:.4f})")
        
        assert len(result.matched_nodes) > 0, "Should find some POIs"
        print("✅ PASSED: AND + NOT combined query executes successfully")
        return result
    
    def test_not_with_aggregation(self):
        """Test: NOT with aggregation operator."""
        print(f"\n{'='*60}")
        print(f"Test: NOT with Aggregation Operator")
        
        # Days that do NOT have upscale restaurants
        query = "/Root/Itinerary_Version/Itinerary/Day[not(agg_exists(Restaurant[atom(content =~ \"upscale\")]))]"
        
        print(f"Query: {query}")
        
        result = self.executor.execute(query)
        
        print(f"Found {len(result.matched_nodes)} Days")
        for node in result.matched_nodes:
            print(f"  - {node.tree_path} (score: {node.score:.4f})")
        
        print("✅ PASSED: NOT with aggregation executes successfully")
        return result


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("Running NOT and AND Operator Tests")
    print("="*60)
    
    # Parsing tests
    print("\n" + "-"*60)
    print("PARSING TESTS")
    print("-"*60)
    parse_tests = TestNotAndParsing()
    parse_tests.test_parse_not_operator()
    parse_tests.test_parse_nested_not()
    parse_tests.test_parse_and_operator()
    parse_tests.test_parse_combined_and_not()
    parse_tests.test_get_all_atomic_values_with_not()
    
    # Scoring tests
    print("\n" + "-"*60)
    print("SCORING TESTS")
    print("-"*60)
    score_tests = TestNotAndScoring()
    score_tests.test_not_score_inversion()
    score_tests.test_and_min_scoring()
    score_tests.test_and_not_combined_scoring()
    
    # End-to-end tests
    print("\n" + "-"*60)
    print("END-TO-END TESTS")
    print("-"*60)
    e2e_tests = TestEndToEndNotAnd()
    e2e_tests.test_execute_not_query()
    e2e_tests.test_execute_and_query()
    e2e_tests.test_execute_and_not_combined()
    e2e_tests.test_not_with_aggregation()
    
    print("\n" + "="*60)
    print("All NOT and AND operator tests passed!")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
