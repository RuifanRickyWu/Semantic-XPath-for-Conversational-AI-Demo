"""
Task State Store - filesystem-backed XML state persistence + XML edit utilities.

Stores plan XML snapshots in:
`storage/xml/<task_id>/<version_id>/state.xml`

When registry_store is provided, new versions from plan edits are created via the
registry (CREATE_VERSION) so registry.xml stays in sync.
"""

from __future__ import annotations

import shutil
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from stores.registry_store import RegistryStore

from common.types import (
    CommitResult,
    RegistryApplyRequest,
    ValidationResult,
    XmlEditResult,
    XmlOp,
    XmlState,
)
from domain.models import (
    CoreCommitResult,
    CoreReplaceXmlNode,
    CoreValidationResult,
    CoreXmlEditResult,
    CoreXmlOp,
    CoreXmlState,
)
from mappers.dto_mapper import (
    to_commit_result,
    to_core_xml_ops,
    to_validation_result,
    to_xml_edit_result,
    to_xml_state,
)
from stores.xml_manager import XmlManager


_BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass
class TaskStateStore:
    """Task state store for plan XML persistence."""

    storage_root: Optional[str | Path] = None
    schema_version: str = "v1"
    xml_manager: Optional[XmlManager] = None
    registry_store: Optional["RegistryStore"] = None

    def __post_init__(self) -> None:
        if self.storage_root is None:
            self.storage_root = _BASE_DIR / "storage" / "xml"
        self.storage_root = Path(self.storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

        if self.xml_manager is None:
            self.xml_manager = XmlManager()

    def load(self, task_id: str, version_id: str) -> XmlState:
        state = self.load_core(task_id, version_id)
        return to_xml_state(state)

    def load_core(self, task_id: str, version_id: str) -> CoreXmlState:
        if not task_id or not version_id:
            raise ValueError("task_id and version_id are required")

        path = self._state_path(task_id, version_id)
        if not path.exists():
            raise FileNotFoundError(f"XML state not found: {path}")
        xml_str = path.read_text(encoding="utf-8")
        return CoreXmlState(
            task_id=task_id,
            version_id=version_id,
            schema_version=self.schema_version,
            xml_str=xml_str,
        )

    def commit(
        self,
        task_id: str,
        base_version_id: str,
        ops: list[XmlOp],
        commit_message: str | None = None,
    ) -> CommitResult:
        core_result = self.commit_core(
            task_id=task_id,
            base_version_id=base_version_id,
            ops=to_core_xml_ops(ops),
            commit_message=commit_message,
        )
        return to_commit_result(core_result)

    def commit_core(
        self,
        task_id: str,
        base_version_id: str,
        ops: list[CoreXmlOp],
        commit_message: str | None = None,
    ) -> CoreCommitResult:
        if not task_id or not base_version_id:
            return CoreCommitResult(
                ok=False,
                errors=["task_id and base_version_id are required"],
            )

        try:
            base_state = self.load_core(task_id, base_version_id)
        except FileNotFoundError:
            if (
                len(ops) == 1
                and isinstance(ops[0], CoreReplaceXmlNode)
                and self._normalize_xpath(ops[0].xpath) == "."
            ):
                xml_str = ops[0].xml_fragment
                validation = self.validate_core(xml_str, schema=None)
                if not validation.ok:
                    return CoreCommitResult(
                        ok=False,
                        errors=validation.errors or ["invalid xml"],
                    )
                xml_to_write = self._set_plan_version(xml_str, base_version_id)
                out_path = self._state_path(task_id, base_version_id)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(xml_to_write, encoding="utf-8")
                return CoreCommitResult(
                    ok=True,
                    new_version_id=base_version_id,
                    diff_summary="xml_bootstrap_commit",
                )
            return CoreCommitResult(
                ok=False,
                errors=[f"base xml not found for {task_id}/{base_version_id}"],
            )

        edit_result = self.xml_manager.apply_ops_core(base_state.xml_str, ops)
        if not edit_result.ok or not edit_result.xml_str:
            return CoreCommitResult(
                ok=False,
                errors=edit_result.errors or ["edit failed"],
            )

        validation = self.xml_manager.validate_core(edit_result.xml_str, schema=None)
        if not validation.ok:
            return CoreCommitResult(ok=False, errors=validation.errors)

        new_version_id = self._create_new_version_in_registry(task_id, commit_message)
        xml_to_write = self._set_plan_version(edit_result.xml_str, new_version_id)
        out_path = self._state_path(task_id, new_version_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml_to_write, encoding="utf-8")

        return CoreCommitResult(
            ok=True,
            new_version_id=new_version_id,
            diff_summary=f"xml_ops_applied={len(ops)}",
        )

    def apply_ops(self, xml_str: str, ops: list[XmlOp]) -> XmlEditResult:
        result = self.apply_ops_core(xml_str, to_core_xml_ops(ops))
        return to_xml_edit_result(result)

    def apply_ops_core(self, xml_str: str, ops: list[CoreXmlOp]) -> CoreXmlEditResult:
        return self.xml_manager.apply_ops_core(xml_str, ops)

    def validate(self, xml_str: str, schema: str | None = None) -> ValidationResult:
        result = self.validate_core(xml_str, schema=schema)
        return to_validation_result(result)

    def validate_core(
        self, xml_str: str, schema: str | None = None
    ) -> CoreValidationResult:
        return self.xml_manager.validate_core(xml_str, schema=schema)

    def load_schema(self, schema_name: str) -> dict:
        return self.xml_manager.load_schema(schema_name)

    def sync_schema(self, xml_str: str, schema_name: str) -> dict:
        return self.xml_manager.sync_schema(xml_str, schema_name)

    def _normalize_xpath(self, xpath: str) -> str:
        return self.xml_manager.normalize_xpath(xpath)

    def _state_path(self, task_id: str, version_id: str) -> Path:
        return self.storage_root / task_id / version_id / "state.xml"

    def clear_all_task_data(self) -> None:
        """Delete all task directories (and their state.xml files) under storage_root."""
        if not self.storage_root.exists():
            return
        for item in self.storage_root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                shutil.rmtree(item, ignore_errors=True)

    def _set_plan_version(self, xml_str: str, version_id: str) -> str:
        """Set the root Plan element's version attribute to version_id."""
        try:
            root = ET.fromstring(xml_str)
            root.set("version", version_id)
            return ET.tostring(root, encoding="unicode")
        except Exception:
            return xml_str

    def _create_new_version_in_registry(
        self, task_id: str, commit_message: Optional[str] = None
    ) -> str:
        """Create a new version in the registry and return its ID. Falls back to timestamp if no registry."""
        registry = self.registry_store
        if registry is not None:
            try:
                result = registry.apply(
                    RegistryApplyRequest(
                        action="CREATE_VERSION",
                        task_id=task_id,
                        metadata={"summary": commit_message or "plan edit"},
                    )
                )
                created = getattr(result, "created_version_id", None)
                if created:
                    return created
            except Exception:
                pass
        return self._generate_version_id()

    def _generate_version_id(self) -> str:
        return f"v{int(time.time() * 1000)}"
