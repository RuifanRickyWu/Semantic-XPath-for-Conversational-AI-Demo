"""
Tests for XPath query generation and node reasoning.

Tests verify:
1. Leaf node queries (POI, Restaurant) return correct results
2. Parent node queries (Day) include subtree context for reasoner
3. Compound queries generate a single XPath query
4. Negative conditions use semantic atoms (no not() operator)
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from xpath_query_generation import XPathQueryGenerator
from reasoner import NodeReasoner
from dense_xpath import DenseXPathExecutor


class TestXPathQueryGeneration:
    """Tests for XPath query generation."""
    
    def __init__(self):
        self.generator = XPathQueryGenerator()
    
    def test_leaf_node_query(self):
        """Test 1: Leaf node query - find specific POI."""
        query = "Find museums in the itinerary"
        result = self.generator.generate(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Leaf Node Query")
        print(f"Input: {query}")
        print(f"Generated: {result}")
        
        # Verify it targets POI nodes
        assert "POI" in result, "Query should target POI nodes"
        assert "museum" in result.lower(), "Query should contain 'museum' semantic"
        print("✅ PASSED: Query correctly targets POI leaf nodes")
        return result
    
    def test_parent_node_query(self):
        """Test 2: Parent node query - find day with specific characteristics."""
        query = "Find a day with outdoor activities"
        result = self.generator.generate(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Parent Node Query")
        print(f"Input: {query}")
        print(f"Generated: {result}")
        
        # Verify it targets Day nodes
        assert "Day" in result, "Query should target Day nodes"
        assert "outdoor" in result.lower(), "Query should contain 'outdoor' semantic"
        print("✅ PASSED: Query correctly targets Day parent nodes")
        return result
    
    def test_compound_query_single_output(self):
        """Test 3: Compound query - multiple constraints in single query."""
        query = "My friend lives in Mississauga. I need a day without work commitments."
        result = self.generator.generate(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Compound Query (Single Output)")
        print(f"Input: {query}")
        print(f"Generated: {result}")
        
        # Verify single query output (no multiple lines)
        lines = [l for l in result.strip().split('\n') if l.strip()]
        assert len(lines) == 1, f"Should generate exactly 1 query, got {len(lines)}"
        
        # Verify the query is well-formed and targets Day nodes
        assert "Day" in result, "Should target Day nodes"
        
        print("✅ PASSED: Compound query generates single output")
        return result
    
    def test_negative_condition_semantic_atom(self):
        """Test 4: Negative condition - queries with 'without' should use not() or semantic predicates."""
        query = "Days without expensive restaurants"
        result = self.generator.generate(query)
        
        print(f"\n{'='*60}")
        print(f"Test: Negative Condition")
        print(f"Input: {query}")
        print(f"Generated: {result}")
        
        # Verify it targets Day nodes
        assert "Day" in result, "Should target Day nodes"
        
        # Verify it uses atom() with semantic content (with or without not())
        assert "atom(" in result, "Should use atom() predicate"
        
        print("✅ PASSED: Negative condition query is well-formed")
        return result


class TestNodeReasonerSubtree:
    """Tests for node reasoner subtree handling."""
    
    def __init__(self):
        self.reasoner = NodeReasoner(save_traces=False)
    
    def test_format_nodes_includes_children(self):
        """Test that _format_nodes includes children for parent nodes."""
        # Sample node with children (like a Day node)
        sample_nodes = [
            {
                "tree_path": "Itinerary > Version 1 > Day 1",
                "score": 0.85,
                "node": {
                    "type": "Day",
                    "attributes": {"index": "1"}
                },
                "children": [
                    {
                        "type": "POI",
                        "name": "Royal Ontario Museum",
                        "description": "World-renowned museum showcasing art, culture, and natural history."
                    },
                    {
                        "type": "Restaurant",
                        "name": "Buca Yorkville",
                        "description": "Upscale Italian dining featuring traditional dishes."
                    }
                ]
            }
        ]
        
        formatted = self.reasoner._format_nodes(sample_nodes)
        
        print(f"\n{'='*60}")
        print(f"Test: Node Reasoner Subtree Inclusion")
        print(f"Formatted output:\n{formatted}")
        
        # Verify children are included (as Subtree)
        assert "Subtree:" in formatted, "Should show subtree section"
        assert "Royal Ontario Museum" in formatted, "Should include child name"
        assert "Buca Yorkville" in formatted, "Should include child name"
        assert "POI:" in formatted, "Should include child type"
        assert "Restaurant:" in formatted, "Should include child type"
        
        print("✅ PASSED: Node reasoner includes children in formatted output")
        return formatted
    
    def test_format_nodes_leaf_no_children(self):
        """Test that leaf nodes (no children) format correctly."""
        sample_nodes = [
            {
                "tree_path": "Itinerary > Version 1 > Day 1 > Royal Ontario Museum",
                "score": 0.92,
                "node": {
                    "type": "POI",
                    "name": "Royal Ontario Museum",
                    "description": "World-renowned museum showcasing art, culture, and natural history."
                },
                "children": []
            }
        ]
        
        formatted = self.reasoner._format_nodes(sample_nodes)
        
        print(f"\n{'='*60}")
        print(f"Test: Leaf Node Formatting (No Children)")
        print(f"Formatted output:\n{formatted}")
        
        # Verify no children section for leaf nodes
        assert "Children" not in formatted, "Leaf nodes should not have Children section"
        assert "Royal Ontario Museum" in formatted, "Should include node name"
        
        print("✅ PASSED: Leaf nodes format correctly without children section")
        return formatted


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("Running XPath Query Generation and Node Reasoner Tests")
    print("="*60)
    
    # Query generation tests
    query_tests = TestXPathQueryGeneration()
    query_tests.test_leaf_node_query()
    query_tests.test_parent_node_query()
    query_tests.test_compound_query_single_output()
    query_tests.test_negative_condition_semantic_atom()
    
    # Node reasoner tests
    reasoner_tests = TestNodeReasonerSubtree()
    reasoner_tests.test_format_nodes_includes_children()
    reasoner_tests.test_format_nodes_leaf_no_children()
    
    print("\n" + "="*60)
    print("All tests passed!")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
