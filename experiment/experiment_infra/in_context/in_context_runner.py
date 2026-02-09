"""
In-Context Experiment Runner - Execute in-context evaluation experiments.

Usage:
    python experiment/experiment_infra/in_context/in_context_runner.py --config experiment.yaml
    # or
    python -m experiment.experiment_infra.in_context.in_context_runner --config experiment.yaml

Output Structure:
    experiment/experiment_result/in_context/{experiment_name}/
    ├── Experiment_Log.json
    ├── Cost_Summary.json           # Token costs and latency tracking
    ├── experiment_config.yaml
    └── Session_1/
        ├── tree.xml
        └── session_result.json
"""

import json
import yaml
import shutil
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import xml.etree.ElementTree as ET
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Handle both direct execution and module import
try:
    from .in_context_pipeline import InContextPipeline, InContextResult
    from .result_logger import InContextResultLogger, SessionResult, QueryResult
except ImportError:
    from in_context_pipeline import InContextPipeline, InContextResult
    from result_logger import InContextResultLogger, SessionResult, QueryResult
from pipeline_execution.semantic_xpath_util import load_schema


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Token pricing (per token rates)
PRICING = {
    "gpt-4o": {"prompt": 0.0025 / 1000, "completion": 0.01 / 1000},
    "gpt-4o-mini": {"prompt": 0.00015 / 1000, "completion": 0.0006 / 1000},
    "gpt-5": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    "gpt-5-mini": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    "o1": {"prompt": 0.015 / 1000, "completion": 0.06 / 1000},
    "o3": {"prompt": 0.015 / 1000, "completion": 0.06 / 1000},
}


class InContextRunner:
    """
    Runs in-context evaluation experiments across multiple sessions.
    
    For each session:
    - Single-turn: Copy fresh tree, process single query, log result
    - Multi-turn: Copy tree once, process queries sequentially with
                 accumulated versions, LLM sees full tree each turn
    
    The LLM autonomously decides which version to operate on based
    on the user's query.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the experiment runner.
        
        Args:
            config_path: Path to experiment.yaml config file
        """
        # Resolve config path relative to project root if not absolute
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = PROJECT_ROOT / config_path
        self.config_path = config_path
        self.config = self._load_config()
        
        self.experiment_name = self.config.get("name", "experiment")
        self.queries = self.config.get("queries", [])
        
        # Load model from embedded config, fallback to config.yaml
        embedded_config = self.config.get("config", {})
        if embedded_config:
            self.app_config = embedded_config
            self.model = embedded_config.get("openai", {}).get("model", "gpt-4o")
        else:
            # Fallback to config.yaml for backward compatibility
            try:
                with open(PROJECT_ROOT / "config.yaml", "r") as f:
                    self.app_config = yaml.safe_load(f)
                self.model = self.app_config.get("openai", {}).get("model", "gpt-4o")
            except (FileNotFoundError, yaml.YAMLError):
                self.app_config = {}
                self.model = "gpt-4o"  # Default fallback
        
        # Setup output directory
        self.base_output_dir = PROJECT_ROOT / "experiment" / "experiment_result" / "in_context"
        self.experiment_dir = None  # Set during run()
        
        # Pipeline instance
        self.pipeline = InContextPipeline()
        
        # Result logger
        self.result_logger = None  # Set during run()
        
        # Cost tracking
        self._cost_tracker: List[Dict[str, Any]] = []
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate experiment config."""
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Validate required fields
        if "queries" not in config or not config["queries"]:
            raise ValueError("Experiment config must have non-empty 'queries' list")
        
        # Validate query format (each should be a list)
        for i, query_list in enumerate(config["queries"]):
            if not isinstance(query_list, list):
                raise ValueError(
                    f"Query at index {i} must be a list. "
                    f"Use [\"query\"] for single-turn or [\"q1\", \"q2\", ...] for multi-turn."
                )
            if not query_list:
                raise ValueError(f"Query list at index {i} is empty")
        
        return config
    
    def _get_next_experiment_index(self) -> int:
        """Find the next available experiment index (001, 002, etc.)."""
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        
        existing_indices = []
        pattern = re.compile(r"experiment_(\d+)")
        
        for item in self.base_output_dir.iterdir():
            if item.is_dir():
                match = pattern.match(item.name)
                if match:
                    existing_indices.append(int(match.group(1)))
        
        if existing_indices:
            return max(existing_indices) + 1
        return 1
    
    def _setup_experiment_dir(self) -> Path:
        """Create experiment directory with auto-incremented index."""
        index = self._get_next_experiment_index()
        experiment_name = f"experiment_{index:03d}"
        experiment_dir = self.base_output_dir / experiment_name
        experiment_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy experiment config
        shutil.copy(self.config_path, experiment_dir / "experiment_config.yaml")
        
        return experiment_dir
    
    def _get_source_tree_path(self) -> Path:
        """Get the source tree path from schema config."""
        # Load schema to find default data file
        schema = load_schema()
        
        # Use travel_toronto_10day as default for experiments
        data_files = schema.get("data_files", {})
        default_data = "travel_toronto_10day"
        
        if default_data in data_files:
            relative_path = data_files[default_data]
        else:
            # Fallback to default_data field
            default_key = schema.get("default_data", "travel_memory_3day")
            relative_path = data_files.get(default_key, "memory/travel/travel_memory_3day.xml")
        
        return PROJECT_ROOT / "storage" / relative_path
    
    def _calculate_cost(self, token_usage: Dict[str, int]) -> float:
        """
        Calculate cost in USD for the given token usage.
        
        Args:
            token_usage: Dict with prompt_tokens and completion_tokens
            
        Returns:
            Cost in USD
        """
        # Find pricing for current model
        pricing = None
        model_lower = self.model.lower()
        for model_key in PRICING:
            if model_lower.startswith(model_key):
                pricing = PRICING[model_key]
                break
        
        if not pricing:
            # Default to gpt-4o pricing
            pricing = PRICING["gpt-4o"]
        
        prompt_cost = token_usage.get("prompt_tokens", 0) * pricing["prompt"]
        completion_cost = token_usage.get("completion_tokens", 0) * pricing["completion"]
        
        return prompt_cost + completion_cost
    
    def _get_pricing_for_model(self) -> Dict[str, Any]:
        """Get pricing info for the current model."""
        model_lower = self.model.lower()
        for model_key in PRICING:
            if model_lower.startswith(model_key):
                return {
                    "prompt_per_1k_tokens": PRICING[model_key]["prompt"] * 1000,
                    "completion_per_1k_tokens": PRICING[model_key]["completion"] * 1000
                }
        # Default
        return {
            "prompt_per_1k_tokens": PRICING["gpt-4o"]["prompt"] * 1000,
            "completion_per_1k_tokens": PRICING["gpt-4o"]["completion"] * 1000
        }
    
    def _sanitize_query_id(self, query: str, session_id: str, index: int) -> str:
        """Create a sanitized query ID from session and query text."""
        # Take first few words
        words = query.split()[:4]
        name = "_".join(words)
        
        # Remove special characters
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        name = name[:30]  # Limit length
        
        return f"{session_id}_Query_{name}" if name else f"{session_id}_Query_{index:03d}"
    
    def _build_cost_summary(self, total_experiment_time_ms: float) -> Dict[str, Any]:
        """
        Build detailed cost summary with per-task breakdown and totals.
        
        Args:
            total_experiment_time_ms: Total experiment execution time in milliseconds
            
        Returns:
            Dict with cost summary data
        """
        # Per-task breakdown
        tasks = []
        for entry in self._cost_tracker:
            token_usage = entry.get("token_usage", {})
            tasks.append({
                "query_id": entry["query_id"],
                "session": entry["session"],
                "query": entry["query"],
                "operation": entry["operation"],
                "success": entry["success"],
                "latency_ms": entry["latency_ms"],
                "tokens": {
                    "prompt": token_usage.get("prompt_tokens", 0),
                    "completion": token_usage.get("completion_tokens", 0),
                    "total": token_usage.get("total_tokens", 0)
                },
                "cost_usd": entry["cost_usd"]
            })
        
        # Calculate totals
        total_latency = sum(t["latency_ms"] for t in tasks)
        total_prompt_tokens = sum(t["tokens"]["prompt"] for t in tasks)
        total_completion_tokens = sum(t["tokens"]["completion"] for t in tasks)
        total_tokens = sum(t["tokens"]["total"] for t in tasks)
        total_cost = sum(t["cost_usd"] for t in tasks)
        
        # Calculate averages
        num_tasks = len(tasks)
        avg_latency = total_latency / num_tasks if num_tasks > 0 else 0
        avg_tokens = total_tokens / num_tasks if num_tasks > 0 else 0
        avg_cost = total_cost / num_tasks if num_tasks > 0 else 0
        
        # Build summary
        return {
            "experiment_name": self.experiment_dir.name,
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "summary": {
                "total_tasks": num_tasks,
                "total_latency_ms": round(total_latency, 2),
                "total_latency_seconds": round(total_latency / 1000, 2),
                "experiment_wall_time_ms": round(total_experiment_time_ms, 2),
                "experiment_wall_time_seconds": round(total_experiment_time_ms / 1000, 2),
                "total_tokens": {
                    "prompt": total_prompt_tokens,
                    "completion": total_completion_tokens,
                    "total": total_tokens
                },
                "total_cost_usd": round(total_cost, 4),
                "averages": {
                    "latency_ms": round(avg_latency, 2),
                    "tokens_per_task": round(avg_tokens, 2),
                    "cost_per_task_usd": round(avg_cost, 4)
                }
            },
            "tasks": tasks,
            "pricing_info": {
                "model": self.model,
                "rates": self._get_pricing_for_model()
            }
        }
    
    def _run_session(
        self,
        query_list: List[str],
        session_index: int
    ) -> SessionResult:
        """
        Run a session with one or more queries.
        
        For single-turn (1 query): Fresh tree, one LLM call
        For multi-turn (N queries): Tree accumulates versions, 
                                   LLM sees full tree each turn
        
        Args:
            query_list: List of queries for this session
            session_index: 1-based session index
            
        Returns:
            SessionResult with all query results
        """
        session_id = f"Session_{session_index}"
        session_dir = self.result_logger.create_session_dir(session_id)
        
        print(f"\n{'='*60}")
        print(f"Session {session_index}: {len(query_list)} queries")
        print(f"{'='*60}")
        
        # Copy source tree to session directory
        source_tree = self._get_source_tree_path()
        session_tree_path = session_dir / "tree.xml"
        shutil.copy2(source_tree, session_tree_path)
        
        # Load tree for this session
        tree = ET.parse(session_tree_path)
        
        session_result = SessionResult(session_id=session_id)
        
        for query_index, query in enumerate(query_list, start=1):
            print(f"\n  [{query_index}/{len(query_list)}] {query[:60]}...")
            
            # Read current tree state (with all versions for multi-turn)
            with open(session_tree_path, "r") as f:
                tree_xml = f.read()
            
            # Process query through pipeline
            # LLM sees full tree and decides which version to operate on
            result = self.pipeline.process_request(query, tree_xml)
            
            # Format and add query result
            query_result = InContextResultLogger.format_query_result(
                query_index, query, result
            )
            session_result.add_query_result(query_result)
            
            # For CUD operations, apply modifications and save tree
            if result.operation in ("CREATE", "UPDATE", "DELETE") and result.success:
                # Reload tree and apply modifications
                tree = ET.parse(session_tree_path)
                success, tree = self.pipeline.apply_modifications(result, tree, query)
                
                if success:
                    # Save modified tree (creates new version)
                    self.pipeline.save_tree(tree, session_tree_path)
                    session_result.final_tree_version = self.pipeline.version_manager.get_version_count(tree)
            
            # Calculate cost from token usage
            token_usage = result.token_usage if result.token_usage else {}
            cost_usd = self._calculate_cost(token_usage)
            
            # Track for cost summary
            query_id = self._sanitize_query_id(query, session_id, query_index)
            self._cost_tracker.append({
                "query_id": query_id,
                "session": session_id,
                "query": query,
                "operation": result.operation,
                "success": result.success,
                "latency_ms": round(result.execution_time_ms, 2),
                "token_usage": token_usage,
                "cost_usd": round(cost_usd, 5)
            })
            
            # Print status with cost info
            status = "SUCCESS" if result.success else "FAILED"
            operation = result.operation
            total_tokens = token_usage.get("total_tokens", 0)
            print(f"      {status} | {operation} | Version {result.version_used} | {result.execution_time_ms:.0f}ms | {total_tokens} tokens | ${cost_usd:.4f}")
            
            if result.related_nodes:
                for node in result.related_nodes[:3]:
                    print(f"        - {node}")
        
        # Save session result file
        self.result_logger.save_session_result(session_result, session_dir)
        
        return session_result
    
    def run(self) -> Dict[str, Any]:
        """
        Run the full experiment.
        
        Returns:
            Experiment log dict
        """
        print(f"\n{'#'*60}")
        print(f"# In-Context Experiment: {self.experiment_name}")
        print(f"# Sessions: {len(self.queries)}")
        print(f"{'#'*60}")
        
        # Setup experiment directory
        self.experiment_dir = self._setup_experiment_dir()
        self.result_logger = InContextResultLogger(self.experiment_dir)
        
        print(f"\nOutput directory: {self.experiment_dir}")
        
        start_time = time.perf_counter()
        
        # Run each session
        total_queries = 0
        for session_index, query_list in enumerate(self.queries, start=1):
            session_result = self._run_session(query_list, session_index)
            total_queries += len(session_result.queries)
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Save experiment log
        self.result_logger.save_experiment_log(
            experiment_name=self.experiment_dir.name,
            total_sessions=len(self.queries),
            total_execution_time_ms=total_time
        )
        
        # Build and save cost summary
        cost_summary = self._build_cost_summary(total_time)
        cost_summary_path = self.experiment_dir / "Cost_Summary.json"
        with open(cost_summary_path, "w", encoding="utf-8") as f:
            json.dump(cost_summary, f, indent=2, ensure_ascii=False)
        
        # Calculate totals for summary display
        total_tokens = sum(entry.get("token_usage", {}).get("total_tokens", 0) 
                          for entry in self._cost_tracker)
        total_cost = sum(entry.get("cost_usd", 0) for entry in self._cost_tracker)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Experiment Complete!")
        print(f"{'='*60}")
        print(f"  Total sessions: {len(self.queries)}")
        print(f"  Total queries: {total_queries}")
        print(f"  Total time: {total_time/1000:.1f}s")
        print(f"  Total tokens: {total_tokens:,}")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"\nResults saved to: {self.experiment_dir}")
        print(f"  - Experiment_Log.json")
        print(f"  - Cost_Summary.json")
        
        # Return experiment log
        with open(self.experiment_dir / "Experiment_Log.json", "r") as f:
            return json.load(f)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run in-context evaluation experiment"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="experiment.yaml",
        help="Path to experiment config file (default: experiment.yaml)"
    )
    
    args = parser.parse_args()
    
    runner = InContextRunner(args.config)
    experiment_log = runner.run()
    
    # Print results summary
    print("\n" + "="*60)
    print("Results Summary:")
    print("="*60)
    
    results = experiment_log.get("results", {})
    for query_id, data in list(results.items())[:5]:
        print(f"\n{query_id}:")
        print(f"  Query: {data.get('query', '')[:50]}...")
        print(f"  Operation: {data.get('operation', 'UNKNOWN')}")
        print(f"  Success: {data.get('success', False)}")
        nodes = data.get("top_k_nodes", [])
        if nodes:
            print(f"  Nodes:")
            for node in nodes[:3]:
                print(f"    - {node}")


if __name__ == "__main__":
    main()
