"""
Protocol interfaces for all pluggable components.

These define the contracts that implementations must satisfy.
The orchestrator and other consumers depend on these protocols,
not on concrete classes, enabling easy substitution and testing.
"""

from .ambiguity_resolver import AmbiguityResolver
from .chatter import Chatter
from .context_manager import ConversationContextStore
from .edit_planner import EditPlanner
from .registry import TaskRegistry
from .retriever import Retriever
from .router import Router
from .session_manager import SessionManager
from .state_builder import StateBuilder
from .state_store import TaskStateStore
from .validator import Validator
from .xml_manager import XmlStateManager

__all__ = [
    "AmbiguityResolver",
    "Chatter",
    "ConversationContextStore",
    "EditPlanner",
    "Router",
    "SessionManager",
    "StateBuilder",
    "TaskRegistry",
    "TaskStateStore",
    "Retriever",
    "Validator",
    "XmlStateManager",
]
