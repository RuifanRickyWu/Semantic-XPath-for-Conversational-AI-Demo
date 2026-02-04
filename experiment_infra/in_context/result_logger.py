"""
Result Logger - Formats and saves in-context evaluation results.

Provides utilities for:
- Session result files (one per session)
- Experiment-level logs (query_id -> related node paths)
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class QueryResult:
    """Result for a single query within a session."""
    query_id: str
    user_query: str
    related_nodes: List[str]
    downstream_task_result: Dict[str, Any]
    execution_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "user_query": self.user_query,
            "related_nodes": self.related_nodes,
            "downstream_task_result": self.downstream_task_result,
            "execution_time_ms": round(self.execution_time_ms, 2)
        }


@dataclass
class SessionResult:
    """Result for a complete session."""
    session_id: str
    queries: List[QueryResult] = field(default_factory=list)
    final_tree_version: int = 1
    total_execution_time_ms: float = 0.0
    
    def add_query_result(self, result: QueryResult):
        """Add a query result to the session."""
        self.queries.append(result)
        self.total_execution_time_ms += result.execution_time_ms
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "queries": [q.to_dict() for q in self.queries],
            "final_tree_version": self.final_tree_version,
            "total_execution_time_ms": round(self.total_execution_time_ms, 2)
        }


class InContextResultLogger:
    """
    Logger for in-context evaluation results.
    
    Handles:
    - Session result files (one JSON file per session)
    - Experiment-level summary log (all query results)
    """
    
    def __init__(self, experiment_dir: Path):
        """
        Initialize the result logger.
        
        Args:
            experiment_dir: Base directory for experiment results
        """
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        
        # Track all results for experiment log
        self._all_results: Dict[str, List[str]] = {}
        self._session_data: Dict[str, Dict[str, Any]] = {}
    
    def create_session_dir(self, session_id: str) -> Path:
        """
        Create directory for a session.
        
        Args:
            session_id: Session identifier (e.g., "Session_1")
            
        Returns:
            Path to session directory
        """
        session_dir = self.experiment_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    
    def save_session_result(self, session_result: SessionResult, session_dir: Path):
        """
        Save session result to file.
        
        Args:
            session_result: SessionResult object
            session_dir: Directory to save to
        """
        output_path = session_dir / "session_result.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(session_result.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Track for experiment log
        for query in session_result.queries:
            query_key = f"{session_result.session_id}_{query.query_id}"
            self._all_results[query_key] = query.related_nodes
            
            # Extract token usage from downstream result
            token_usage = query.downstream_task_result.get("token_usage", {})
            
            self._session_data[query_key] = {
                "query": query.user_query,
                "operation": query.downstream_task_result.get("operation", "UNKNOWN"),
                "success": query.downstream_task_result.get("success", False),
                "top_k_nodes": query.related_nodes,
                "execution_time_ms": query.execution_time_ms,
                "token_usage": token_usage
            }
    
    def save_experiment_log(
        self,
        experiment_name: str,
        total_sessions: int,
        total_execution_time_ms: float
    ):
        """
        Save experiment-level summary log.
        
        Args:
            experiment_name: Name of the experiment
            total_sessions: Total number of sessions
            total_execution_time_ms: Total execution time
        """
        experiment_log = {
            "experiment_name": experiment_name,
            "timestamp": datetime.now().isoformat(),
            "total_sessions": total_sessions,
            "total_queries": len(self._all_results),
            "results": self._session_data,
            "node_paths_summary": self._all_results,
            "total_execution_time_ms": round(total_execution_time_ms, 2)
        }
        
        output_path = self.experiment_dir / "Experiment_Log.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(experiment_log, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def format_query_result(
        query_index: int,
        user_query: str,
        pipeline_result,  # InContextResult
    ) -> QueryResult:
        """
        Format a pipeline result into a QueryResult.
        
        Args:
            query_index: 1-based query index
            user_query: Original user query
            pipeline_result: InContextResult from pipeline
            
        Returns:
            QueryResult object
        """
        return QueryResult(
            query_id=f"Query_{query_index:03d}",
            user_query=user_query,
            related_nodes=pipeline_result.related_nodes,
            downstream_task_result={
                "operation": pipeline_result.operation,
                "success": pipeline_result.success,
                "version_used": pipeline_result.version_used,
                "reasoning": pipeline_result.reasoning,
                "token_usage": pipeline_result.token_usage,
                "error": pipeline_result.error
            },
            execution_time_ms=pipeline_result.execution_time_ms
        )
    
    @staticmethod
    def format_downstream_result(pipeline_result) -> Dict[str, Any]:
        """
        Format downstream task result.
        
        Args:
            pipeline_result: InContextResult from pipeline
            
        Returns:
            Dict with downstream task details
        """
        return {
            "operation": pipeline_result.operation,
            "success": pipeline_result.success,
            "version_used": pipeline_result.version_used,
            "reasoning": pipeline_result.reasoning,
            "result_preview": pipeline_result.result_xml[:500] if pipeline_result.result_xml else "",
            "token_usage": pipeline_result.token_usage,
            "error": pipeline_result.error
        }
