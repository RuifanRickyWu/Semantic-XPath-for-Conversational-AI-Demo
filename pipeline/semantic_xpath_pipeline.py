"""
Semantic XPath Pipeline - Interactive pipeline for generating and executing XPath queries.
"""

import json
import yaml
import time
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from xpath_query_generation import XPathQueryGenerator
from dense_xpath import DenseXPathExecutor


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class SemanticXPathPipeline:
    """
    Pipeline for semantic XPath query generation and execution.
    
    Converts natural language requests to XPath queries and executes them
    against the tree memory with semantic scoring.
    """
    
    def __init__(
        self, 
        top_k: int = None, 
        score_threshold: float = None,
        scoring_method: str = None
    ):
        """
        Initialize the pipeline.
        
        Args:
            top_k: Number of top-scoring nodes to consider for semantic predicates.
                   If None, uses value from config.yaml.
            score_threshold: Minimum score for a node to be considered relevant.
                   If None, uses value from config.yaml.
            scoring_method: Scoring method ("llm" or "entailment").
                   If None, uses value from config.yaml.
        """
        self.query_generator = XPathQueryGenerator()
        # Let executor load from config if values not provided
        self.executor = DenseXPathExecutor(
            top_k=top_k, 
            score_threshold=score_threshold,
            scoring_method=scoring_method
        )
    
    def process_request(self, user_request: str) -> dict:
        """
        Process a user request: generate query and execute it.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            dict with 'request', 'query', 'matched_nodes', 'execution_log', timing info
        """
        total_start = time.perf_counter()
        
        # Generate query
        query_gen_start = time.perf_counter()
        query = self.query_generator.generate(user_request)
        query_gen_time_ms = (time.perf_counter() - query_gen_start) * 1000
        
        # Execute query
        execution_result = self.executor.execute(query)
        
        total_time_ms = (time.perf_counter() - total_start) * 1000
        
        return {
            "request": user_request,
            "query": query,
            "matched_nodes": execution_result.matched_nodes,
            "execution_log": execution_result.execution_log,
            "scoring_traces": execution_result.scoring_traces,
            "timing": {
                "query_generation_ms": query_gen_time_ms,
                "query_execution_ms": execution_result.execution_time_ms,
                "total_ms": total_time_ms
            }
        }
    
    def format_result(self, result: dict) -> str:
        """Format the result for display (sorted by score, highest first)."""
        lines = []
        lines.append(f"\nQuery: {result['query']}")
        
        # Display timing information if available
        if "timing" in result:
            timing = result["timing"]
            lines.append(f"⏱️  Timing: query_gen={timing['query_generation_ms']:.1f}ms, "
                        f"execution={timing['query_execution_ms']:.1f}ms, "
                        f"total={timing['total_ms']:.1f}ms")
        
        lines.append(f"\nMatched {len(result['matched_nodes'])} node(s) (sorted by score):")
        lines.append("=" * 60)
        
        for i, matched in enumerate(result['matched_nodes']):
            lines.append(f"\n[Result {i + 1}] ⭐ Score: {matched.score:.3f}")
            lines.append(f"📍 Tree Path: {matched.tree_path}")
            lines.append("-" * 50)
            
            node = matched.node_data
            node_type = node.get("type", "?")
            
            # Display node info
            if node_type == "Day":
                attrs = node.get("attributes", {})
                day_idx = attrs.get("index", "?")
                lines.append(f"📅 Day {day_idx}")
            else:
                # Try multiple common name fields (generic across schemas)
                name = node.get("name") or node.get("title") or node.get("label") or "Unknown"
                lines.append(f"🏷️  {node_type}: {name}")
                if node.get("description"):
                    lines.append(f"📝 {node['description']}")
                if node.get("time_block"):
                    lines.append(f"🕐 {node['time_block']}")
                if node.get("expected_cost"):
                    lines.append(f"💰 {node['expected_cost']}")
                if node.get("highlights"):
                    lines.append(f"✨ {', '.join(node['highlights'])}")
            
            # Display children (subtree)
            if matched.children:
                lines.append(f"\n📂 Children ({len(matched.children)}):")
                for j, child in enumerate(matched.children):
                    child_type = child.get("type", "?")
                    child_name = child.get("name") or child.get("title") or child.get("label") or "Unknown"
                    child_time = child.get("time_block", "")
                    
                    prefix = "├──" if j < len(matched.children) - 1 else "└──"
                    type_icon = "📍" if child_type == "POI" else "🍽️"
                    
                    lines.append(f"   {prefix} {type_icon} [{child_type}] {child_name}")
                    if child_time:
                        lines.append(f"   │      🕐 {child_time}")
                    if child.get("description"):
                        desc = child['description'][:80]
                        lines.append(f"   │      📝 {desc}{'...' if len(child.get('description', '')) > 80 else ''}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    def run_interactive(self):
        """
        Run an interactive loop where user can continuously send requests.
        Each request generates a query and executes it.
        
        Type 'exit' or 'quit' to stop.
        Type 'stats' to see session statistics.
        """
        print("=" * 60)
        print("Semantic XPath Pipeline - Interactive Mode")
        print("=" * 60)
        print(f"Config: scoring_method={self.executor.scoring_method}, top_k={self.executor.top_k}, score_threshold={self.executor.score_threshold}")
        print("Enter your request to generate and execute an XPath query.")
        print("Type 'exit' to quit, 'stats' for session timing.\n")
        
        # Session statistics
        session_start = time.perf_counter()
        query_count = 0
        total_query_time_ms = 0.0
        
        while True:
            try:
                user_input = input("Request: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit", "q"):
                    session_time = (time.perf_counter() - session_start) * 1000
                    print(f"\n📊 Session Summary:")
                    print(f"   Queries: {query_count}")
                    print(f"   Total query time: {total_query_time_ms:.1f}ms")
                    print(f"   Session duration: {session_time:.1f}ms")
                    if query_count > 0:
                        print(f"   Average per query: {total_query_time_ms / query_count:.1f}ms")
                    print("Goodbye!")
                    break
                
                if user_input.lower() == "stats":
                    session_time = (time.perf_counter() - session_start) * 1000
                    print(f"\n📊 Session Statistics:")
                    print(f"   Queries executed: {query_count}")
                    print(f"   Total query time: {total_query_time_ms:.1f}ms")
                    print(f"   Session duration: {session_time:.1f}ms")
                    if query_count > 0:
                        print(f"   Average per query: {total_query_time_ms / query_count:.1f}ms")
                    print()
                    continue
                
                result = self.process_request(user_input)
                print(self.format_result(result))
                print()
                
                # Update session stats
                query_count += 1
                if "timing" in result:
                    total_query_time_ms += result["timing"]["total_ms"]
                
            except KeyboardInterrupt:
                session_time = (time.perf_counter() - session_start) * 1000
                print(f"\n\n📊 Session Summary:")
                print(f"   Queries: {query_count}")
                print(f"   Total query time: {total_query_time_ms:.1f}ms")
                print(f"   Session duration: {session_time:.1f}ms")
                print("Goodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point for running the pipeline interactively."""
    import argparse
    
    config = load_config()
    executor_config = config.get("xpath_executor", {})
    default_top_k = executor_config.get("top_k", 5)
    default_threshold = executor_config.get("score_threshold", 0.5)
    default_method = executor_config.get("scoring_method", "llm")
    
    parser = argparse.ArgumentParser(description="Semantic XPath Pipeline")
    parser.add_argument("--top-k", type=int, default=None, 
                        help=f"Top K nodes for semantic matching (default from config: {default_top_k})")
    parser.add_argument("--threshold", type=float, default=None, 
                        help=f"Score threshold for relevance (default from config: {default_threshold})")
    parser.add_argument("--scoring", "-s", type=str, default=None,
                        choices=["llm", "entailment", "cosine"],
                        help=f"Scoring method: llm, entailment, or cosine (default from config: {default_method})")
    
    args = parser.parse_args()
    
    pipeline = SemanticXPathPipeline(
        top_k=args.top_k, 
        score_threshold=args.threshold,
        scoring_method=args.scoring
    )
    pipeline.run_interactive()


if __name__ == "__main__":
    main()
