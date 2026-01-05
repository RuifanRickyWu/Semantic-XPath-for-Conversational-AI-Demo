"""
Test file for Semantic XPath Pipeline
Tests various query types: global, local, syntactic, semantic, single, and multiple
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import SemanticXPathPipeline


def run_tests():
    """Run all test queries and display results."""
    
    # Initialize the pipeline
    print("=" * 70)
    print("Semantic XPath Pipeline - Test Suite")
    print("=" * 70)
    
    pipeline = SemanticXPathPipeline()
    
    print(f"\nConfig: scoring_method={pipeline.executor.scoring_method}, "
          f"top_k={pipeline.executor.top_k}, "
          f"score_threshold={pipeline.executor.score_threshold}")
    print("\n")
    
    # Define test queries with their categories
    test_queries = [
        ("1. Global", "find me the 5th poi"),
        ("2. Local", "find me the first poi in each day"),
        ("3. Syntactic", "find me the first poi in first day"),
        ("4. Semantic", "find me an artistic day"),
        ("5. Single", "find me a museum"),
        ("6. Multiple", "find me all the museums"),
    ]
    
    # Run each test
    for category, query in test_queries:
        print("\n" + "=" * 70)
        print(f"📋 TEST: {category}")
        print(f"📝 Query: \"{query}\"")
        print("=" * 70)
        
        try:
            result = pipeline.process_request(query)
            print(pipeline.format_result(result))
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n")
    
    print("=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

