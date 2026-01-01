"""
Semantic XPath Pipeline - Interactive pipeline for generating and executing XPath queries.
"""

import json
import yaml
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
            dict with 'request', 'query', 'matched_nodes', 'execution_log'
        """
        # Generate query
        query = self.query_generator.generate(user_request)
        
        # Execute query
        execution_result = self.executor.execute(query)
        
        return {
            "request": user_request,
            "query": query,
            "matched_nodes": execution_result.matched_nodes,
            "execution_log": execution_result.execution_log,
            "scoring_traces": execution_result.scoring_traces
        }
    
    def format_result(self, result: dict) -> str:
        """Format the result for display (sorted by score, highest first)."""
        lines = []
        lines.append(f"\nQuery: {result['query']}")
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
                name = node.get("name", "Unknown")
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
                    child_name = child.get("name", "Unknown")
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
        """
        print("=" * 60)
        print("Semantic XPath Pipeline - Interactive Mode")
        print("=" * 60)
        print(f"Config: scoring_method={self.executor.scoring_method}, top_k={self.executor.top_k}, score_threshold={self.executor.score_threshold}")
        print("Enter your request to generate and execute an XPath query.")
        print("Type 'exit' to quit.\n")
        
        while True:
            try:
                user_input = input("Request: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                
                result = self.process_request(user_input)
                print(self.format_result(result))
                print()
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
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
                        choices=["llm", "entailment"],
                        help=f"Scoring method: llm or entailment (default from config: {default_method})")
    
    args = parser.parse_args()
    
    pipeline = SemanticXPathPipeline(
        top_k=args.top_k, 
        score_threshold=args.threshold,
        scoring_method=args.scoring
    )
    pipeline.run_interactive()


if __name__ == "__main__":
    main()
