"""
End-to-End Tests for Semantic XPath Grammar.

Tests the full pipeline: parsing → indexing → predicate evaluation → results.
Uses travel/itinerary schema with 17 diverse queries covering all grammar features:
- Predicates: atom(), not(), AND, OR, agg_exists(), agg_prev()
- Index: local ([i], [-i], [i:j]), global ((path)[i])
- Axis: none (default), desc (descendants)
- Wildcard: "." (select all children)

Grammar Reference:
    Query Q := Step | Step / Query | (Query)[GlobalIndex]
    Step := Axis NodeType Index [Predicate]
    Axis := none | desc ::
    NodeType := Name | "." (wildcard)
    Index := none | [i] | [-i] | [i:j]
    Predicate := Predicate AND Predicate | Predicate OR Predicate | not(Predicate) | Atom | Agg
    Atom := atom(content =~ "value")
    Agg := agg_exists(Axis ChildType [Predicate]) | agg_prev(Axis ChildType [Predicate])
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dense_xpath import DenseXPathExecutor


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def executor():
    """Create executor with travel_memory_3day data."""
    return DenseXPathExecutor(
        scoring_method="cosine",
        top_k=20,
        score_threshold=0.0,
        data_name="travel_memory_3day"
    )


# =============================================================================
# End-to-End Test Queries
# =============================================================================

# 17 queries testing different grammar features
E2E_QUERIES = [
    # 1. Basic atom() - Find museums
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/POI[atom(content =~ "museum")]',
        "POI", 1, None,
        id="Q01_atom_museums"
    ),
    
    # 2. atom() with different content - Find jazz venues
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/Restaurant[atom(content =~ "jazz")]',
        "Restaurant", 1, None,
        id="Q02_atom_jazz_venues"
    ),
    
    # 3. OR predicate - Find museums OR galleries
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/POI[atom(content =~ "museum") OR atom(content =~ "gallery")]',
        "POI", 1, None,
        id="Q03_OR_museum_or_gallery"
    ),
    
    # 4. AND predicate - Find upscale Italian dining
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/Restaurant[atom(content =~ "upscale") AND atom(content =~ "Italian")]',
        "Restaurant", 1, None,
        id="Q04_AND_upscale_italian"
    ),
    
    # 5. NOT predicate - Find affordable restaurants
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/Restaurant[not(atom(content =~ "upscale"))]',
        "Restaurant", 1, None,
        id="Q05_NOT_not_expensive"
    ),
    
    # 6. agg_exists() - Find days with museums
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")])]',
        "Day", 1, None,
        id="Q06_agg_exists_days_with_museums"
    ),
    
    # 7. agg_exists() with OR - Days with jazz or live music
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day[agg_exists(Restaurant[atom(content =~ "jazz") OR atom(content =~ "live music")])]',
        "Day", 1, None,
        id="Q07_agg_exists_OR_live_music"
    ),
    
    # 8. Local index [N] - Get 2nd POI in each day
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/POI[2]',
        "POI", 1, 3,
        id="Q08_local_index_second_POI"
    ),
    
    # 9. Local negative index [-1] - Get last restaurant each day
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/Restaurant[-1]',
        "Restaurant", 1, None,
        id="Q09_local_index_negative_last_restaurant"
    ),
    
    # 10. Local range index [1:2] - First 2 POIs per day
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/POI[1:2]',
        "POI", 1, None,
        id="Q10_local_range_first_two_POIs"
    ),
    
    # 11. Global index (path)[N] - First 3 POIs overall
    pytest.param(
        '(/Root/Itinerary_Version/Itinerary/Day/POI)[1:3]',
        "POI", 1, 3,
        id="Q11_global_index_first_3_POIs"
    ),
    
    # 12. desc:: axis - All POIs under Itinerary
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/desc::POI',
        "POI", 5, None,
        id="Q12_desc_axis_all_POIs"
    ),
    
    # 13. desc:: with predicate - Find historic places
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/desc::POI[atom(content =~ "historic")]',
        "POI", 1, None,
        id="Q13_desc_axis_historic_places"
    ),
    
    # 14. Combined: predicate + local index - First museum
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day/POI[atom(content =~ "museum")][1]',
        "POI", 1, None,
        id="Q14_predicate_plus_index_first_museum"
    ),
    
    # 15. Complex combined - Days with outdoor activities, not expensive
    pytest.param(
        '(/Root/Itinerary_Version/Itinerary/Day[agg_exists(POI[atom(content =~ "outdoor") OR atom(content =~ "island")])])[1:2]',
        "Day", 1, 2,
        id="Q15_complex_combined_outdoor_days"
    ),
    
    # 16. Wildcard selector - Get all children of Day 1
    pytest.param(
        '/Root/Itinerary_Version/Itinerary/Day[1]/.',
        None, 1, None,  # expected_type=None means any type (wildcard)
        id="Q16_wildcard_all_children_day1"
    ),
    
    # 17. Wildcard with global index - First 3 items overall
    pytest.param(
        '(/Root/Itinerary_Version/Itinerary/Day/.)[1:3]',
        None, 1, 3,
        id="Q17_wildcard_global_index"
    ),
]


# =============================================================================
# Tests
# =============================================================================

@pytest.mark.parametrize("query,expected_type,min_results,max_results", E2E_QUERIES)
def test_e2e_query(executor, query, expected_type, min_results, max_results):
    """End-to-end test for a single query."""
    result = executor.execute(query)
    num_results = len(result.matched_nodes)
    
    # Print results for visibility
    type_desc = expected_type if expected_type else "item"  # Handle wildcard (None)
    print(f"\nQuery: {query}")
    print(f"Results: {num_results} {type_desc}(s) found")
    for i, node in enumerate(result.matched_nodes[:5], 1):
        name_val = node.node_data.get('name', 'N/A')
        node_type = node.node_data.get('type', 'N/A')
        print(f"  {i}. [{node_type}] {name_val} (score: {node.score:.4f})")
    
    # Assertions
    assert num_results >= min_results, f"Expected at least {min_results} results, got {num_results}"
    if max_results is not None:
        assert num_results <= max_results, f"Expected at most {max_results} results, got {num_results}"
