"""
Trace Writer - Handles logging and trace file writing.
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
            f.write("=" * 60 + "\n\n")
            f.write("Execution Log:\n")
            f.write("-" * 40 + "\n")
            for line in result.execution_log:
                f.write(line + "\n")
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"Matched Nodes: {len(result.matched_nodes)}\n")
            f.write("-" * 40 + "\n")
            for matched in result.matched_nodes:
                f.write(json.dumps(matched.to_dict(), indent=2) + "\n")
        
        logger.debug(f"Saved execution log to {log_file}")
    
    def _save_json_trace(self, timestamp: str, result: ExecutionResult):
        """Save detailed JSON trace for analysis."""
        trace_file = self.traces_path / f"execution_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            "query": result.query,
            "traversal_steps": [step.to_dict() for step in result.traversal_steps],
            "scoring_traces": result.scoring_traces,
            "matched_nodes": [m.to_dict() for m in result.matched_nodes],
            "summary": {
                "total_steps": len(result.traversal_steps),
                "total_scoring_calls": len(result.scoring_traces),
                "matched_count": len(result.matched_nodes)
            }
        }
        
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved reasoning trace to {trace_file}")

