from __future__ import annotations

from common.types import RegistryApplyRequest
from stores.registry_store import RegistryStore


def mk_store(tmp_path):
    return RegistryStore(registry_xml_path=tmp_path / "registry.xml")


def test_create_task_stores_default_metadata(tmp_path):
    store = mk_store(tmp_path)
    res = store.apply(RegistryApplyRequest(action="CREATE_TASK"))

    assert res.created_task_id == "t1"
    assert res.created_version_id == "v1"

    tasks = store.apply(RegistryApplyRequest(action="LIST_TASKS")).tasks or []
    assert len(tasks) == 1
    meta = tasks[0]["metadata"]
    assert meta["task_name"] is None
    assert meta["created_at"]
    assert meta["updated_at"]

    versions = store.apply(
        RegistryApplyRequest(action="LIST_VERSIONS", task_id="t1")
    ).versions or []
    assert len(versions) == 1
    assert versions[0]["metadata"]["summary"] == "Initial version"
    assert versions[0]["metadata"]["created_at"]


def test_create_task_uses_metadata(tmp_path):
    store = mk_store(tmp_path)
    store.apply(
        RegistryApplyRequest(
            action="CREATE_TASK",
            metadata={"task_name": "Paris trip", "version_summary": "Planner draft"},
        )
    )
    tasks = store.apply(RegistryApplyRequest(action="LIST_TASKS")).tasks or []
    assert tasks[0]["metadata"]["task_name"] == "Paris trip"
    versions = store.apply(
        RegistryApplyRequest(action="LIST_VERSIONS", task_id="t1")
    ).versions or []
    assert versions[0]["metadata"]["summary"] == "Planner draft"


def test_update_task_metadata_sets_name(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK"))
    store.apply(
        RegistryApplyRequest(
            action="UPDATE_TASK_METADATA",
            task_id="t1",
            metadata={"task_name": "Paris trip"},
        )
    )
    tasks = store.apply(RegistryApplyRequest(action="LIST_TASKS")).tasks or []
    assert tasks[0]["metadata"]["task_name"] == "Paris trip"


def test_update_version_metadata_sets_summary(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK"))
    store.apply(
        RegistryApplyRequest(
            action="UPDATE_VERSION_METADATA",
            task_id="t1",
            version_id="v1",
            metadata={"summary": "LLM generated summary"},
        )
    )
    versions = store.apply(
        RegistryApplyRequest(action="LIST_VERSIONS", task_id="t1")
    ).versions or []
    assert versions[0]["metadata"]["summary"] == "LLM generated summary"


def test_update_version_metadata_uses_active_task_and_version(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK"))
    store.apply(RegistryApplyRequest(action="CREATE_VERSION", task_id="t1"))
    store.apply(
        RegistryApplyRequest(
            action="UPDATE_VERSION_METADATA",
            metadata={"version_summary": "Active version summary"},
        )
    )
    versions = store.apply(
        RegistryApplyRequest(action="LIST_VERSIONS", task_id="t1")
    ).versions or []
    assert versions[-1]["version_id"] == "v2"
    assert versions[-1]["metadata"]["summary"] == "Active version summary"


def test_create_version_sets_active_and_metadata(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK"))
    res = store.apply(
        RegistryApplyRequest(
            action="CREATE_VERSION",
            task_id="t1",
            metadata={"summary": "Add museums"},
        )
    )
    assert res.created_version_id == "v2"
    assert res.active_version_id == "v2"

    versions = store.apply(
        RegistryApplyRequest(action="LIST_VERSIONS", task_id="t1")
    ).versions or []
    assert len(versions) == 2
    assert versions[-1]["version_id"] == "v2"
    assert versions[-1]["metadata"]["summary"] == "Add museums"


def test_switch_version_and_activate_task(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "A"}))
    store.apply(RegistryApplyRequest(action="CREATE_VERSION", task_id="t1"))
    store.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "B"}))

    act = store.apply(RegistryApplyRequest(action="ACTIVATE_TASK", task_id="t1"))
    assert act.active_task_id == "t1"
    assert act.active_version_id == "v2"

    sw = store.apply(
        RegistryApplyRequest(action="SWITCH_VERSION", task_id="t1", version_id="v1")
    )
    assert sw.active_task_id == "t1"
    assert sw.active_version_id == "v1"


def test_list_versions_without_task_uses_active_task(tmp_path):
    store = mk_store(tmp_path)
    store.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "One"}))
    store.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "Two"}))
    store.apply(RegistryApplyRequest(action="ACTIVATE_TASK", task_id="t1"))

    res = store.apply(RegistryApplyRequest(action="LIST_VERSIONS"))
    assert res.active_task_id == "t1"
    versions = res.versions or []
    assert len(versions) == 1
    assert versions[0]["task_id"] == "t1"


def test_registry_xml_cache_tracks_mutations(tmp_path):
    store = RegistryStore(registry_xml_path=tmp_path / "registry-cache.xml")
    store.apply(
        RegistryApplyRequest(
            action="CREATE_TASK",
            metadata={"task_name": "Trip A", "version_summary": "Draft 1"},
        )
    )
    store.apply(
        RegistryApplyRequest(
            action="UPDATE_VERSION_METADATA",
            task_id="t1",
            version_id="v1",
            metadata={"summary": "Draft updated"},
        )
    )
    xml_str = store.get_registry_xml()
    assert "<Registry>" in xml_str
    assert 'task_id="t1"' in xml_str
    assert 'task_name="Trip A"' in xml_str
    assert 'summary="Draft updated"' in xml_str


def test_registry_xml_persisted_to_disk(tmp_path):
    out = tmp_path / "registry.xml"
    store = RegistryStore(registry_xml_path=out)
    store.apply(
        RegistryApplyRequest(
            action="CREATE_TASK",
            metadata={"task_name": "Trip Persist", "version_summary": "v1"},
        )
    )
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<Registry>" in content
    assert 'task_id="t1"' in content
    assert 'task_name="Trip Persist"' in content
    assert "\n" in content
    assert "  <Tasks" in content


def test_registry_reloads_from_disk_and_continues_task_ids(tmp_path):
    out = tmp_path / "registry.xml"

    first = RegistryStore(registry_xml_path=out)
    first.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "A"}))
    first.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "B"}))

    second = RegistryStore(registry_xml_path=out)
    res = second.apply(RegistryApplyRequest(action="CREATE_TASK", metadata={"task_name": "C"}))
    assert res.created_task_id == "t3"
    assert res.active_task_id == "t3"
