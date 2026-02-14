from __future__ import annotations

from common.types import (
    RegistryApplyRequest,
    RoutingDecision,
    SessionSnapshot,
    TaskState,
    TreeNode,
    TurnRequest,
    TurnTelemetry,
)
from services.intent_handling.intent_handling_service import IntentContext
from services.intent_handling.plan_create_service import PlanCreateService
from stores.registry_store import RegistryStore
from stores.task_state_store import TaskStateStore


class StubPlanBuilder:
    def build_initial_state(self, utterance: str, task_id: str, version_id: str, context_messages=None) -> TaskState:
        xml = "<Trip><Meta><Title>Test Trip</Title></Meta></Trip>"
        return TaskState(
            task_id=task_id,
            version_id=version_id,
            schema_version="xml/plan/v1",
            root=TreeNode(node_id="/Trip", type="Trip", text=""),
            metadata={"xml": xml, "task_name": "Test Trip"},
        )


def test_plan_create_persists_xml_to_local_storage(tmp_path):
    registry = RegistryStore(registry_xml_path=tmp_path / "registry.xml")
    svc = PlanCreateService(
        registry=registry,
        plan_builder=StubPlanBuilder(),
        state_store=TaskStateStore(storage_root=tmp_path),
    )

    req = TurnRequest(user_utterance="make a trip", session_id="s1", timestamp="now")
    routing = RoutingDecision(intent="PLAN_CREATE", registry_op=0)
    ctx = IntentContext(
        req=req,
        session=SessionSnapshot(),
        routing=routing,
        telemetry=TurnTelemetry(),
    )
    result = svc.handle(ctx)

    assert result.session_updates.active_task_id == "t1"
    assert result.session_updates.active_version_id == "v1"

    out_path = tmp_path / "t1" / "v1" / "state.xml"
    assert out_path.exists()
    assert "Test Trip" in out_path.read_text(encoding="utf-8")
    tasks = registry.apply(RegistryApplyRequest(action="LIST_TASKS")).tasks or []
    assert tasks[0]["metadata"]["task_name"] == "Test Trip"
