"""
Semantic XPath Logger - Logging utilities for semantic xpath pipeline.

Provides structured logging and trace management for:
- Pipeline execution logging
- Result formatting for logs
- Session metrics tracking
- Trace file organization
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class SemanticXPathLogger:
    """
    Logger for Semantic XPath Pipeline operations.
    
    Provides structured logging with:
    - Operation tracking
    - Result logging
    - Performance metrics
    - Error tracking
    """
    
    def __init__(self, log_file: Optional[Path] = None, level: int = logging.INFO):
        """
        Initialize the logger.
        
        Args:
            log_file: Optional path to log file. If None, logs to console only.
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger("SemanticXPath")
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(console_format)
            self.logger.addHandler(file_handler)
    
    def log_operation_start(self, operation: str, request: str):
        """
        Log the start of a CRUD operation.
        
        Args:
            operation: Operation type (READ, CREATE, UPDATE, DELETE)
            request: User request text
        """
        self.logger.info(f"Starting {operation} operation: {request[:100]}")
    
    def log_operation_result(self, result: Dict[str, Any]):
        """
        Log the result of a CRUD operation.
        
        Args:
            result: Operation result dictionary
        """
        operation = result.get("operation", "UNKNOWN")
        success = result.get("success", False)
        status = "SUCCESS" if success else "FAILED"
        timing = result.get("total_time_ms", 0)
        
        self.logger.info(
            f"{operation} operation {status} in {timing:.1f}ms"
        )
        
        if not success and result.get("message"):
            self.logger.error(f"Error: {result['message']}")
    
    def log_session_stats(self, stats: Dict[str, Any]):
        """
        Log session statistics.
        
        Args:
            stats: Session statistics dictionary
        """
        self.logger.info(
            f"Session Stats - Operations: {stats.get('operations', 0)}, "
            f"Success Rate: {stats.get('success_rate', 0):.1f}%"
        )
    
    def log_error(self, error: Exception, context: str = ""):
        """
        Log an error with context.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
        """
        self.logger.error(f"Error in {context}: {str(error)}", exc_info=True)


class TraceLogger:
    """
    Manages trace file logging for detailed operation tracking.
    
    Organizes trace files by:
    - Timestamp
    - Operation type
    - Session
    """
    
    def __init__(self, traces_dir: Optional[Path] = None):
        """
        Initialize the trace logger.
        
        Args:
            traces_dir: Directory for trace files. If None, uses default.
        """
        if traces_dir is None:
            traces_dir = Path.cwd() / "traces" / "pipeline_traces"
        
        self.traces_dir = traces_dir
        self.traces_dir.mkdir(parents=True, exist_ok=True)
    
    def save_operation_trace(
        self,
        operation: str,
        result: Dict[str, Any],
        timestamp: Optional[str] = None
    ):
        """
        Save a detailed trace of an operation.
        
        Args:
            operation: Operation type
            result: Operation result dictionary
            timestamp: Optional timestamp string (auto-generated if None)
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        filename = f"{operation.lower()}_{timestamp}.json"
        trace_file = self.traces_dir / filename
        
        with open(trace_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
    
    def save_session_summary(self, stats: Dict[str, Any], session_id: str):
        """
        Save session summary.
        
        Args:
            stats: Session statistics
            session_id: Unique session identifier
        """
        filename = f"session_{session_id}.json"
        summary_file = self.traces_dir / filename
        
        with open(summary_file, "w") as f:
            json.dump(stats, f, indent=2, default=str)
    
    def get_trace_files(self, operation: Optional[str] = None) -> list[Path]:
        """
        Get list of trace files, optionally filtered by operation.
        
        Args:
            operation: Optional operation type to filter by
            
        Returns:
            List of trace file paths
        """
        if operation:
            pattern = f"{operation.lower()}_*.json"
        else:
            pattern = "*.json"
        
        return sorted(self.traces_dir.glob(pattern), reverse=True)


def create_pipeline_logger(
    log_file: Optional[Path] = None,
    traces_dir: Optional[Path] = None,
    level: int = logging.INFO
) -> tuple[SemanticXPathLogger, TraceLogger]:
    """
    Create a complete logging setup for the pipeline.
    
    Args:
        log_file: Optional path to log file
        traces_dir: Optional directory for trace files
        level: Logging level
        
    Returns:
        Tuple of (logger, trace_logger)
    """
    logger = SemanticXPathLogger(log_file, level)
    trace_logger = TraceLogger(traces_dir)
    
    return logger, trace_logger
