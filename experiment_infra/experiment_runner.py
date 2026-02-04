"""
Experiment Runner - Execute queries across sessions and generate structured logs.

Usage:
    python -m experiment_infra.experiment_runner --config experiment.yaml

Output Structure:
    semantic_xpath_result/{experiment_name}/
    ├── Experiment_Log.json
    ├── experiment_config.yaml
    ├── Session_1/
    │   ├── tree.xml
    │   └── Query_001/
    │       ├── query_master_log.json
    │       └── reasoning_traces/
    │           ├── execution_*.json
    │           └── entailment_scoring_*.json
    └── Session_2/
        └── ...
"""

import json
import yaml
import shutil
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.semantic_xpath_pipeline import SemanticXPathPipeline
from utils.log_formatter import LogFormatter


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class ExperimentRunner:
    """
    Runs experiments across multiple sessions with session-based query execution.
    
    Each session:
    - Contains a list of queries that share the same tree state
    - Uses in-tree versioning (changes patched to single tree.xml)
    - Produces query_master_log.json for each query
    
    Experiment-level output:
    - Experiment_Log.json summarizing all query results
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
        
        # Setup output directory
        self.base_output_dir = Path(__file__).parent.parent / "semantic_xpath_result"
        self.experiment_dir = None  # Set during run()
        
        # Track results for experiment log
        self._session_results: Dict[str, Dict[str, Any]] = {}
    
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
    
    def _sanitize_query_name(self, query: str, index: int) -> str:
        """Create a sanitized folder name from query text."""
        # Take first few words
        words = query.split()[:4]
        name = "_".join(words)
        
        # Remove special characters
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        name = name[:30]  # Limit length
        
        if not name:
            name = f"Query_{index:03d}"
        else:
            name = f"Query_{name}"
        
        return name
    
    def _run_session(
        self,
        query_list: List[str],
        session_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run a session with multiple queries sharing the same tree state.
        
        Args:
            query_list: List of queries to execute in this session
            session_index: 1-based session index
            
        Returns:
            Dict mapping query IDs to their results
        """
        session_name = f"Session_{session_index}"
        session_dir = self.experiment_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Session {session_index}: {len(query_list)} queries")
        print(f"{'='*60}")
        
        # Get source tree path
        from dense_xpath.schema_loader import get_data_path
        source_tree = get_data_path()
        
        # Copy tree to session directory
        session_tree = session_dir / "tree.xml"
        shutil.copy2(source_tree, session_tree)
        
        # Create pipeline for this session (uses session's tree)
        pipeline = SemanticXPathPipeline(tree_path=session_tree)
        
        session_results = {}
        
        for query_index, query in enumerate(query_list, start=1):
            query_name = self._sanitize_query_name(query, query_index)
            query_dir = session_dir / query_name
            query_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"\n  [{query_index}/{len(query_list)}] {query[:60]}...")
            
            # Set traces path for this query
            pipeline.set_traces_path(query_dir)
            
            # Execute query
            start_time = time.perf_counter()
            result = pipeline.process_request(query)
            execution_time = (time.perf_counter() - start_time) * 1000
            
            # Format and save query master log
            master_log = LogFormatter.format_query_master_log(
                user_query=query,
                pipeline_result=result,
                traces_dir=query_dir
            )
            master_log["execution_time_ms"] = round(execution_time, 2)
            
            log_path = query_dir / "query_master_log.json"
            LogFormatter.save_query_master_log(master_log, log_path)
            
            # Extract top-k paths for experiment log
            top_k_paths = LogFormatter.extract_top_k_paths(result)
            
            # Store result for experiment log
            query_id = f"{session_name}_{query_name}"
            session_results[query_id] = {
                "query": query,
                "operation": result.get("operation", "UNKNOWN"),
                "success": result.get("success", False),
                "top_k_nodes": top_k_paths,
                "execution_time_ms": round(execution_time, 2)
            }
            
            status = "SUCCESS" if result.get("success") else "FAILED"
            operation = result.get("operation", "UNKNOWN")
            print(f"      {status} | {operation} | {execution_time:.0f}ms")
        
        return session_results
    
    def run(self) -> Dict[str, Any]:
        """
        Run the full experiment.
        
        Returns:
            Experiment log dict
        """
        print(f"\n{'#'*60}")
        print(f"# Experiment: {self.experiment_name}")
        print(f"# Sessions: {len(self.queries)}")
        print(f"{'#'*60}")
        
        # Setup experiment directory
        self.experiment_dir = self._setup_experiment_dir()
        print(f"\nOutput directory: {self.experiment_dir}")
        
        start_time = time.perf_counter()
        
        # Run each session
        for session_index, query_list in enumerate(self.queries, start=1):
            session_results = self._run_session(query_list, session_index)
            self._session_results.update(session_results)
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Build and save experiment log
        experiment_log = LogFormatter.format_experiment_log(
            experiment_name=self.experiment_dir.name,
            sessions_data=self._session_results
        )
        experiment_log["total_execution_time_ms"] = round(total_time, 2)
        
        log_path = self.experiment_dir / "Experiment_Log.json"
        LogFormatter.save_experiment_log(experiment_log, log_path)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Experiment Complete!")
        print(f"{'='*60}")
        print(f"  Total sessions: {len(self.queries)}")
        print(f"  Total queries: {len(self._session_results)}")
        
        success_count = sum(
            1 for r in self._session_results.values() if r.get("success")
        )
        print(f"  Successful: {success_count}/{len(self._session_results)}")
        print(f"  Total time: {total_time/1000:.1f}s")
        print(f"\nResults saved to: {self.experiment_dir}")
        
        return experiment_log


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run experiment with session-based query execution"
    )
    parser.add_argument(
        "--config", "-c", 
        type=str, 
        default="experiment.yaml",
        help="Path to experiment config file (default: experiment.yaml)"
    )
    
    args = parser.parse_args()
    
    runner = ExperimentRunner(args.config)
    experiment_log = runner.run()
    
    # Print top-k results summary
    print("\n" + "="*60)
    print("Top-K Results Summary:")
    print("="*60)
    for query_id, data in experiment_log["results"].items():
        print(f"\n{query_id}:")
        print(f"  Query: {data['query'][:50]}...")
        print(f"  Top nodes:")
        for path in data.get("top_k_nodes", [])[:3]:
            print(f"    - {path}")


if __name__ == "__main__":
    main()
