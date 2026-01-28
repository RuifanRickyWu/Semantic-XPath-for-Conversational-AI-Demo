"""
CRUD module for tree operations.

Provides:
- CRUDExecutor: Main executor for CRUD operations with 3-stage LLM pipeline
- Handlers: ReadHandler, DeleteHandler, UpdateHandler, CreateHandler
- Base classes: BaseHandler, HandlerResult, and result types
"""

from .crud_executor import CRUDExecutor, PipelineTimer, StageResult
from .base import (
    BaseHandler,
    HandlerResult,
    SelectedNode,
    ReadResult,
    DeleteResult,
    UpdateItem,
    UpdateResult,
    CreateResult
)
from .read_handler import ReadHandler
from .delete_handler import DeleteHandler
from .update_handler import UpdateHandler
from .create_handler import CreateHandler

__all__ = [
    # Main executor
    "CRUDExecutor",
    "PipelineTimer",
    "StageResult",
    
    # Base classes
    "BaseHandler",
    "HandlerResult",
    "SelectedNode",
    
    # Result types
    "ReadResult",
    "DeleteResult",
    "UpdateItem",
    "UpdateResult",
    "CreateResult",
    
    # Handlers
    "ReadHandler",
    "DeleteHandler",
    "UpdateHandler",
    "CreateHandler"
]
