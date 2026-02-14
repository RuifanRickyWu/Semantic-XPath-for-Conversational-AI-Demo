"""
Tests for XmlManagerService.

Adapted from Semantic_XPath_Demo/refactor/tests/test_xml_manager.py.
Uses pytest tmp_path for isolated test storage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.intent_handling.xml_manager_service import XmlManagerService
from common.types import (
    AddXmlNode,
    DeleteXmlNode,
    ReplaceXmlNode,
    MoveXmlNode,
    EditXmlAttr,
    EditXmlText,
)


def sample_xml() -> str:
    return (
        "<Trip>"
        "<Day id='1'>"
        "<Block id='morning'><Item id='museum'>Visit museum</Item></Block>"
        "</Day>"
        "<Day id='2'>"
        "<Block id='afternoon'><Item id='park'>Walk in park</Item></Block>"
        "</Day>"
        "</Trip>"
    )


def mgr(tmp_path: Path) -> XmlManagerService:
    return XmlManagerService(storage_root=tmp_path)


def write_base(root: Path, task_id: str, version_id: str, xml: str) -> Path:
    path = root / task_id / version_id / "state.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# apply_ops tests
# ---------------------------------------------------------------------------

def test_apply_ops_basic(tmp_path):
    m = mgr(tmp_path)
    ops = [
        EditXmlText(xpath=".//Item[@id='museum']", new_text="Visit art museum"),
        EditXmlAttr(xpath=".//Day[@id='1']", attr_name="theme", new_value="culture"),
        AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='evening'/>"),
        MoveXmlNode(xpath=".//Block[@id='afternoon']", new_parent_xpath=".//Day[@id='1']"),
        ReplaceXmlNode(xpath=".//Item[@id='park']", xml_fragment="<Item id='lake'>Boat on lake</Item>"),
        DeleteXmlNode(xpath=".//Block[@id='morning']"),
    ]
    res = m.apply_ops(sample_xml(), ops)
    assert res.ok, f"apply_ops failed: {res.errors}"
    out = res.xml_str or ""
    assert "theme" in out
    assert "evening" in out
    assert "lake" in out
    assert "morning" not in out


def test_apply_ops_invalid_xml(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops("<Trip><Day></Trip>", [])
    assert not res.ok


def test_add_node_invalid_parent(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Nope", xml_fragment="<X/>")])
    assert not res.ok


def test_delete_missing_node(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [DeleteXmlNode(xpath=".//Missing")])
    assert not res.ok


def test_replace_missing_node(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [ReplaceXmlNode(xpath=".//Missing", xml_fragment="<X/>")])
    assert not res.ok


def test_move_missing_node(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(
        sample_xml(),
        [MoveXmlNode(xpath=".//Missing", new_parent_xpath=".//Day[@id='1']")],
    )
    assert not res.ok


def test_edit_attr_missing_node(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(
        sample_xml(),
        [EditXmlAttr(xpath=".//Missing", attr_name="x", new_value="y")],
    )
    assert not res.ok


def test_edit_text_missing_node(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(
        sample_xml(),
        [EditXmlText(xpath=".//Missing", new_text="x")],
    )
    assert not res.ok


def test_add_node_append_position_none(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='x'/>")])
    assert res.ok


def test_add_node_insert_position0(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='x'/>", position=0)])
    assert res.ok


def test_add_node_insert_middle(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='x'/>", position=1)])
    assert res.ok


def test_move_node_append_default(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [MoveXmlNode(xpath=".//Block[@id='afternoon']", new_parent_xpath=".//Day[@id='1']")])
    assert res.ok


def test_move_node_insert_position0(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [MoveXmlNode(xpath=".//Block[@id='afternoon']", new_parent_xpath=".//Day[@id='1']", position=0)])
    assert res.ok


def test_replace_node_preserves_order(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [ReplaceXmlNode(xpath=".//Item[@id='park']", xml_fragment="<Item id='park2'>X</Item>")])
    assert res.ok


def test_delete_node_removes(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [DeleteXmlNode(xpath=".//Item[@id='park']")])
    assert res.ok
    assert "park" not in (res.xml_str or "")


def test_edit_attr_string_value(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlAttr(xpath=".//Day[@id='1']", attr_name="note", new_value="hello")])
    assert res.ok


def test_edit_attr_numeric_value(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlAttr(xpath=".//Day[@id='1']", attr_name="n", new_value=7)])
    assert res.ok


def test_edit_text_numeric_value(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlText(xpath=".//Item[@id='museum']", new_text=123)])
    assert res.ok


def test_edit_text_empty(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlText(xpath=".//Item[@id='museum']", new_text="")])
    assert res.ok


def test_move_root_fails(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [MoveXmlNode(xpath=".", new_parent_xpath=".//Day[@id='1']")])
    assert not res.ok


def test_delete_root_fails(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [DeleteXmlNode(xpath=".")])
    assert not res.ok


def test_replace_root_fails(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [ReplaceXmlNode(xpath=".", xml_fragment="<X/>")])
    assert not res.ok


def test_add_node_with_nested_children(tmp_path):
    m = mgr(tmp_path)
    frag = "<Block id='evening'><Item id='dinner'>Dinner</Item></Block>"
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='2']", xml_fragment=frag)])
    assert res.ok


def test_add_node_double_slash_xpath(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath="Day[@id='1']", xml_fragment="<Block id='x'/>")])
    assert res.ok


def test_add_node_relative_xpath(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='2']", xml_fragment="<Block id='x'/>")])
    assert res.ok


def test_add_node_root_xpath_dot(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".", xml_fragment="<Meta/>")])
    assert res.ok


def test_edit_text_no_prefix_xpath(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlText(xpath="Item[@id='museum']", new_text="X")])
    assert res.ok


def test_edit_attr_with_slash_path(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlAttr(xpath="./Day[@id='1']", attr_name="k", new_value="v")])
    assert res.ok


def test_move_node_new_parent_missing(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [MoveXmlNode(xpath=".//Block[@id='afternoon']", new_parent_xpath=".//Missing")])
    assert not res.ok


def test_add_node_position_out_of_range_append(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='x'/>", position=99)])
    assert res.ok


def test_multiple_ops_sequence(tmp_path):
    m = mgr(tmp_path)
    ops = [
        AddXmlNode(parent_xpath=".", xml_fragment="<Meta/>"),
        EditXmlText(xpath=".//Item[@id='museum']", new_text="A"),
        DeleteXmlNode(xpath=".//Item[@id='park']"),
    ]
    res = m.apply_ops(sample_xml(), ops)
    assert res.ok


def test_add_node_empty_xpath(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [AddXmlNode(parent_xpath="", xml_fragment="<Meta/>")])
    assert res.ok


def test_edit_attr_on_root(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlAttr(xpath=".", attr_name="x", new_value="y")])
    assert res.ok


def test_edit_text_on_root(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlText(xpath=".", new_text="X")])
    assert res.ok


def test_apply_ops_whitespace_xpath(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(sample_xml(), [EditXmlText(xpath="  .//Item[@id='museum']  ", new_text="X")])
    assert res.ok


def test_move_node_position_out_of_range_append(tmp_path):
    m = mgr(tmp_path)
    res = m.apply_ops(
        sample_xml(),
        [MoveXmlNode(xpath=".//Block[@id='afternoon']", new_parent_xpath=".//Day[@id='1']", position=999)],
    )
    assert res.ok


def test_add_node_then_edit_text(tmp_path):
    m = mgr(tmp_path)
    ops = [
        AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='x'><Item id='y'>Z</Item></Block>"),
        EditXmlText(xpath=".//Item[@id='y']", new_text="Y"),
    ]
    res = m.apply_ops(sample_xml(), ops)
    assert res.ok


def test_replace_then_edit_attr(tmp_path):
    m = mgr(tmp_path)
    ops = [
        ReplaceXmlNode(xpath=".//Item[@id='park']", xml_fragment="<Item id='park'>P</Item>"),
        EditXmlAttr(xpath=".//Item[@id='park']", attr_name="k", new_value="v"),
    ]
    res = m.apply_ops(sample_xml(), ops)
    assert res.ok


def test_delete_then_add_same_xpath(tmp_path):
    m = mgr(tmp_path)
    ops = [
        DeleteXmlNode(xpath=".//Block[@id='morning']"),
        AddXmlNode(parent_xpath=".//Day[@id='1']", xml_fragment="<Block id='morning'/>"),
    ]
    res = m.apply_ops(sample_xml(), ops)
    assert res.ok


# ---------------------------------------------------------------------------
# commit / load tests
# ---------------------------------------------------------------------------

def test_commit_and_load(tmp_path):
    m = mgr(tmp_path)
    write_base(tmp_path, "t1", "v0", sample_xml())
    ops = [EditXmlText(xpath=".//Item[@id='museum']", new_text="Museum visit")]
    commit = m.commit(task_id="t1", base_version_id="v0", ops=ops)
    assert commit.status == "OK"
    assert commit.new_version_id is not None
    state = m.load("t1", commit.new_version_id)
    assert "Museum visit" in state.xml_str


def test_commit_creates_new_version_folder(tmp_path):
    m = mgr(tmp_path)
    write_base(tmp_path, "t1", "v0", sample_xml())
    commit = m.commit(task_id="t1", base_version_id="v0", ops=[])
    assert commit.status == "OK"
    out_path = tmp_path / "t1" / commit.new_version_id / "state.xml"
    assert out_path.exists()


def test_commit_diff_summary(tmp_path):
    m = mgr(tmp_path)
    write_base(tmp_path, "t2", "v0", sample_xml())
    commit = m.commit(task_id="t2", base_version_id="v0", ops=[])
    assert commit.diff is not None


def test_commit_missing_base_version(tmp_path):
    m = mgr(tmp_path)
    commit = m.commit(task_id="t_missing", base_version_id=None, ops=[])
    assert commit.status == "FAILED"


def test_commit_plan_missing_task_id(tmp_path):
    m = mgr(tmp_path)
    write_base(tmp_path, "t1", "v0", sample_xml())
    with pytest.raises(ValueError):
        m.commit(None, "v0", [])


def test_load_missing_file_raises(tmp_path):
    m = mgr(tmp_path)
    with pytest.raises(FileNotFoundError):
        m.load("t_missing", "v_missing")


# ---------------------------------------------------------------------------
# validate tests
# ---------------------------------------------------------------------------

def test_validate_invalid_xml(tmp_path):
    m = mgr(tmp_path)
    res = m.validate("<Trip><Day></Trip>")
    assert not res.ok


def test_validate_valid_xml(tmp_path):
    m = mgr(tmp_path)
    res = m.validate(sample_xml())
    assert res.ok


# ---------------------------------------------------------------------------
# schema tests
# ---------------------------------------------------------------------------

def test_schema_load_and_sync(tmp_path):
    m = mgr(tmp_path)
    schema = m.sync_schema(sample_xml(), "trip")
    assert schema.get("root") == "Trip"
    loaded = m.load_schema("trip")
    assert loaded.get("root") == "Trip"


def test_schema_cache_isolated_by_name(tmp_path):
    m = mgr(tmp_path)
    m.sync_schema(sample_xml(), "trip")
    m.sync_schema("<A><B/></A>", "simple")
    assert m.load_schema("trip").get("root") == "Trip"
    assert m.load_schema("simple").get("root") == "A"


def test_load_schema_missing_raises(tmp_path):
    m = mgr(tmp_path)
    with pytest.raises(FileNotFoundError):
        m.load_schema("missing")


# ---------------------------------------------------------------------------
# registry mode tests
# ---------------------------------------------------------------------------

def test_registry_mode_commit_and_load(tmp_path):
    registry_path = tmp_path / "registry.xml"
    registry_path.write_text("<Registry></Registry>", encoding="utf-8")
    m = XmlManagerService(registry_path=registry_path)
    ops = [AddXmlNode(parent_xpath=".", xml_fragment="<Task id='t1' />")]
    commit = m.commit(task_id=None, base_version_id=None, ops=ops)
    assert commit.status == "OK"
    state = m.load()
    assert "t1" in state.xml_str


def test_registry_load_defaults_task_version(tmp_path):
    registry_path = tmp_path / "registry.xml"
    registry_path.write_text("<Registry></Registry>", encoding="utf-8")
    m = XmlManagerService(registry_path=registry_path)
    state = m.load()
    assert state.task_id == "registry"
    assert state.version_id == "current"


def test_load_registry_missing_raises(tmp_path):
    registry_path = tmp_path / "nonexistent" / "registry.xml"
    m = XmlManagerService(registry_path=registry_path)
    with pytest.raises(FileNotFoundError):
        m.load()


def test_commit_registry_ignores_task_version(tmp_path):
    registry_path = tmp_path / "registry.xml"
    registry_path.write_text("<Registry />", encoding="utf-8")
    m = XmlManagerService(registry_path=registry_path)
    commit = m.commit(task_id="anything", base_version_id="v0", ops=[])
    assert commit.status == "OK"
