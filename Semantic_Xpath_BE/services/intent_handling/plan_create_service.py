"""
Plan Create Service - Handles the PLAN_CREATE intent.

Orchestrates: registry (create task) -> plan builder (generate XML) -> state (commit).

Migrated from Semantic_XPath_Demo/refactor/controller_core/intent_handlers.py (PlanCreateIntentHandler).
"""

from __future__ import annotations

from typing import Optional

from common.types import (
    HandlerResult,
    ReplaceXmlNode,
    RegistryApplyRequest,
    RoutingDecision,
    SessionUpdate,
    TurnRequest,
)
from interfaces.state_store import TaskStateStore
from interfaces.xml_manager import XmlStateManager
from services.intent_handling.plan_builder_service import PlanBuilderService
from stores.registry_store import RegistryStore


class PlanCreateService:
    """Creates a new plan from a user utterance."""

    intent: str = "PLAN_CREATE"

    def __init__(
        self,
        registry: RegistryStore,
        plan_builder: PlanBuilderService,
        state_store: TaskStateStore | None = None,
        xml_state_manager: XmlStateManager | None = None,
        commit_mode: str = "CREATE_NEW_VERSION",
    ) -> None:
        if state_store is None and xml_state_manager is None:
            raise ValueError("PlanCreateService requires state_store or xml_state_manager")
        self.registry = registry
        self.state_store = state_store
        self.xml_state_manager = xml_state_manager
        self.plan_builder = plan_builder
        self.commit_mode = commit_mode

    def handle(
        self,
        req: TurnRequest,
        routing: RoutingDecision,
        context_messages: Optional[list[dict[str, str]]] = None,
    ) -> HandlerResult:
        # Check for clarification
        if routing.requires_clarification and routing.clarification_question:
            return HandlerResult(
                stop=True,
                generation_hint=routing.clarification_question,
            )

        # 1. Create task in registry
        apply_res = self.registry.apply(RegistryApplyRequest(action="CREATE_TASK"))
        task_id = apply_res.active_task_id or apply_res.created_task_id
        version_id = apply_res.active_version_id or apply_res.created_version_id
        if not task_id or not version_id:
            return HandlerResult(
                stop=True,
                generation_hint="Plan creation failed: registry did not return task/version IDs.",
            )

        # 2. Build initial state via GPT
        new_state = self.plan_builder.build_initial_state(
            req.user_utterance,
            task_id,
            version_id,
            context_messages=context_messages,
        )

        # 3. Commit state
        task_xml = (new_state.metadata or {}).get("xml")
        if isinstance(task_xml, str) and task_xml.strip() and self.xml_state_manager is not None:
            commit_result = self.xml_state_manager.commit(
                task_id=task_id,
                base_version_id=version_id,
                ops=[ReplaceXmlNode(xpath=".", xml_fragment=task_xml)],
                commit_message="initial state",
            )
        elif self.state_store is not None:
            from common.types import CommitRequest
            commit_result = self.state_store.commit(
                CommitRequest(
                    task_id=task_id,
                    commit_mode=self.commit_mode,
                    new_state=new_state,
                    commit_message="initial state",
                )
            )
        else:
            return HandlerResult(
                stop=True,
                generation_hint="Plan creation failed: planner did not return valid XML.",
            )

        # 4. Build result
        task_name = None
        task_xml = task_xml if isinstance(task_xml, str) else None
        if new_state.metadata:
            task_name = new_state.metadata.get("task_name")
        if not task_name:
            task_name = req.user_utterance.strip() or "New plan"

        generation_hint = f'We created the plan named "{task_name}".'
        session_updates = SessionUpdate()

        if commit_result.status == "OK":
            new_version_id = commit_result.new_version_id or version_id
            if new_version_id != version_id:
                self.registry.apply(
                    RegistryApplyRequest(
                        action="SWITCH_VERSION",
                        task_id=task_id,
                        version_id=new_version_id,
                    )
                )
            session_updates.active_task_id = task_id
            session_updates.active_version_id = new_version_id
        else:
            generation_hint = (
                "Plan creation failed. "
                f"Errors: {', '.join(commit_result.errors or [])}"
            )

        return HandlerResult(
            session_updates=session_updates,
            generation_hint=generation_hint,
            task_name=task_name,
            task_xml=task_xml,
        )
