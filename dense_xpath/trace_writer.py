"""
Trace Writer - Handles logging and trace file writing.

Writes comprehensive execution traces including:
- Stepwise traversal details
- Atomic scoring results
- Compound predicate composition (AND/OR)
- Hierarchical quantifier evaluation (exist/mass)
- Score fusion across steps (product)
- Final filtering decisions
- CRUD operation traces
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

from .models import ExecutionResult, CRUDExecutionResult

logger = logging.getLogger(__name__)


class TraceWriter:
    """
    Writes execution logs and detailed reasoning traces to files.
    
    Produces two outputs per query:
    1. Human-readable text log (.log)
    2. Detailed JSON trace for analysis (.json)
    """
    
    def __init__(
        self,
        log_path: Path = None,
        traces_path: Path = None
    ):
        """
        Initialize the trace writer.
        
        Args:
            log_path: Directory for text log files
            traces_path: Directory for JSON trace files
        """
        base_path = Path(__file__).parent.parent
        
        self.log_path = log_path or base_path / "traces" / "log"
        self.traces_path = traces_path or base_path / "traces" / "reasoning_traces"
        
        # Ensure directories exist
        self.log_path.mkdir(parents=True, exist_ok=True)
        self.traces_path.mkdir(parents=True, exist_ok=True)
    
    def save_traces(self, timestamp: str, result: ExecutionResult):
        """
        Save execution log and reasoning traces to files.
        
        Args:
            timestamp: Timestamp string for file naming
            result: ExecutionResult containing all trace data
        """
        self._save_text_log(timestamp, result)
        self._save_json_trace(timestamp, result)
    
    def _save_text_log(self, timestamp: str, result: ExecutionResult):
        """Save human-readable text log."""
        log_file = self.log_path / f"execution_{timestamp}.log"
        
        with open(log_file, "w") as f:
            f.write(f"Query: {result.query}\n")
            f.write(f"Data File: {result.data_file}\n")
            f.write(f"Execution Time: {result.execution_time_ms:.2f}ms\n")
            f.write("=" * 60 + "\n\n")
            
            # Execution log
            f.write("Execution Log:\n")
            f.write("-" * 40 + "\n")
            for line in result.execution_log:
                f.write(line + "\n")
            
            # Score Fusion Summary
            if result.score_fusion_trace:
                f.write("\n" + "=" * 60 + "\n")
                f.write("Score Fusion Summary:\n")
                f.write("-" * 40 + "\n")
                for node_trace in result.score_fusion_trace.per_node_traces:
                    f.write(f"\n{node_trace.node_path} ({node_trace.node_type}):\n")
                    for contrib in node_trace.step_contributions:
                        f.write(f"  Step {contrib.step_index}: {contrib.predicate_str}\n")
                        f.write(f"    score={contrib.score:.4f}\n")
                    f.write(f"  Accumulated product: {node_trace.accumulated_product:.4f}\n")
                    f.write(f"  Final score: {node_trace.final_score:.4f}\n")
            
            # Final Filtering Summary
            if result.final_filtering_trace:
                f.write("\n" + "=" * 60 + "\n")
                f.write("Final Filtering:\n")
                f.write("-" * 40 + "\n")
                fft = result.final_filtering_trace
                f.write(f"Before: {fft.before_filter_count} nodes\n")
                f.write(f"Threshold: {fft.threshold}\n")
                f.write(f"Top-K: {fft.top_k}\n")
                f.write(f"After: {fft.after_filter_count} nodes\n")
            
            # Matched Nodes
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"Matched Nodes: {len(result.matched_nodes)}\n")
            f.write("-" * 40 + "\n")
            for i, matched in enumerate(result.matched_nodes, 1):
                f.write(f"\n{i}. {matched.tree_path} (score: {matched.score:.4f})\n")
                f.write(json.dumps(matched.node_data, indent=2, ensure_ascii=False) + "\n")
        
        logger.debug(f"Saved execution log to {log_file}")
    
    def _save_json_trace(self, timestamp: str, result: ExecutionResult):
        """
        Save detailed JSON trace for analysis.
        
        Structure:
        {
            "timestamp": "...",
            "query": "...",
            "data_file": "...",
            "execution_time_ms": ...,
            "traversal_steps": [...],
            "scoring_traces": [...],
            "scoring_details": {
                "step_scores": [...],
                "score_fusion": {...}
            },
            "final_filtering": {...},
            "matched_nodes": [...],
            "summary": {...}
        }
        """
        trace_file = self.traces_path / f"execution_{timestamp}.json"
        
        # Build scoring details from scoring traces
        step_scores = []
        for i, trace in enumerate(result.scoring_traces):
            step_detail = {
                "step_index": i,
                "predicate": trace.get("predicate", ""),
                "predicate_ast": trace.get("predicate_ast", {}),
                "node_scores": trace.get("node_scores", []),
                "ranking": trace.get("ranking", [])
            }
            step_scores.append(step_detail)
        
        # Build score fusion details
        score_fusion = None
        if result.score_fusion_trace:
            score_fusion = result.score_fusion_trace.to_dict()
        
        # Build final filtering details
        final_filtering = None
        if result.final_filtering_trace:
            final_filtering = result.final_filtering_trace.to_dict()
        
        trace_data = {
            "timestamp": timestamp,
            "query": result.query,
            "data_file": result.data_file,
            "execution_time_ms": result.execution_time_ms,
            
            # Stepwise traversal
            "traversal_steps": [step.to_dict() for step in result.traversal_steps],
            
            # Raw scoring traces (detailed per-step)
            "scoring_traces": result.scoring_traces,
            
            # Structured scoring details
            "scoring_details": {
                "step_scores": step_scores,
                "score_fusion": score_fusion
            },
            
            # Final filtering
            "final_filtering": final_filtering,
            
            # Results
            "matched_nodes": [m.to_dict() for m in result.matched_nodes],
            
            # Summary statistics
            "summary": {
                "total_steps": len(result.traversal_steps),
                "total_scoring_calls": len(result.scoring_traces),
                "matched_count": len(result.matched_nodes),
                "execution_time_ms": result.execution_time_ms,
                "has_score_fusion": score_fusion is not None,
                "num_nodes_before_filter": (
                    result.final_filtering_trace.before_filter_count 
                    if result.final_filtering_trace else 0
                ),
                "num_nodes_after_filter": (
                    result.final_filtering_trace.after_filter_count 
                    if result.final_filtering_trace else len(result.matched_nodes)
                )
            }
        }
        
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved reasoning trace to {trace_file}")
        
        # Also print path to console for easy access
        print(f"📝 Trace saved: {trace_file}")
    
    # =========================================================================
    # CRUD Operation Trace Methods
    # =========================================================================
    
    def save_crud_traces(self, timestamp: str, result: Dict[str, Any]):
        """
        Save CRUD operation traces to files.
        
        Args:
            timestamp: Timestamp string for file naming
            result: CRUD operation result dictionary
        """
        self._save_crud_text_log(timestamp, result)
        self._save_crud_json_trace(timestamp, result)
    
    def _save_crud_text_log(self, timestamp: str, result: Dict[str, Any]):
        """Save human-readable CRUD operation log."""
        operation = result.get("operation", "UNKNOWN")
        log_file = self.log_path / f"crud_{operation.lower()}_{timestamp}.log"
        
        with open(log_file, "w") as f:
            f.write(f"CRUD Operation: {operation}\n")
            f.write(f"User Query: {result.get('user_query', '')}\n")
            f.write(f"Full Query: {result.get('full_query', '')}\n")
            f.write(f"Timestamp: {result.get('timestamp', timestamp)}\n")
            f.write(f"Success: {result.get('success', False)}\n")
            f.write("=" * 60 + "\n\n")
            
            # Intent Classification
            intent = result.get("intent", {})
            if intent:
                f.write("Intent Classification:\n")
                f.write("-" * 40 + "\n")
                f.write(f"  Type: {intent.get('intent', 'UNKNOWN')}\n")
                f.write(f"  XPath Hint: {intent.get('xpath_hint', '')}\n")
                f.write(f"  Confidence: {intent.get('confidence', 0.0):.2f}\n")
                if intent.get("operation_details"):
                    f.write(f"  Details: {json.dumps(intent['operation_details'], indent=4)}\n")
                f.write("\n")
            
            # XPath Query
            f.write(f"XPath Query: {result.get('xpath_query', '')}\n\n")
            
            # Operation-specific sections
            if operation == "READ":
                self._write_read_log(f, result)
            elif operation == "DELETE":
                self._write_delete_log(f, result)
            elif operation == "UPDATE":
                self._write_update_log(f, result)
            elif operation == "CREATE":
                self._write_create_log(f, result)
            
            # Tree Version Info
            tree_version = result.get("tree_version")
            if tree_version:
                f.write("\n" + "=" * 60 + "\n")
                f.write("Tree Version:\n")
                f.write("-" * 40 + "\n")
                f.write(f"  Version: {tree_version.get('version', 'N/A')}\n")
                f.write(f"  Path: {tree_version.get('path', 'N/A')}\n")
                f.write(f"  Operation: {tree_version.get('operation', 'N/A')}\n")
        
        logger.debug(f"Saved CRUD log to {log_file}")
    
    def _write_read_log(self, f, result: Dict[str, Any]):
        """Write READ operation specific log sections."""
        f.write("=== READ Operation Results ===\n")
        f.write(f"Candidates: {result.get('candidates_count', 0)}\n")
        f.write(f"Selected: {result.get('selected_count', 0)}\n\n")
        
        selected = result.get("selected_nodes", [])
        if selected:
            f.write("Selected Nodes:\n")
            f.write("-" * 40 + "\n")
            for i, node in enumerate(selected, 1):
                f.write(f"\n{i}. {node.get('type', '?')}: {node.get('name', 'Unknown')}\n")
                if node.get("description"):
                    f.write(f"   {node['description'][:100]}...\n")
    
    def _write_delete_log(self, f, result: Dict[str, Any]):
        """Write DELETE operation specific log sections."""
        f.write("=== DELETE Operation Results ===\n")
        f.write(f"Deleted: {result.get('deleted_count', 0)} node(s)\n\n")
        
        deleted_paths = result.get("deleted_paths", [])
        if deleted_paths:
            f.write("Deleted Paths:\n")
            for path in deleted_paths:
                f.write(f"  - {path}\n")
    
    def _write_update_log(self, f, result: Dict[str, Any]):
        """Write UPDATE operation specific log sections."""
        f.write("=== UPDATE Operation Results ===\n")
        f.write(f"Updated: {result.get('updated_count', 0)} node(s)\n\n")
        
        update_results = result.get("update_results", [])
        for i, update in enumerate(update_results, 1):
            f.write(f"\n{i}. {update.get('path', 'Unknown')}\n")
            f.write(f"   Success: {update.get('success', False)}\n")
            changes = update.get("changes", {})
            if changes:
                f.write("   Changes:\n")
                for field, change_info in changes.get("changes", {}).items():
                    f.write(f"     {field}: {change_info.get('from', '?')} -> {change_info.get('to', '?')}\n")
    
    def _write_create_log(self, f, result: Dict[str, Any]):
        """Write CREATE operation specific log sections."""
        f.write("=== CREATE Operation Results ===\n")
        f.write(f"Created Path: {result.get('created_path', 'None')}\n\n")
        
        # Insertion point
        insertion = result.get("insertion_point", {})
        if insertion:
            f.write("Insertion Point:\n")
            f.write(f"  Parent: {insertion.get('parent_path', 'Unknown')}\n")
            f.write(f"  Position: {insertion.get('position', -1)}\n")
            f.write(f"  Reasoning: {insertion.get('reasoning', '')}\n\n")
        
        # Generated content
        content = result.get("content_result", {})
        if content and content.get("success"):
            f.write("Generated Content:\n")
            f.write(f"  Node Type: {content.get('node_type', '?')}\n")
            fields = content.get("fields", {})
            for field, value in fields.items():
                if isinstance(value, list):
                    f.write(f"  {field}: {', '.join(str(v) for v in value)}\n")
                else:
                    f.write(f"  {field}: {value}\n")
    
    def _save_crud_json_trace(self, timestamp: str, result: Dict[str, Any]):
        """
        Save detailed CRUD operation JSON trace.
        
        Structure:
        {
            "timestamp": "...",
            "operation": "...",
            "user_query": "...",
            "full_query": "...",
            "success": ...,
            "intent": {...},
            "xpath_query": "...",
            "reasoning_trace": {...},
            "operation_specific": {...},
            "tree_version": {...}
        }
        """
        operation = result.get("operation", "unknown").lower()
        trace_file = self.traces_path / f"crud_{operation}_{timestamp}.json"
        
        trace_data = {
            "timestamp": result.get("timestamp", timestamp),
            "operation": result.get("operation"),
            "user_query": result.get("user_query"),
            "full_query": result.get("full_query"),
            "xpath_query": result.get("xpath_query"),
            "success": result.get("success"),
            
            "intent": result.get("intent"),
            "reasoning_trace": result.get("reasoning_trace"),
            
            # Operation-specific data
            "operation_data": self._extract_operation_data(result),
            
            # Tree version
            "tree_version": result.get("tree_version"),
            
            # Summary
            "summary": {
                "operation": result.get("operation"),
                "success": result.get("success"),
                "affected_count": len(result.get("affected_nodes", result.get("deleted_paths", result.get("updated_paths", []))))
            }
        }
        
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved CRUD trace to {trace_file}")
        print(f"📝 CRUD trace saved: {trace_file}")
    
    def _extract_operation_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract operation-specific data for the trace."""
        operation = result.get("operation", "")
        
        if operation == "READ":
            return {
                "candidates_count": result.get("candidates_count"),
                "selected_count": result.get("selected_count"),
                "selected_nodes": result.get("selected_nodes")
            }
        elif operation == "DELETE":
            return {
                "deleted_count": result.get("deleted_count"),
                "deleted_paths": result.get("deleted_paths"),
                "deletion_results": result.get("deletion_results")
            }
        elif operation == "UPDATE":
            return {
                "updated_count": result.get("updated_count"),
                "updated_paths": result.get("updated_paths"),
                "update_results": result.get("update_results")
            }
        elif operation == "CREATE":
            return {
                "created_path": result.get("created_path"),
                "insert_result": result.get("insert_result"),
                "content_result": result.get("content_result"),
                "insertion_point": result.get("insertion_point")
            }
        
        return {}
