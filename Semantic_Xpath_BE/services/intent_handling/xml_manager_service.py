"""
XML Manager Service - XPath-based XML state operations.

Manages loading, committing, applying edit operations, and validating
XML plan state. Supports both plan XML (task/version folders) and
registry XML (single file).

Migrated from Semantic_XPath_Demo/refactor/components/xml_manager/xml_manager.py.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from common.types import (
    CommitResult,
    DiffSummary,
    ValidationResult,
    XmlEditResult,
    XmlOp,
    XmlState,
    AddXmlNode,
    DeleteXmlNode,
    ReplaceXmlNode,
    MoveXmlNode,
    EditXmlAttr,
    EditXmlText,
)


_BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass
class XmlManagerService:
    """XML manager for a single XML domain (e.g., registry XML or plan XML).

    For plan XML, each task/version folder contains state.xml:
      <storage_root>/<task_id>/<version_id>/state.xml

    For registry XML, storage_root points to the registry root, and registry_path
    points to the single registry.xml file.
    """

    storage_root: Optional[str | Path] = None
    schema_version: str = "v1"
    registry_path: Optional[str | Path] = None
    _schema_cache: Dict[str, Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.storage_root is None:
            self.storage_root = _BASE_DIR / "storage" / "xml"
        self.storage_root = Path(self.storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

        self._schema_cache = {}

        if self.registry_path is not None:
            self.registry_path = Path(self.registry_path)
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, task_id: str | None = None, version_id: str | None = None) -> XmlState:
        if self.registry_path is not None:
            if not self.registry_path.exists():
                raise FileNotFoundError(f"Registry XML not found: {self.registry_path}")
            xml_str = self.registry_path.read_text(encoding="utf-8")
            return XmlState(
                task_id=task_id or "registry",
                version_id=version_id or "current",
                schema_version=self.schema_version,
                xml_str=xml_str,
            )

        if not task_id or not version_id:
            raise ValueError("task_id and version_id are required for plan XML load")

        path = self._state_path(task_id, version_id)
        if not path.exists():
            raise FileNotFoundError(f"XML state not found: {path}")
        xml_str = path.read_text(encoding="utf-8")
        return XmlState(
            task_id=task_id,
            version_id=version_id,
            schema_version=self.schema_version,
            xml_str=xml_str,
        )

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def commit(
        self,
        task_id: str | None,
        base_version_id: str | None,
        ops: list[XmlOp],
        commit_message: str | None = None,
    ) -> CommitResult:
        if self.registry_path is None and base_version_id is None:
            return CommitResult(status="FAILED", errors=["base_version_id is required"])

        try:
            base_state = self.load(task_id, base_version_id)
        except FileNotFoundError:
            # Bootstrap case: caller supplies a full XML snapshot as root replacement
            # for the requested version path, before any base file exists.
            if (
                self.registry_path is None
                and task_id is not None
                and base_version_id is not None
                and len(ops) == 1
                and isinstance(ops[0], ReplaceXmlNode)
                and self._normalize_xpath(ops[0].xpath) == "."
            ):
                xml_str = ops[0].xml_fragment
                validation = self.validate(xml_str, schema=None)
                if not validation.ok:
                    return CommitResult(
                        status="FAILED",
                        errors=validation.errors or ["invalid xml"],
                    )
                out_path = self._state_path(task_id, base_version_id)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(xml_str, encoding="utf-8")
                return CommitResult(
                    status="OK",
                    new_version_id=base_version_id,
                    diff=DiffSummary(summary="xml_bootstrap_commit"),
                )
            return CommitResult(
                status="FAILED",
                errors=[f"base xml not found for {task_id}/{base_version_id}"],
            )

        edit_result = self.apply_ops(base_state.xml_str, ops)
        if not edit_result.ok or not edit_result.xml_str:
            return CommitResult(status="FAILED", errors=edit_result.errors or ["edit failed"])

        validation = self.validate(edit_result.xml_str, schema=None)
        if not validation.ok:
            return CommitResult(status="FAILED", errors=validation.errors)

        new_version_id = self._generate_version_id()

        if self.registry_path is not None:
            self.registry_path.write_text(edit_result.xml_str, encoding="utf-8")
        else:
            if not task_id:
                return CommitResult(status="FAILED", errors=["task_id is required"])
            out_path = self._state_path(task_id, new_version_id)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(edit_result.xml_str, encoding="utf-8")

        diff = DiffSummary(summary=f"xml_ops_applied={len(ops)}")
        return CommitResult(status="OK", new_version_id=new_version_id, diff=diff)

    # ------------------------------------------------------------------
    # Apply operations
    # ------------------------------------------------------------------

    def apply_ops(self, xml_str: str, ops: list[XmlOp]) -> XmlEditResult:
        try:
            root = ET.fromstring(xml_str)
        except Exception as exc:
            return XmlEditResult(ok=False, errors=[f"invalid xml: {exc}"])

        for op in ops:
            try:
                self._apply_op(root, op)
            except Exception as exc:
                return XmlEditResult(ok=False, errors=[str(exc)])

        return XmlEditResult(ok=True, xml_str=self._serialize(root))

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, xml_str: str, schema: str | None = None) -> ValidationResult:
        try:
            ET.fromstring(xml_str)
            return ValidationResult(ok=True)
        except Exception as exc:
            return ValidationResult(ok=False, errors=[str(exc)])

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def load_schema(self, schema_name: str) -> dict:
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]
        raise FileNotFoundError(f"Schema cache not found for: {schema_name}")

    def sync_schema(self, xml_str: str, schema_name: str) -> dict:
        schema = self._infer_schema(xml_str)
        self._schema_cache[schema_name] = schema
        return schema

    # ------------------------------------------------------------------
    # Operation dispatch
    # ------------------------------------------------------------------

    def _apply_op(self, root: ET.Element, op: XmlOp) -> None:
        parent_map = {child: parent for parent in root.iter() for child in parent}

        if isinstance(op, AddXmlNode):
            parent = self._find_node(root, op.parent_xpath)
            if parent is None:
                raise ValueError(f"parent not found for xpath: {op.parent_xpath}")
            node = ET.fromstring(op.xml_fragment)
            if op.position is None or op.position >= len(parent):
                parent.append(node)
            else:
                parent.insert(op.position, node)
            return

        if isinstance(op, DeleteXmlNode):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            parent = parent_map.get(node)
            if parent is None:
                raise ValueError("cannot delete root node")
            parent.remove(node)
            return

        if isinstance(op, ReplaceXmlNode):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            parent = parent_map.get(node)
            if parent is None:
                raise ValueError("cannot replace root node")
            new_node = ET.fromstring(op.xml_fragment)
            idx = list(parent).index(node)
            parent.remove(node)
            parent.insert(idx, new_node)
            return

        if isinstance(op, MoveXmlNode):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            new_parent = self._find_node(root, op.new_parent_xpath)
            if new_parent is None:
                raise ValueError(f"new parent not found: {op.new_parent_xpath}")
            old_parent = parent_map.get(node)
            if old_parent is None:
                raise ValueError("cannot move root node")
            old_parent.remove(node)
            if op.position is None or op.position >= len(new_parent):
                new_parent.append(node)
            else:
                new_parent.insert(op.position, node)
            return

        if isinstance(op, EditXmlAttr):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            node.set(op.attr_name, str(op.new_value))
            return

        if isinstance(op, EditXmlText):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            node.text = str(op.new_text)
            return

        raise ValueError(f"unsupported op: {op}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_node(self, root: ET.Element, xpath: str) -> Optional[ET.Element]:
        normalized = self._normalize_xpath(xpath)
        return root.find(normalized)

    def _normalize_xpath(self, xpath: str) -> str:
        path = (xpath or "").strip()
        if not path:
            return "."
        if path.startswith("/"):
            return "." + path
        if path.startswith("."):
            return path
        return ".//" + path

    def _serialize(self, root: ET.Element) -> str:
        return ET.tostring(root, encoding="unicode")

    def _state_path(self, task_id: str, version_id: str) -> Path:
        return self.storage_root / task_id / version_id / "state.xml"

    def _generate_version_id(self) -> str:
        return f"v{int(time.time() * 1000)}"

    def _infer_schema(self, xml_str: str) -> dict:
        root = ET.fromstring(xml_str)
        node_types: Set[str] = set()
        attributes: Dict[str, Set[str]] = {}
        children: Dict[str, Set[str]] = {}
        paths: Set[str] = set()

        def walk(node: ET.Element, path: List[str]) -> None:
            tag = node.tag
            node_types.add(tag)
            if tag not in attributes:
                attributes[tag] = set()
            for k in node.attrib.keys():
                attributes[tag].add(k)

            current_path = path + [tag]
            paths.add("/" + "/".join(current_path))

            if tag not in children:
                children[tag] = set()
            for child in list(node):
                children[tag].add(child.tag)
                walk(child, current_path)

        walk(root, [])

        return {
            "root": root.tag,
            "node_types": sorted(node_types),
            "attributes": {k: sorted(v) for k, v in attributes.items()},
            "children": {k: sorted(v) for k, v in children.items()},
            "paths": sorted(paths),
        }
