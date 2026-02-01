"""
Experiment Runner - Execute queries across multiple pipelines and store results.

Usage:
    python experiment_runner.py --config experiment.yaml

Output Structure:
    experiment_results/{experiment_name}/
    ├── experiment_config.yaml
    ├── {pipeline_name}/
    │   ├── query_001_result.json
    │   └── run.log
    └── summary.json
"""

import json
import yaml
import shutil
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
import sys
import copy
import xml.etree.ElementTree as ET

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.semantic_xpath_pipeline import SemanticXPathPipeline
from pipeline.incontext_pipeline import IncontextPipeline


@dataclass
class NodeChange:
    """Represents a change to a node (for CUD operations)."""
    path: str
    change_type: str  # "created", "deleted", "updated"
    old_node: Optional[Dict[str, Any]] = None
    new_node: Optional[Dict[str, Any]] = None
    field_changes: Optional[Dict[str, Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "old_node": self.old_node,
            "new_node": self.new_node,
            "field_changes": self.field_changes
        }


@dataclass 
class QueryResult:
    """Result from running a single query."""
    query_index: int
    query: str
    operation: str
    success: bool
    execution_time_ms: float
    token_usage: Optional[Dict[str, int]] = None
    # For READ
    selected_nodes: Optional[List[Dict[str, Any]]] = None
    # For CUD - detailed changes
    changes: Optional[List[NodeChange]] = None
    error: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "query_index": self.query_index,
            "query": self.query,
            "operation": self.operation,
            "success": self.success,
            "execution_time_ms": round(self.execution_time_ms, 2)
        }
        if self.token_usage:
            result["token_usage"] = self.token_usage
        if self.selected_nodes is not None:
            result["selected_nodes"] = self.selected_nodes
        if self.changes:
            result["changes"] = [c.to_dict() for c in self.changes]
        if self.error:
            result["error"] = self.error
        if self.raw_result:
            result["raw_result"] = self.raw_result
        return result


class ExperimentRunner:
    """Runs experiments across multiple pipelines."""
    
    SUPPORTED_PIPELINES = ["semantic_xpath", "incontext"]
    
    def __init__(self, config_path: str):
        """
        Initialize the experiment runner.
        
        Args:
            config_path: Path to experiment.yaml config file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        self.experiment_name = self.config["name"]
        self.pipelines = self.config.get("pipelines", [])
        self.queries = self.config.get("queries", [])
        
        # Setup output directory
        self.base_output_dir = Path(__file__).parent / "experiment_results"
        self.experiment_dir = self.base_output_dir / self.experiment_name
        
        # Pipeline instances (lazy loaded)
        self._pipeline_instances = {}
        
        # Store original tree state for diff comparison
        self._original_tree_xml = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate experiment config."""
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Validate required fields
        if "name" not in config:
            raise ValueError("Experiment config must have 'name' field")
        if "queries" not in config or not config["queries"]:
            raise ValueError("Experiment config must have non-empty 'queries' list")
        if "pipelines" not in config or not config["pipelines"]:
            raise ValueError("Experiment config must have non-empty 'pipelines' list")
        
        # Validate pipelines
        for pipeline in config["pipelines"]:
            if pipeline not in self.SUPPORTED_PIPELINES:
                raise ValueError(f"Unsupported pipeline: {pipeline}. Supported: {self.SUPPORTED_PIPELINES}")
        
        return config
    
    def _get_pipeline(self, name: str):
        """Get or create a pipeline instance."""
        if name not in self._pipeline_instances:
            # Setup isolated environment for this pipeline
            pipeline_dir = self.experiment_dir / name
            pipeline_dir.mkdir(parents=True, exist_ok=True)
            
            # Get source data path
            from dense_xpath.schema_loader import get_data_path
            source_path = get_data_path()
            
            # Define target path for this pipeline's memory
            # Use a subdirectory 'memory' to keep it organized
            memory_dir = pipeline_dir / "memory"
            memory_dir.mkdir(exist_ok=True)
            target_path = memory_dir / source_path.name
            
            # Copy source to target if it doesn't exist (initialize from source)
            if not target_path.exists():
                shutil.copy2(source_path, target_path)
            
            if name == "semantic_xpath":
                self._pipeline_instances[name] = SemanticXPathPipeline(tree_path=target_path)
            elif name == "incontext":
                self._pipeline_instances[name] = IncontextPipeline(tree_path=target_path)
            else:
                raise ValueError(f"Unknown pipeline: {name}")
        
        return self._pipeline_instances[name]
    
    def _setup_output_dirs(self):
        """Create output directory structure."""
        # Create experiment directory
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        
        # Create pipeline subdirectories
        for pipeline in self.pipelines:
            pipeline_dir = self.experiment_dir / pipeline
            pipeline_dir.mkdir(exist_ok=True)
        
        # Copy experiment config
        shutil.copy(self.config_path, self.experiment_dir / "experiment_config.yaml")
    
    def _setup_logging(self, pipeline_name: str) -> logging.Logger:
        """Setup logging for a pipeline run."""
        log_path = self.experiment_dir / pipeline_name / "run.log"
        
        logger = logging.getLogger(f"experiment.{pipeline_name}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        logger.handlers = []
        
        # File handler
        fh = logging.FileHandler(log_path, mode='w', encoding='utf-8')
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger
    
    def _capture_tree_state(self, pipeline) -> Optional[str]:
        """Capture current tree state as XML string for diff comparison."""
        try:
            if hasattr(pipeline, 'executor') and hasattr(pipeline.executor, 'tree'):
                # Semantic XPath pipeline
                tree = pipeline.executor.tree
                return ET.tostring(tree.getroot(), encoding="unicode")
            elif hasattr(pipeline, 'tree'):
                # Incontext pipeline
                if pipeline.tree is not None:
                    return ET.tostring(pipeline.tree.getroot(), encoding="unicode")
        except Exception:
            pass
        return None
    
    def _extract_node_data(self, element: ET.Element) -> Dict[str, Any]:
        """Extract all data from an XML element as a dict."""
        data = {"type": element.tag}
        
        # Add attributes
        for key, value in element.attrib.items():
            data[key] = value
        
        # Add child elements as fields
        for child in element:
            if len(child) == 0:  # Leaf node
                data[child.tag] = child.text.strip() if child.text else ""
            elif child.tag == "highlights":  # Special handling for lists
                data["highlights"] = [h.text.strip() for h in child if h.text]
            else:
                # Nested structure - recurse
                data[child.tag] = self._extract_node_data(child)
        
        return data
    
    def _extract_changes_from_semantic_xpath(
        self, 
        result: Dict[str, Any], 
        operation: str
    ) -> List[NodeChange]:
        """Extract detailed node changes from semantic xpath pipeline result."""
        changes = []
        
        if operation == "DELETE":
            # Extract deleted node info
            deleted_paths = result.get("deleted_paths", [])
            for path in deleted_paths:
                changes.append(NodeChange(
                    path=path,
                    change_type="deleted",
                    old_node={"path": path},  # Full node data would need tree access
                    new_node=None
                ))
        
        elif operation == "UPDATE":
            update_results = result.get("update_results", [])
            for update in update_results:
                field_changes = {}
                changes_data = update.get("changes", {}).get("changes", {})
                for field, change in changes_data.items():
                    field_changes[field] = {
                        "from": change.get("from"),
                        "to": change.get("to")
                    }
                
                changes.append(NodeChange(
                    path=update.get("path", ""),
                    change_type="updated",
                    old_node=None,  # Would need to capture before
                    new_node=None,  # Would need to capture after
                    field_changes=field_changes
                ))
        
        elif operation == "CREATE":
            created_path = result.get("created_path")
            if created_path:
                content_result = result.get("content_result", {})
                changes.append(NodeChange(
                    path=created_path,
                    change_type="created",
                    old_node=None,
                    new_node={
                        "node_type": content_result.get("node_type"),
                        "fields": content_result.get("fields", {})
                    }
                ))
        
        return changes
    
    def _extract_changes_from_incontext(
        self,
        result,  # PipelineResult
        original_xml: str
    ) -> List[NodeChange]:
        """Extract detailed node changes from incontext pipeline result."""
        changes = []
        
        if result.diff:
            # Use the new node-level diff format
            for node_diff in result.diff.created_nodes:
                changes.append(NodeChange(
                    path=f"Day {node_diff.day} > {node_diff.name}",
                    change_type="created",
                    new_node=node_diff.new_data
                ))
            
            for node_diff in result.diff.deleted_nodes:
                changes.append(NodeChange(
                    path=f"Day {node_diff.day} > {node_diff.name}",
                    change_type="deleted", 
                    old_node=node_diff.old_data
                ))
            
            for node_diff in result.diff.modified_nodes:
                changes.append(NodeChange(
                    path=f"Day {node_diff.day} > {node_diff.name}",
                    change_type="modified",
                    old_node=node_diff.old_data,
                    new_node=node_diff.new_data,
                    field_changes=node_diff.changed_fields
                ))
        
        return changes
    
    def _run_query_semantic_xpath(
        self, 
        pipeline: SemanticXPathPipeline,
        query: str, 
        query_index: int,
        logger: logging.Logger
    ) -> QueryResult:
        """Run a single query on the semantic xpath pipeline."""
        logger.info(f"Running query {query_index + 1}: {query}")
        
        start_time = time.perf_counter()
        try:
            result = pipeline.process_request(query)
            execution_time = (time.perf_counter() - start_time) * 1000
            
            operation = result.get("operation", "UNKNOWN")
            success = result.get("success", False)
            
            # Extract token usage from timing
            token_usage = None
            timing = result.get("timing", {})
            if timing.get("total_tokens"):
                token_usage = timing["total_tokens"]
            
            # Extract selected nodes for READ
            selected_nodes = None
            if operation == "READ":
                selected_nodes = result.get("selected_nodes", [])
            
            # Extract changes for CUD
            changes = None
            if operation in ("CREATE", "UPDATE", "DELETE"):
                changes = self._extract_changes_from_semantic_xpath(result, operation)
            
            query_result = QueryResult(
                query_index=query_index,
                query=query,
                operation=operation,
                success=success,
                execution_time_ms=execution_time,
                token_usage=token_usage,
                selected_nodes=selected_nodes,
                changes=changes,
                raw_result=result
            )
            
            logger.info(f"  Operation: {operation}, Success: {success}, Time: {execution_time:.1f}ms")
            return query_result
            
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"  Error: {str(e)}")
            return QueryResult(
                query_index=query_index,
                query=query,
                operation="ERROR",
                success=False,
                execution_time_ms=execution_time,
                error=str(e)
            )
    
    def _run_query_incontext(
        self,
        pipeline: IncontextPipeline,
        query: str,
        query_index: int,
        logger: logging.Logger
    ) -> QueryResult:
        """Run a single query on the incontext pipeline."""
        logger.info(f"Running query {query_index + 1}: {query}")
        
        # Capture original tree state
        original_xml = self._capture_tree_state(pipeline)
        
        start_time = time.perf_counter()
        try:
            result = pipeline.process_request(query)
            execution_time = (time.perf_counter() - start_time) * 1000
            
            operation = result.operation
            success = result.success
            
            # Token usage
            token_usage = None
            if result.token_usage:
                token_usage = result.token_usage.to_dict()
            
            # Selected nodes for READ (parse from result_xml)
            selected_nodes = None
            if operation == "READ" and result.result_xml:
                # For READ, the result_xml contains the selected nodes
                selected_nodes = [{"xml": result.result_xml}]
            
            # Changes for CUD
            changes = None
            if operation in ("CREATE", "UPDATE", "DELETE"):
                changes = self._extract_changes_from_incontext(result, original_xml or "")
            
            query_result = QueryResult(
                query_index=query_index,
                query=query,
                operation=operation,
                success=success,
                execution_time_ms=execution_time,
                token_usage=token_usage,
                selected_nodes=selected_nodes,
                changes=changes,
                raw_result=result.to_dict()
            )
            
            logger.info(f"  Operation: {operation}, Success: {success}, Time: {execution_time:.1f}ms")
            if token_usage:
                logger.info(f"  Tokens: {token_usage.get('total_tokens', 0)}")
            
            return query_result
            
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"  Error: {str(e)}")
            return QueryResult(
                query_index=query_index,
                query=query,
                operation="ERROR",
                success=False,
                execution_time_ms=execution_time,
                error=str(e)
            )
    
    def _save_result(self, result: QueryResult, pipeline_name: str):
        """Save a query result to file."""
        filename = f"query_{result.query_index + 1:03d}_result.json"
        filepath = self.experiment_dir / pipeline_name / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    def run(self) -> Dict[str, Any]:
        """
        Run the full experiment.
        
        Returns:
            Summary dict with overall statistics
        """
        print(f"\n{'='*60}")
        print(f"Experiment: {self.experiment_name}")
        print(f"Pipelines: {', '.join(self.pipelines)}")
        print(f"Queries: {len(self.queries)}")
        print(f"{'='*60}\n")
        
        # Setup output directories
        self._setup_output_dirs()
        
        # Track summary statistics
        summary = {
            "experiment_name": self.experiment_name,
            "start_time": datetime.now().isoformat(),
            "total_queries": len(self.queries),
            "pipelines": {}
        }
        
        # Run each pipeline
        for pipeline_name in self.pipelines:
            print(f"\n--- Running pipeline: {pipeline_name} ---\n")
            
            logger = self._setup_logging(pipeline_name)
            logger.info(f"Starting pipeline: {pipeline_name}")
            logger.info(f"Total queries: {len(self.queries)}")
            
            pipeline = self._get_pipeline(pipeline_name)
            pipeline_start = time.perf_counter()
            
            results = []
            success_count = 0
            total_tokens = 0
            
            for i, query in enumerate(self.queries):
                print(f"  [{i+1}/{len(self.queries)}] {query[:50]}...")
                
                if pipeline_name == "semantic_xpath":
                    result = self._run_query_semantic_xpath(pipeline, query, i, logger)
                else:  # incontext
                    result = self._run_query_incontext(pipeline, query, i, logger)
                
                results.append(result)
                
                if result.success:
                    success_count += 1
                
                if result.token_usage:
                    total_tokens += result.token_usage.get("total_tokens", 0)
                
                # Save individual result
                self._save_result(result, pipeline_name)
            
            pipeline_time = (time.perf_counter() - pipeline_start) * 1000
            
            # Record pipeline summary
            summary["pipelines"][pipeline_name] = {
                "total_queries": len(self.queries),
                "success_count": success_count,
                "total_time_ms": round(pipeline_time, 2),
                "total_tokens": total_tokens,
                "avg_time_per_query_ms": round(pipeline_time / len(self.queries), 2) if self.queries else 0
            }
            
            logger.info(f"Pipeline complete: {success_count}/{len(self.queries)} succeeded")
            logger.info(f"Total time: {pipeline_time:.1f}ms")
            logger.info(f"Total tokens: {total_tokens}")
            
            print(f"\n  ✅ {success_count}/{len(self.queries)} queries succeeded")
            print(f"  ⏱️  Total time: {pipeline_time:.1f}ms")
            print(f"  🔢 Total tokens: {total_tokens}")
        
        # Save summary
        summary["end_time"] = datetime.now().isoformat()
        summary_path = self.experiment_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"Experiment complete!")
        print(f"Results saved to: {self.experiment_dir}")
        print(f"{'='*60}\n")
        
        return summary


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run experiment across pipelines")
    parser.add_argument("--config", "-c", type=str, default="experiment.yaml",
                        help="Path to experiment config file (default: experiment.yaml)")
    
    args = parser.parse_args()
    
    runner = ExperimentRunner(args.config)
    summary = runner.run()
    
    # Print summary
    print("\nSummary:")
    for pipeline, stats in summary["pipelines"].items():
        print(f"  {pipeline}: {stats['success_count']}/{stats['total_queries']} succeeded, "
              f"{stats['total_tokens']} tokens, {stats['total_time_ms']:.0f}ms")


if __name__ == "__main__":
    main()
