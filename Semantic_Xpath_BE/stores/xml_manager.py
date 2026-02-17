"""
XML Manager - shared XML utilities for stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Set

from stores.xml_utils import find_by_path_segments
from domain.models import (
    CoreAddXmlNode,
    CoreDeleteXmlNode,
    CoreEditXmlAttr,
    CoreEditXmlText,
    CoreMoveXmlNode,
    CoreReplaceXmlNode,
    CoreValidationResult,
    CoreXmlEditResult,
    CoreXmlOp,
)
from mappers.dto_mapper import to_core_xml_ops, to_validation_result, to_xml_edit_result
from common.types import (
    ValidationResult,
    XmlEditResult,
    XmlOp,
)


class XmlManager:
    """Centralized XML operations, validation, and schema sync."""

    def __init__(self) -> None:
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def apply_ops_core(self, xml_str: str, ops: list[CoreXmlOp]) -> CoreXmlEditResult:
        try:
            root = ET.fromstring(xml_str)
        except Exception as exc:
            return CoreXmlEditResult(ok=False, errors=[f"invalid xml: {exc}"])

        for op in ops:
            try:
                self._apply_op(root, op)
            except Exception as exc:
                return CoreXmlEditResult(ok=False, errors=[str(exc)])

        return CoreXmlEditResult(ok=True, xml_str=self.serialize(root))

    def apply_ops(self, xml_str: str, ops: list[XmlOp]) -> XmlEditResult:
        result = self.apply_ops_core(xml_str, to_core_xml_ops(ops))
        return to_xml_edit_result(result)

    def validate_core(
        self, xml_str: str, schema: str | None = None
    ) -> CoreValidationResult:
        del schema
        try:
            ET.fromstring(xml_str)
            return CoreValidationResult(ok=True)
        except Exception as exc:
            return CoreValidationResult(ok=False, errors=[str(exc)])

    def validate(self, xml_str: str, schema: str | None = None) -> ValidationResult:
        result = self.validate_core(xml_str, schema=schema)
        return to_validation_result(result)

    def load_schema(self, schema_name: str) -> dict:
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]
        raise FileNotFoundError(f"Schema cache not found for: {schema_name}")

    def sync_schema(self, xml_str: str, schema_name: str) -> dict:
        schema = self._infer_schema(xml_str)
        self._schema_cache[schema_name] = schema
        return schema

    def parse(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def serialize(self, root: ET.Element) -> str:
        return ET.tostring(root, encoding="unicode")

    def normalize_xpath(self, xpath: str) -> str:
        return self._normalize_xpath(xpath)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _apply_op(self, root: ET.Element, op: CoreXmlOp) -> None:
        parent_map = {child: parent for parent in root.iter() for child in parent}

        if isinstance(op, CoreAddXmlNode):
            parent = self._find_node(root, op.parent_xpath)
            if parent is None:
                raise ValueError(f"parent not found for xpath: {op.parent_xpath}")
            node = ET.fromstring(op.xml_fragment)
            if op.position is None or op.position >= len(parent):
                parent.append(node)
            else:
                parent.insert(op.position, node)
            return

        if isinstance(op, CoreDeleteXmlNode):
            node = (
                find_by_path_segments(root, op.path_segments)
                if op.path_segments
                else self._find_node(root, op.xpath)
            )
            if node is None:
                raise ValueError(
                    f"node not found for path_segments={op.path_segments!r} or xpath={op.xpath!r}"
                )
            parent = parent_map.get(node)
            if parent is None:
                raise ValueError("cannot delete root node")
            parent.remove(node)
            return

        if isinstance(op, CoreReplaceXmlNode):
            if op.path_segments is not None:
                node = find_by_path_segments(root, op.path_segments)
            else:
                node = self._find_node(root, op.xpath or ".")
            if node is None:
                raise ValueError(
                    f"node not found for path_segments={op.path_segments!r} or xpath={op.xpath!r}"
                )
            parent = parent_map.get(node)
            if parent is None:
                new_root_elem = ET.fromstring(op.xml_fragment)
                root.clear()
                root.tag = new_root_elem.tag
                root.attrib = dict(new_root_elem.attrib)
                for child in new_root_elem:
                    root.append(child)
                root.text = new_root_elem.text
                root.tail = new_root_elem.tail
                return
            new_node = ET.fromstring(op.xml_fragment)
            idx = list(parent).index(node)
            parent.remove(node)
            parent.insert(idx, new_node)
            return

        if isinstance(op, CoreMoveXmlNode):
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

        if isinstance(op, CoreEditXmlAttr):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            node.set(op.attr_name, str(op.new_value))
            return

        if isinstance(op, CoreEditXmlText):
            node = self._find_node(root, op.xpath)
            if node is None:
                raise ValueError(f"node not found for xpath: {op.xpath}")
            node.text = str(op.new_text)
            return

        raise ValueError(f"unsupported op: {op}")

    def _find_node(self, root: ET.Element, xpath: str) -> Optional[ET.Element]:
        normalized = self._normalize_xpath(xpath)
        return root.find(normalized)

    @staticmethod
    def _normalize_xpath(xpath: str) -> str:
        path = (xpath or "").strip()
        if not path:
            return "."
        if path.startswith("/"):
            return "." + path
        if path.startswith("."):
            return path
        return ".//" + path

    def _infer_schema(self, xml_str: str) -> dict:
        root = ET.fromstring(xml_str)
        node_types: Set[str] = set()
        attributes: Dict[str, Set[str]] = {}
        children: Dict[str, Set[str]] = {}
        paths: Set[str] = set()

        def walk(node: ET.Element, path: list[str]) -> None:
            tag = node.tag
            node_types.add(tag)
            if tag not in attributes:
                attributes[tag] = set()
            for key in node.attrib.keys():
                attributes[tag].add(key)

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
