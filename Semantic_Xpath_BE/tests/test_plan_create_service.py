from __future__ import annotations

from common.types import RoutingDecision, TaskState, TreeNode, TurnRequest
from services.intent_handling.plan_create_service import PlanCreateService
from services.intent_handling.xml_manager_service import XmlManagerService
from stores.registry_store import RegistryStore


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
    svc = PlanCreateService(
        registry=RegistryStore(),
        plan_builder=StubPlanBuilder(),
        xml_state_manager=XmlManagerService(storage_root=tmp_path),
    )

    req = TurnRequest(user_utterance="make a trip", session_id="s1", timestamp="now")
    routing = RoutingDecision(intent="PLAN_CREATE", registry_op=0)
    result = svc.handle(req, routing)

    assert result.session_updates.active_task_id == "t1"
    assert result.session_updates.active_version_id == "v1"

    out_path = tmp_path / "t1" / "v1" / "state.xml"
    assert out_path.exists()
    assert "Test Trip" in out_path.read_text(encoding="utf-8")
