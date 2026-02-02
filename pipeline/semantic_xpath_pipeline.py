"""
Semantic XPath Pipeline - Full CRUD Pipeline for tree operations.

Provides an interactive interface for executing CRUD operations on tree data
with full query display, trace saving, and result formatting.

Uses in-tree versioning - all operations create new Version nodes within the tree,
enabling full history tracking and version-based queries.

Supports:
- Read: Find and retrieve nodes using semantic XPath
- Create: Add new nodes to the tree (creates new version)
- Update: Modify existing nodes (creates new version)
- Delete: Remove nodes from the tree (creates new version)
"""

import json
import yaml
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from crud import CRUDExecutor
from dense_xpath.trace_writer import TraceWriter


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class SemanticXPathPipeline:
    """
    Full CRUD Pipeline for semantic XPath operations with in-tree versioning.
    
    Converts natural language requests to CRUD operations:
    - Classifies intent and generates XPath in a single LLM call
    - Executes operations with LLM reasoning
    - Creates new versions within the tree for modifications
    - Provides full query display (e.g., "Delete(/Itinerary/Version[-1]/Day/POI[...])")
    
    All modifications create new Version nodes in the tree, enabling:
    - Full history tracking
    - Version-based queries ("show me the second version")
    - Semantic version search ("what did I change about the museum?")
    """
    
    def __init__(
        self, 
        top_k: int = None, 
        score_threshold: float = None,
        scoring_method: str = None,
        tree_path: Path = None,
        traces_path: Path = None
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
            tree_path: Optional path to the XML tree. Overrides config default.
            traces_path: Optional path for trace files. If None, uses default traces folder.
        """
        self.executor = CRUDExecutor(
            scoring_method=scoring_method,
            top_k=top_k,
            score_threshold=score_threshold,
            tree_path=tree_path,
            traces_path=traces_path
        )
        self.trace_writer = TraceWriter(
            log_path=traces_path / "log" if traces_path else None,
            traces_path=traces_path / "reasoning_traces" if traces_path else None
        )
        
        # Session statistics
        self.session_stats = {
            "operations": 0,
            "reads": 0,
            "creates": 0,
            "updates": 0,
            "deletes": 0,
            "successes": 0,
            "failures": 0,
            "versions_created": 0
        }
    
    def process_request(self, user_request: str) -> Dict[str, Any]:
        """
        Process a user request as a CRUD operation.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            Dict with operation results, traces, and timing info
        """
        start_time = time.perf_counter()
        
        # Execute the CRUD operation (includes step timing)
        result = self.executor.execute(user_request)
        
        # Calculate total pipeline timing
        total_time_ms = (time.perf_counter() - start_time) * 1000
        result["total_time_ms"] = total_time_ms
        
        # Preserve step timing from executor, add total
        if "timing" not in result:
            result["timing"] = {}
        result["timing"]["pipeline_total_ms"] = total_time_ms
        
        # Save traces
        timestamp = result.get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        self.trace_writer.save_crud_traces(timestamp, result)
        
        # Update session stats
        self._update_stats(result)
        
        return result
    
    def _update_stats(self, result: Dict[str, Any]):
        """Update session statistics."""
        self.session_stats["operations"] += 1
        
        operation = result.get("operation", "").upper()
        if operation == "READ":
            self.session_stats["reads"] += 1
        elif operation == "CREATE":
            self.session_stats["creates"] += 1
        elif operation == "UPDATE":
            self.session_stats["updates"] += 1
        elif operation == "DELETE":
            self.session_stats["deletes"] += 1
        
        if result.get("success"):
            self.session_stats["successes"] += 1
            # Track version creation for non-READ operations
            if operation in ("CREATE", "UPDATE", "DELETE") and result.get("tree_version"):
                self.session_stats["versions_created"] += 1
        else:
            self.session_stats["failures"] += 1
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """Format the result for display."""
        lines = []
        
        operation = result.get("operation", "UNKNOWN")
        success = result.get("success", False)
        status_icon = "✅" if success else "❌"
        
        lines.append(f"\n{status_icon} {operation} Operation {'Succeeded' if success else 'Failed'}")
        lines.append("=" * 60)
        
        # Version info
        version_used = result.get("version_used")
        if version_used:
            lines.append(f"📌 Operating on Version: {version_used}")
        
        # Timing
        if "total_time_ms" in result:
            lines.append(f"⏱️  Time: {result['total_time_ms']:.1f}ms")
        
        # Operation-specific formatting
        if operation == "READ":
            lines.extend(self._format_read_result(result))
        elif operation == "DELETE":
            lines.extend(self._format_delete_result(result))
        elif operation == "UPDATE":
            lines.extend(self._format_update_result(result))
        elif operation == "CREATE":
            lines.extend(self._format_create_result(result))
        
        # Tree version info (for modifications)
        tree_version = result.get("tree_version")
        if tree_version:
            lines.append(f"\n📁 Tree saved: {tree_version.get('path', 'N/A')}")
            lines.append(f"   Total versions: {tree_version.get('version', 'N/A')}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def _format_read_result(self, result: Dict[str, Any]) -> list:
        """Format READ operation results."""
        lines = []
        
        candidates = result.get("candidates_count", 0)
        selected = result.get("selected_count", 0)
        lines.append(f"\n📊 Results: {selected} selected from {candidates} candidates")
        
        selected_nodes = result.get("selected_nodes", [])
        if selected_nodes:
            lines.append("\n📋 Selected Nodes:")
            lines.append("-" * 50)
            
            for i, node in enumerate(selected_nodes, 1):
                node_type = node.get("type", "?")
                tree_path = node.get("tree_path", "")
                
                # For container nodes (Day, Version), use tree_path for display
                if tree_path:
                    display_name = tree_path.split(" > ")[-1] if " > " in tree_path else tree_path
                elif node.get("attributes", {}).get("index"):
                    display_name = f"{node_type} {node['attributes']['index']}"
                else:
                    display_name = node.get("name", "Unknown")
                
                lines.append(f"\n[{i}] {display_name}")
                if tree_path:
                    lines.append(f"    📍 Path: {tree_path}")
                
                if node.get("description"):
                    desc = node["description"]
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    lines.append(f"    📝 {desc}")
                
                if node.get("time_block"):
                    lines.append(f"    🕐 {node['time_block']}")
                
                if node.get("expected_cost"):
                    lines.append(f"    💰 {node['expected_cost']}")
                
                if node.get("highlights"):
                    highlights = node["highlights"]
                    if isinstance(highlights, list):
                        lines.append(f"    ✨ {', '.join(highlights)}")
                
                # For container nodes, display children subtree
                children = node.get("children", [])
                if children:
                    lines.append(f"    📦 Children ({len(children)}):")
                    for child in children:
                        child_type = child.get("type", "?")
                        child_name = child.get("name", "Unknown")
                        child_desc = child.get("description", "")
                        lines.append(f"        - {child_type}: {child_name}")
                        if child_desc:
                            short_desc = child_desc[:60] + "..." if len(child_desc) > 60 else child_desc
                            lines.append(f"          {short_desc}")
        else:
            lines.append("\n⚠️  No nodes matched the query")
        
        return lines
    
    def _format_delete_result(self, result: Dict[str, Any]) -> list:
        """Format DELETE operation results."""
        lines = []
        
        deleted_count = result.get("deleted_count", 0)
        deleted_paths = result.get("deleted_paths", [])
        
        lines.append(f"\n🗑️  Deleted: {deleted_count} node(s)")
        
        if deleted_paths:
            lines.append("\nDeleted Paths:")
            for path in deleted_paths:
                lines.append(f"  ❌ {path}")
        
        return lines
    
    def _format_update_result(self, result: Dict[str, Any]) -> list:
        """Format UPDATE operation results."""
        lines = []
        
        updated_count = result.get("updated_count", 0)
        updated_paths = result.get("updated_paths", [])
        
        lines.append(f"\n✏️  Updated: {updated_count} node(s)")
        
        update_results = result.get("update_results", [])
        for update in update_results:
            path = update.get("path", "Unknown")
            success = update.get("success", False)
            icon = "✅" if success else "❌"
            lines.append(f"\n{icon} {path}")
            
            changes_data = update.get("changes", {})
            changes = changes_data.get("changes", {})
            if changes:
                for field, change in changes.items():
                    old_val = change.get("from", "?")
                    new_val = change.get("to", "?")
                    lines.append(f"    {field}: {old_val} → {new_val}")
        
        return lines
    
    def _format_create_result(self, result: Dict[str, Any]) -> list:
        """Format CREATE operation results."""
        lines = []
        
        created_path = result.get("created_path")
        
        if created_path:
            lines.append(f"\n➕ Created: {created_path}")
            
            # Show insertion point
            insertion = result.get("insertion_point", {})
            if insertion:
                lines.append(f"\n📍 Insertion Point:")
                lines.append(f"    Parent: {insertion.get('parent_path', 'Unknown')}")
                lines.append(f"    Position: {insertion.get('position', -1)}")
            
            # Show generated content summary
            content = result.get("content_result", {})
            if content.get("success"):
                fields = content.get("fields", {})
                lines.append(f"\n📄 Generated Content:")
                for key, value in fields.items():
                    if isinstance(value, list):
                        lines.append(f"    {key}: {', '.join(str(v) for v in value[:3])}...")
                    elif len(str(value)) > 50:
                        lines.append(f"    {key}: {str(value)[:50]}...")
                    else:
                        lines.append(f"    {key}: {value}")
        else:
            lines.append("\n⚠️  Creation failed")
            if result.get("message"):
                lines.append(f"    Reason: {result['message']}")
        
        return lines
    
    def run_interactive(self):
        """
        Run an interactive loop for CRUD operations.
        
        Commands:
        - Type a natural language query to execute a CRUD operation
        - Type 'stats' to see session statistics
        - Type 'history' to see version history
        - Type 'reload' to reload the tree from the original file
        - Type 'exit' or 'quit' to stop
        """
        print("=" * 60)
        print("Semantic XPath Pipeline - CRUD Operations")
        print("=" * 60)
        print("In-tree versioning enabled:")
        print("  - All modifications create new versions")
        print("  - Query specific versions with Version[N] or Version[-1]")
        print("  - Search versions: 'what changed about museum?'")
        print("-" * 60)
        print("Commands:")
        print("  - Natural language query for CRUD operations")
        print("  - 'stats' - Session statistics")
        print("  - 'history' - View version history")
        print("  - 'reload' - Reload tree from file")
        print("  - 'exit' or 'quit' - Exit")
        print("=" * 60)
        print()
        
        session_start = time.perf_counter()
        
        while True:
            try:
                user_input = input("🔄 Query: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit", "q"):
                    self._print_session_summary(session_start)
                    print("Goodbye!")
                    break
                
                if user_input.lower() == "stats":
                    self._print_stats()
                    continue
                
                if user_input.lower() == "history":
                    self._print_version_history()
                    continue
                
                if user_input.lower() == "reload":
                    self.executor.reload_tree()
                    print("✅ Tree reloaded from original file")
                    continue
                
                # Process the query
                result = self.process_request(user_input)
                print(self.format_result(result))
                print()
                
            except KeyboardInterrupt:
                self._print_session_summary(session_start)
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
    
    def _print_stats(self):
        """Print session statistics."""
        print("\n📊 Session Statistics:")
        print("-" * 40)
        print(f"  Total Operations: {self.session_stats['operations']}")
        print(f"  - Reads:   {self.session_stats['reads']}")
        print(f"  - Creates: {self.session_stats['creates']}")
        print(f"  - Updates: {self.session_stats['updates']}")
        print(f"  - Deletes: {self.session_stats['deletes']}")
        print(f"  Successes: {self.session_stats['successes']}")
        print(f"  Failures:  {self.session_stats['failures']}")
        print(f"  Versions Created: {self.session_stats['versions_created']}")
        print()
    
    def _print_version_history(self):
        """Print version history from the tree."""
        print("\n📜 Version History:")
        print("-" * 50)
        
        history = self.executor.version_manager.get_version_history(self.executor.tree)
        
        if not history:
            print("  No versions found")
            return
        
        for version in history:
            print(f"\n  Version {version['number']}:")
            if version['patch_info']:
                print(f"    📝 Changes: {version['patch_info']}")
            if version['conversation_history']:
                print(f"    💬 Request: {version['conversation_history']}")
            print(f"    📦 Content: {version['content_count']} items")
        print()
    
    def _print_session_summary(self, session_start: float):
        """Print session summary on exit."""
        session_time = (time.perf_counter() - session_start) * 1000
        
        print("\n" + "=" * 60)
        print("📊 Session Summary:")
        print("-" * 40)
        print(f"  Duration: {session_time/1000:.1f}s")
        print(f"  Operations: {self.session_stats['operations']}")
        print(f"  - Reads:   {self.session_stats['reads']}")
        print(f"  - Creates: {self.session_stats['creates']}")
        print(f"  - Updates: {self.session_stats['updates']}")
        print(f"  - Deletes: {self.session_stats['deletes']}")
        print(f"  Versions Created: {self.session_stats['versions_created']}")
        
        if self.session_stats['operations'] > 0:
            success_rate = self.session_stats['successes'] / self.session_stats['operations'] * 100
            print(f"  Success Rate: {success_rate:.1f}%")
        
        print("=" * 60)


def main():
    """Main entry point for running the pipeline interactively."""
    import argparse
    
    config = load_config()
    executor_config = config.get("xpath_executor", {})
    default_top_k = executor_config.get("top_k", 5)
    default_threshold = executor_config.get("score_threshold", 0.5)
    default_method = executor_config.get("scoring_method", "entailment")
    
    parser = argparse.ArgumentParser(description="Semantic XPath Pipeline - CRUD Operations")
    parser.add_argument("--top-k", type=int, default=None, 
                        help=f"Top K nodes for semantic matching (default from config: {default_top_k})")
    parser.add_argument("--threshold", type=float, default=None, 
                        help=f"Score threshold for relevance (default from config: {default_threshold})")
    parser.add_argument("--scoring", "-s", type=str, default=None,
                        choices=["llm", "entailment", "cosine"],
                        help=f"Scoring method: llm, entailment, or cosine (default from config: {default_method})")
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="Single query to execute (non-interactive)")
    
    args = parser.parse_args()
    
    pipeline = SemanticXPathPipeline(
        top_k=args.top_k, 
        score_threshold=args.threshold,
        scoring_method=args.scoring
    )
    
    if args.query:
        # Single query mode
        result = pipeline.process_request(args.query)
        print(pipeline.format_result(result))
    else:
        # Interactive mode
        pipeline.run_interactive()


if __name__ == "__main__":
    main()
