"""
Mapping helpers between transport DTOs (common.types) and domain/core models.
"""

from __future__ import annotations

from common.types import (
    AddXmlNode,
    CommitResult,
    DeleteXmlNode,
    DiffSummary,
    EditXmlAttr,
    EditXmlText,
    MoveXmlNode,
    RegistryApplyResult,
    ReplaceXmlNode,
    ValidationResult,
    XmlEditResult,
    XmlOp,
    XmlState,
)
from domain.models import (
    CoreAddXmlNode,
    CoreCommitResult,
    CoreDeleteXmlNode,
    CoreEditXmlAttr,
    CoreEditXmlText,
    CoreMoveXmlNode,
    CoreRegistryResult,
    CoreReplaceXmlNode,
    CoreValidationResult,
    CoreXmlEditResult,
    CoreXmlOp,
    CoreXmlState,
)


def to_core_xml_op(op: XmlOp) -> CoreXmlOp:
    if isinstance(op, AddXmlNode):
        return CoreAddXmlNode(
            parent_xpath=op.parent_xpath,
            xml_fragment=op.xml_fragment,
            position=op.position,
        )
    if isinstance(op, DeleteXmlNode):
        return CoreDeleteXmlNode(xpath=op.xpath)
    if isinstance(op, ReplaceXmlNode):
        return CoreReplaceXmlNode(xpath=op.xpath, xml_fragment=op.xml_fragment)
    if isinstance(op, MoveXmlNode):
        return CoreMoveXmlNode(
            xpath=op.xpath,
            new_parent_xpath=op.new_parent_xpath,
            position=op.position,
        )
    if isinstance(op, EditXmlAttr):
        return CoreEditXmlAttr(
            xpath=op.xpath,
            attr_name=op.attr_name,
            new_value=op.new_value,
        )
    if isinstance(op, EditXmlText):
        return CoreEditXmlText(xpath=op.xpath, new_text=op.new_text)
    raise ValueError(f"unsupported XmlOp type: {type(op)}")


def to_core_xml_ops(ops: list[XmlOp]) -> list[CoreXmlOp]:
    return [to_core_xml_op(op) for op in ops]


def to_xml_edit_result(result: CoreXmlEditResult) -> XmlEditResult:
    return XmlEditResult(ok=result.ok, xml_str=result.xml_str, errors=result.errors)


def to_validation_result(result: CoreValidationResult) -> ValidationResult:
    return ValidationResult(ok=result.ok, errors=result.errors)


def to_commit_result(result: CoreCommitResult) -> CommitResult:
    status = "OK" if result.ok else "FAILED"
    diff = None
    if result.diff_summary:
        diff = DiffSummary(summary=result.diff_summary)
    return CommitResult(
        status=status,
        new_version_id=result.new_version_id,
        diff=diff,
        errors=result.errors,
    )


def to_xml_state(state: CoreXmlState) -> XmlState:
    return XmlState(
        task_id=state.task_id,
        version_id=state.version_id,
        schema_version=state.schema_version,
        xml_str=state.xml_str,
    )


def to_registry_apply_result(result: CoreRegistryResult) -> RegistryApplyResult:
    return RegistryApplyResult(
        active_task_id=result.active_task_id,
        active_version_id=result.active_version_id,
        tasks=result.tasks,
        versions=result.versions,
        created_task_id=result.created_task_id,
        created_version_id=result.created_version_id,
    )
