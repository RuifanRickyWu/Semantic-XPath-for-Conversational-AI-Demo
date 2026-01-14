"""
Trace Writer - Handles logging and trace file writing.

Writes comprehensive execution traces including:
- Stepwise traversal details
- Atomic scoring results
- Compound predicate composition (AND/OR)
- Hierarchical quantifier evaluation (exists/all)
- Bayesian fusion across steps
- Final filtering decisions
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from .models import ExecutionResult

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
            
            # Bayesian Fusion Summary
            if result.bayesian_fusion_trace:
                f.write("\n" + "=" * 60 + "\n")
                f.write("Bayesian Fusion Summary:\n")
                f.write("-" * 40 + "\n")
                for node_trace in result.bayesian_fusion_trace.per_node_traces:
                    f.write(f"\n{node_trace.node_path} ({node_trace.node_type}):\n")
                    for contrib in node_trace.step_contributions:
                        f.write(f"  Step {contrib.step_index}: {contrib.predicate_str}\n")
                        f.write(f"    score={contrib.score:.4f}, log_odds={contrib.log_odds:.4f}\n")
                    f.write(f"  Accumulated log-odds: {node_trace.accumulated_log_odds:.4f}\n")
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
                "bayesian_fusion": {...}
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
        
        # Build Bayesian fusion details
        bayesian_fusion = None
        if result.bayesian_fusion_trace:
            bayesian_fusion = result.bayesian_fusion_trace.to_dict()
        
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
                "bayesian_fusion": bayesian_fusion
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
                "has_bayesian_fusion": bayesian_fusion is not None,
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
