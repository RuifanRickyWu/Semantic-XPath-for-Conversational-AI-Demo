"""
CRUD Handlers for semantic XPath tree operations.

Provides downstream task handlers for:
- Read operations
- Delete operations
- Update operations
- Create operations
"""

from .read_handler import ReadHandler
from .delete_handler import DeleteHandler
from .update_handler import UpdateHandler
from .create_handler import CreateHandler

__all__ = [
    "ReadHandler",
    "DeleteHandler",
    "UpdateHandler",
    "CreateHandler"
]
