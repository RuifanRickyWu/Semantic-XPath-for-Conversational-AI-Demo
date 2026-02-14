"""
Plan Create Service - Handles the PLAN_CREATE intent.

Orchestrates: registry (create task) -> plan builder (generate XML) -> state (commit).

Migrated from Semantic_XPath_Demo/refactor/controller_core/intent_handlers.py (PlanCreateIntentHandler).
"""

from __future__ import annotations

from common.types import (
    HandlerResult,
    ReplaceXmlNode,
    RegistryApplyRequest,
    SessionUpdate,
)
from interfaces.state_store import TaskStateStore
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler
from services.intent_handling.plan_builder_service import PlanBuilderService
from stores.registry_store import RegistryStore


class PlanCreateService(BaseIntentHandler):
    """Creates a new plan from a user utterance."""

    intent: str = "PLAN_CREATE"

    def __init__(
        self,
        registry: RegistryStore,
        plan_builder: PlanBuilderService,
        state_store: TaskStateStore,
    ) -> None:
        self.registry = registry
        self.state_store = state_store
        self.plan_builder = plan_builder

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        req = ctx.req
        context_messages = ctx.context_messages
        # 1. Create task in registry
        apply_res = self.registry.apply(
            RegistryApplyRequest(
                action="CREATE_TASK",
                metadata={
                    "version_summary": "Initial version",
                },
            )
        )
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
        if not isinstance(task_xml, str) or not task_xml.strip():
            return HandlerResult(
                stop=True,
                generation_hint="Plan creation failed: planner did not return valid XML.",
            )
        commit_result = self.state_store.commit(
            task_id=task_id,
            base_version_id=version_id,
            ops=[ReplaceXmlNode(xpath=".", xml_fragment=task_xml)],
            commit_message="initial state",
        )

        # 4. Build result
        task_name = None
        task_xml = task_xml if isinstance(task_xml, str) else None
        if new_state.metadata:
            task_name = new_state.metadata.get("task_name")
        if isinstance(task_name, str):
            task_name = task_name.strip() or None
        else:
            task_name = None

        generation_hint = "We created the plan."
        if task_name:
            generation_hint = f'We created the plan named "{task_name}".'
        session_updates = SessionUpdate()

        if commit_result.status == "OK":
            new_version_id = commit_result.new_version_id or version_id
            if task_name:
                self.registry.apply(
                    RegistryApplyRequest(
                        action="UPDATE_TASK_METADATA",
                        task_id=task_id,
                        metadata={"task_name": task_name},
                    )
                )
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
