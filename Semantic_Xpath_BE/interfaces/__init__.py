"""
Protocol interfaces for all pluggable components.

These define the contracts that implementations must satisfy.
The orchestrator and other consumers depend on these protocols,
not on concrete classes, enabling easy substitution and testing.
"""

from .chatting import Chatting
from .context_manager import ConversationContextStore
from .registry import TaskRegistry
from .retriever import Retriever
from .routting import Routting
from .session_manager import SessionManager
from .state_builder import StateBuilder
from .state_store import TaskStateStore

__all__ = [
    "Chatting",
    "ConversationContextStore",
    "Routting",
    "SessionManager",
    "StateBuilder",
    "TaskRegistry",
    "TaskStateStore",
    "Retriever",
]
