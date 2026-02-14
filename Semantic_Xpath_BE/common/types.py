"""
Shared data types for the Semantic XPath conversation system.

Migrated from Semantic_XPath_Demo/refactor/controller_core/types.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union


# ---------------------------------------------------------------------------
# Literal type aliases
# ---------------------------------------------------------------------------

Bit = Literal[0, 1]

RoutingIntent = Literal[
    "CHAT",
    "PLAN_QA",
    "PLAN_EDIT",
    "PLAN_CREATE",
    "REGISTRY_QA",
    "REGISTRY_EDIT",
]

RegistryAction = Literal[
    "LIST_TASKS",
    "LIST_VERSIONS",
    "ACTIVATE_TASK",
    "SWITCH_VERSION",
    "CREATE_TASK",
    "CREATE_VERSION",
    "NONE",
]

CommitMode = Literal["CREATE_NEW_VERSION", "OVERWRITE"]
CommitStatus = Literal["OK", "FAILED"]

RetrieveMode = Literal["STRUCTURAL_FIRST", "XPATH_ONLY", "HYBRID"]
RetrieveUsed = Literal["STRUCTURAL", "XPATH", "HYBRID"]

AmbiguityResolveStatus = Literal["RESOLVED", "ASK"]


# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------

@dataclass
class ContextTurn:
    user: str
    assistant: str
    timestamp: Optional[str] = None


@dataclass
class FocusMemory:
    last_task_reference: Optional[str] = None
    last_version_reference: Optional[str] = None
    last_target_node_id: Optional[str] = None
    last_action: Optional[str] = None


@dataclass
class FocusLabels:
    last_task_label: Optional[str] = None
    last_version_label: Optional[str] = None
    last_target_label: Optional[str] = None
    last_action: Optional[str] = None


@dataclass
class IntentMemory:
    last_intent: Optional[str] = None
    last_intent_label: Optional[str] = None
    last_user_utterance: Optional[str] = None
    awaiting_clarification: Optional[bool] = None
    clarification_question: Optional[str] = None


@dataclass
class ConversationContext:
    last_user: Optional[str] = None
    last_assistant: Optional[str] = None
    window: Optional[List[ContextTurn]] = None
    focus: Optional[FocusMemory] = None
    session_notes: Optional[str] = None
    intent_memory: Optional[IntentMemory] = None


# ---------------------------------------------------------------------------
# Turn request / response
# ---------------------------------------------------------------------------

@dataclass
class TurnRequest:
    user_utterance: str
    session_id: str
    timestamp: str
    original_user_utterance: Optional[str] = None
    conversation_context: Optional[ConversationContext] = None


@dataclass
class SessionSnapshot:
    active_task_id: Optional[str] = None
    active_version_id: Optional[str] = None
    focus_path: Optional[str] = None
    last_retrieved_node_ids: Optional[List[str]] = None


@dataclass
class SessionUpdate:
    active_task_id: Optional[str] = None
    active_version_id: Optional[str] = None
    focus_path: Optional[str] = None
    last_retrieved_node_ids: Optional[List[str]] = None


@dataclass
class RoutingDecision:
    intent: RoutingIntent
    registry_op: Bit
    intent_label: Optional[str] = None
    confidence: Optional[float] = None
    requires_clarification: Optional[bool] = None
    clarification_question: Optional[str] = None
    reformulated_utterance: Optional[str] = None


@dataclass
class TurnTelemetry:
    events: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResponse:
    assistant_message: str
    routing: RoutingDecision
    session_updates: SessionUpdate
    telemetry: Optional[TurnTelemetry] = None


@dataclass
class HandlerResult:
    session_updates: SessionUpdate = field(default_factory=SessionUpdate)
    stop: bool = False
    generation_hint: Optional[str] = None
    task_name: Optional[str] = None
    task_xml: Optional[str] = None


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

@dataclass
class RouteInput:
    utterance: str
    session: SessionSnapshot
    context_messages: Optional[List[Dict[str, str]]] = None


@dataclass
class RouteResult:
    routing: RoutingDecision
    effective_utterance: str
    original_utterance: Optional[str] = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class RegistryApplyRequest:
    action: RegistryAction
    task_id: Optional[str] = None
    version_id: Optional[str] = None
    task_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RegistryApplyResult:
    active_task_id: Optional[str] = None
    active_version_id: Optional[str] = None
    tasks: Optional[List[Any]] = None
    versions: Optional[List[Any]] = None
    created_task_id: Optional[str] = None
    created_version_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Plan state / tree
# ---------------------------------------------------------------------------

@dataclass
class TreeNode:
    node_id: str
    type: str
    text: str
    attrs: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    time_window: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    children: List[TreeNode] = field(default_factory=list)


@dataclass
class TaskState:
    task_id: str
    version_id: str
    schema_version: str
    root: TreeNode
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DiffSummary:
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommitRequest:
    task_id: str
    base_version_id: Optional[str] = None
    commit_mode: CommitMode = "CREATE_NEW_VERSION"
    new_state: Optional[TaskState] = None
    ops: Optional[List["EditOp"]] = None
    commit_message: Optional[str] = None


@dataclass
class CommitResult:
    status: CommitStatus
    new_version_id: Optional[str] = None
    diff: Optional[DiffSummary] = None
    changed_nodes: Optional[List[TreeNode]] = None
    errors: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Chatter / realize
# ---------------------------------------------------------------------------

@dataclass
class RealizeRequest:
    utterance: str
    routing: RoutingDecision
    session: SessionSnapshot
    original_utterance: Optional[str] = None
    conversation_context: Optional[ConversationContext] = None
    context_messages: Optional[List[Dict[str, str]]] = None
    registry_context: Optional[Any] = None
    state_context: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# XML state / operations
# ---------------------------------------------------------------------------

@dataclass
class XmlState:
    task_id: str
    version_id: str
    schema_version: str
    xml_str: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class XmlEditResult:
    ok: bool
    xml_str: Optional[str] = None
    errors: Optional[List[str]] = None
    changed_xpaths: Optional[List[str]] = None


@dataclass
class AddXmlNode:
    parent_xpath: str
    xml_fragment: str
    position: Optional[int] = None


@dataclass
class DeleteXmlNode:
    xpath: str


@dataclass
class ReplaceXmlNode:
    xpath: str
    xml_fragment: str


@dataclass
class MoveXmlNode:
    xpath: str
    new_parent_xpath: str
    position: Optional[int] = None


@dataclass
class EditXmlAttr:
    xpath: str
    attr_name: str
    new_value: Any


@dataclass
class EditXmlText:
    xpath: str
    new_text: str


XmlOp = Union[
    AddXmlNode,
    DeleteXmlNode,
    ReplaceXmlNode,
    MoveXmlNode,
    EditXmlAttr,
    EditXmlText,
]


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

@dataclass
class RetrieveRequest:
    utterance: str
    state: TaskState
    mode: RetrieveMode
    top_k: int


@dataclass
class RetrievedNode:
    node_id: str
    score: Optional[float]
    path: str
    snippet: str
    node: Optional[TreeNode] = None


@dataclass
class RetrieveResult:
    nodes: List[RetrievedNode]
    used: RetrieveUsed
    xpath_query: Optional[str] = None


# ---------------------------------------------------------------------------
# Edit planner
# ---------------------------------------------------------------------------

@dataclass
class EditPlanRequest:
    utterance: str
    state: TaskState
    retrieved_nodes: List[RetrievedNode]
    policy: Dict[str, Any]


@dataclass
class EditPlanResult:
    ops: List["EditOp"]
    rationale: Optional[str] = None
    needs_clarification: Optional[bool] = None
    clarification_question: Optional[str] = None


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Ambiguity resolver
# ---------------------------------------------------------------------------

@dataclass
class AmbiguityResolveRequest:
    utterance: str
    clarification_question: str
    context: Optional[ConversationContext] = None
    session: Optional[SessionSnapshot] = None


@dataclass
class AmbiguityResolveResult:
    status: AmbiguityResolveStatus
    resolved_utterance: Optional[str] = None
    clarification_question: Optional[str] = None
    rationale: Optional[str] = None


# ---------------------------------------------------------------------------
# Tree-level edit operations
# ---------------------------------------------------------------------------

@dataclass
class AddNode:
    parent_id: str
    node: TreeNode
    position: Optional[int] = None


@dataclass
class DeleteNode:
    node_id: str


@dataclass
class MoveNode:
    node_id: str
    new_parent_id: str
    position: Optional[int] = None


@dataclass
class EditField:
    node_id: str
    field_path: str
    new_value: Any


@dataclass
class SwapNodes:
    a: str
    b: str


@dataclass
class ReplaceSubtree:
    node_id: str
    new_subtree: TreeNode


EditOp = Union[
    AddNode,
    DeleteNode,
    MoveNode,
    EditField,
    SwapNodes,
    ReplaceSubtree,
]
