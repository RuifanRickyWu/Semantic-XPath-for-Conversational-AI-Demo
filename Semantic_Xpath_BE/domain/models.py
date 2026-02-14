"""
Core domain models independent of transport DTO wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union


@dataclass
class CoreRegistryResult:
    active_task_id: Optional[str] = None
    active_version_id: Optional[str] = None
    tasks: Optional[list[Any]] = None
    versions: Optional[list[Any]] = None
    created_task_id: Optional[str] = None
    created_version_id: Optional[str] = None


@dataclass
class CoreXmlState:
    task_id: str
    version_id: str
    schema_version: str
    xml_str: str


@dataclass
class CoreXmlEditResult:
    ok: bool
    xml_str: Optional[str] = None
    errors: Optional[list[str]] = None


@dataclass
class CoreValidationResult:
    ok: bool
    errors: Optional[list[str]] = None


@dataclass
class CoreCommitResult:
    ok: bool
    new_version_id: Optional[str] = None
    diff_summary: Optional[str] = None
    errors: Optional[list[str]] = None


@dataclass
class CoreAddXmlNode:
    parent_xpath: str
    xml_fragment: str
    position: Optional[int] = None


@dataclass
class CoreDeleteXmlNode:
    xpath: str


@dataclass
class CoreReplaceXmlNode:
    xpath: str
    xml_fragment: str


@dataclass
class CoreMoveXmlNode:
    xpath: str
    new_parent_xpath: str
    position: Optional[int] = None


@dataclass
class CoreEditXmlAttr:
    xpath: str
    attr_name: str
    new_value: Any


@dataclass
class CoreEditXmlText:
    xpath: str
    new_text: str


CoreXmlOp = Union[
    CoreAddXmlNode,
    CoreDeleteXmlNode,
    CoreReplaceXmlNode,
    CoreMoveXmlNode,
    CoreEditXmlAttr,
    CoreEditXmlText,
]
