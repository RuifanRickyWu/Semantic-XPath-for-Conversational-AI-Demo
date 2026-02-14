"""
Registry Store - In-memory task/version registry.

Manages task creation, version creation/switching, task activation,
and task/version listing with metadata.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional

from domain.models import CoreRegistryResult
from mappers.dto_mapper import to_registry_apply_result
from common.types import RegistryApplyRequest, RegistryApplyResult
from stores.xml_manager import XmlManager

_BASE_DIR = Path(__file__).resolve().parents[1]


class RegistryStore:
    """In-memory task registry with metadata on tasks and versions."""

    def __init__(
        self,
        xml_manager: Optional[XmlManager] = None,
        registry_xml_path: Optional[str | Path] = None,
    ) -> None:
        self._tasks: Dict[str, Dict[str, object]] = {}
        self._task_counter = 0
        self._active_task_id: Optional[str] = None
        self._xml_manager = xml_manager or XmlManager()
        self._registry_xml_cache = "<Registry><Tasks /></Registry>"
        if registry_xml_path is None:
            registry_xml_path = _BASE_DIR / "storage" / "xml" / "registry.xml"
        self._registry_xml_path = Path(registry_xml_path)
        self._registry_xml_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_registry_from_disk()

    def apply(self, req: RegistryApplyRequest) -> RegistryApplyResult:
        result: CoreRegistryResult
        if req.action == "CREATE_TASK":
            result = self.create_task(req.metadata or {})
        elif req.action == "CREATE_VERSION":
            result = self.create_version(req.task_id, req.metadata or {})
        elif req.action == "UPDATE_TASK_METADATA":
            result = self.update_task_metadata(req.task_id, req.metadata or {})
        elif req.action == "UPDATE_VERSION_METADATA":
            result = self.update_version_metadata(
                req.task_id, req.version_id, req.metadata or {}
            )
        elif req.action == "LIST_TASKS":
            result = CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
                tasks=self._list_tasks(),
            )
        elif req.action == "LIST_VERSIONS":
            task_id = req.task_id or self._active_task_id
            result = CoreRegistryResult(
                active_task_id=task_id,
                active_version_id=self._active_version_for(task_id),
                versions=self._list_versions(task_id),
            )
        elif req.action == "ACTIVATE_TASK":
            result = self.activate_task(req.task_id)
        elif req.action == "SWITCH_VERSION":
            result = self.switch_version(req.task_id, req.version_id)
        else:
            result = CoreRegistryResult()

        return to_registry_apply_result(result)

    def create_task(self, metadata: Dict[str, Any]) -> CoreRegistryResult:
        self._task_counter += 1
        task_id = f"t{self._task_counter}"
        version_id = "v1"
        now = self._now()

        task_name_raw = metadata.get("task_name")
        task_name = None
        if isinstance(task_name_raw, str):
            task_name = task_name_raw.strip() or None
        version_summary = (
            str(metadata.get("version_summary") or "").strip() or "Initial version"
        )
        task_meta = {
            "task_name": task_name,
            "created_at": now,
            "updated_at": now,
        }
        version_meta = {
            "summary": version_summary,
            "created_at": now,
        }
        self._tasks[task_id] = {
            "active_version_id": version_id,
            "versions": [{"version_id": version_id, "metadata": version_meta}],
            "metadata": task_meta,
        }
        self._active_task_id = task_id
        self._refresh_registry_xml_cache()
        return CoreRegistryResult(
            active_task_id=task_id,
            active_version_id=version_id,
            created_task_id=task_id,
            created_version_id=version_id,
        )

    def create_version(
        self, task_id: Optional[str], metadata: Dict[str, Any]
    ) -> CoreRegistryResult:
        if not task_id:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )
        task = self._tasks.get(task_id)
        if not task:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )

        versions = task["versions"]
        version_id = f"v{len(versions) + 1}"
        summary = str(metadata.get("summary") or metadata.get("version_summary") or "").strip()
        version_meta = {
            "summary": summary or f"Version {version_id}",
            "created_at": self._now(),
        }
        versions.append({"version_id": version_id, "metadata": version_meta})
        task["active_version_id"] = version_id
        task_meta = task["metadata"]
        task_meta["updated_at"] = self._now()
        self._active_task_id = task_id
        self._refresh_registry_xml_cache()

        return CoreRegistryResult(
            active_task_id=task_id,
            active_version_id=version_id,
            created_version_id=version_id,
        )

    def update_task_metadata(
        self, task_id: Optional[str], metadata: Dict[str, Any]
    ) -> CoreRegistryResult:
        if not task_id:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )
        task = self._tasks.get(task_id)
        if not task:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )

        task_meta = task["metadata"]
        if "task_name" in metadata:
            task_name_raw = metadata.get("task_name")
            if isinstance(task_name_raw, str):
                task_meta["task_name"] = task_name_raw.strip() or None
            elif task_name_raw is None:
                task_meta["task_name"] = None
        task_meta["updated_at"] = self._now()
        self._active_task_id = task_id
        self._refresh_registry_xml_cache()
        return CoreRegistryResult(
            active_task_id=task_id,
            active_version_id=task["active_version_id"],
        )

    def update_version_metadata(
        self,
        task_id: Optional[str],
        version_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> CoreRegistryResult:
        resolved_task_id = task_id or self._active_task_id
        if not resolved_task_id:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )

        task = self._tasks.get(resolved_task_id)
        if not task:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )

        resolved_version_id = version_id or task["active_version_id"]
        version = self._get_version(task, resolved_version_id)
        if not version:
            return CoreRegistryResult(
                active_task_id=resolved_task_id,
                active_version_id=task["active_version_id"],
            )

        version_meta = version["metadata"]
        if "summary" in metadata or "version_summary" in metadata:
            summary_raw = metadata.get("summary")
            if summary_raw is None:
                summary_raw = metadata.get("version_summary")
            if isinstance(summary_raw, str):
                version_meta["summary"] = summary_raw.strip() or None
            elif summary_raw is None:
                version_meta["summary"] = None

        task_meta = task["metadata"]
        task_meta["updated_at"] = self._now()
        self._active_task_id = resolved_task_id
        self._refresh_registry_xml_cache()
        return CoreRegistryResult(
            active_task_id=resolved_task_id,
            active_version_id=task["active_version_id"],
        )

    def activate_task(self, task_id: Optional[str]) -> CoreRegistryResult:
        if task_id and task_id in self._tasks:
            self._active_task_id = task_id
            active_version_id = self._tasks[task_id]["active_version_id"]
            self._refresh_registry_xml_cache()
            return CoreRegistryResult(
                active_task_id=task_id,
                active_version_id=active_version_id,
            )
        return CoreRegistryResult(
            active_task_id=self._active_task_id,
            active_version_id=self._active_version_for(self._active_task_id),
        )

    def switch_version(
        self, task_id: Optional[str], version_id: Optional[str]
    ) -> CoreRegistryResult:
        if not task_id or not version_id:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )
        task = self._tasks.get(task_id)
        if not task:
            return CoreRegistryResult(
                active_task_id=self._active_task_id,
                active_version_id=self._active_version_for(self._active_task_id),
            )
        if self._has_version(task, version_id):
            task["active_version_id"] = version_id
            task_meta = task["metadata"]
            task_meta["updated_at"] = self._now()
            self._active_task_id = task_id
            self._refresh_registry_xml_cache()
        return CoreRegistryResult(
            active_task_id=task_id,
            active_version_id=task["active_version_id"],
        )

    def _list_tasks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for task_id, task in sorted(self._tasks.items(), key=lambda kv: kv[0]):
            versions = task["versions"]
            out.append({
                "task_id": task_id,
                "active_version_id": task["active_version_id"],
                "version_count": len(versions),
                "is_active_task": task_id == self._active_task_id,
                "metadata": task["metadata"],
            })
        return out

    def _list_versions(self, task_id: Optional[str]) -> list[dict[str, Any]]:
        if not task_id:
            return []
        task = self._tasks.get(task_id)
        if not task:
            return []
        active_version_id = task["active_version_id"]
        versions = task["versions"]
        out: list[dict[str, Any]] = []
        for version in versions:
            version_id = version["version_id"]
            out.append({
                "task_id": task_id,
                "version_id": version_id,
                "is_active": version_id == active_version_id,
                "metadata": version["metadata"],
            })
        return out

    @staticmethod
    def _has_version(task: Dict[str, Any], version_id: str) -> bool:
        versions = task["versions"]
        for version in versions:
            if version["version_id"] == version_id:
                return True
        return False

    @staticmethod
    def _get_version(task: Dict[str, Any], version_id: str) -> Optional[Dict[str, Any]]:
        versions = task["versions"]
        for version in versions:
            if version["version_id"] == version_id:
                return version
        return None

    def _active_version_for(self, task_id: Optional[str]) -> Optional[str]:
        if not task_id:
            return None
        task = self._tasks.get(task_id)
        if not task:
            return None
        return task["active_version_id"]

    def get_registry_xml(self) -> str:
        return self._registry_xml_cache

    def _refresh_registry_xml_cache(self) -> None:
        root = ET.Element("Registry")
        tasks_node = ET.SubElement(root, "Tasks")
        if self._active_task_id:
            tasks_node.set("active_task_id", self._active_task_id)

        for task_id, task in sorted(self._tasks.items(), key=lambda kv: kv[0]):
            task_meta = task["metadata"]
            task_node = ET.SubElement(
                tasks_node,
                "Task",
                {
                    "task_id": task_id,
                    "active_version_id": str(task["active_version_id"]),
                    "task_name": str(task_meta.get("task_name") or ""),
                    "created_at": str(task_meta.get("created_at") or ""),
                    "updated_at": str(task_meta.get("updated_at") or ""),
                },
            )
            versions_node = ET.SubElement(task_node, "Versions")
            for version in task["versions"]:
                version_meta = version["metadata"]
                ET.SubElement(
                    versions_node,
                    "Version",
                    {
                        "version_id": str(version["version_id"]),
                        "summary": str(version_meta.get("summary") or ""),
                        "created_at": str(version_meta.get("created_at") or ""),
                    },
                )

        xml_str = self._xml_manager.serialize(root)
        validation = self._xml_manager.validate(xml_str)
        if validation.ok:
            self._registry_xml_cache = xml_str
            self._persist_registry_xml_cache()

    def _now(self) -> str:
        return self._xml_manager.now_iso()

    def _persist_registry_xml_cache(self) -> None:
        pretty_xml = self._format_xml_for_storage(self._registry_xml_cache)
        self._registry_xml_path.write_text(pretty_xml, encoding="utf-8")

    def _format_xml_for_storage(self, xml_str: str) -> str:
        try:
            root = ET.fromstring(xml_str)
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
            return ET.tostring(root, encoding="unicode")
        except Exception:
            return xml_str

    def _load_registry_from_disk(self) -> None:
        if not self._registry_xml_path.exists():
            return
        xml_str = self._registry_xml_path.read_text(encoding="utf-8").strip()
        if not xml_str:
            return
        validation = self._xml_manager.validate(xml_str)
        if not validation.ok:
            return

        try:
            root = ET.fromstring(xml_str)
        except Exception:
            return

        tasks_node = root.find("./Tasks")
        if tasks_node is None:
            return

        loaded_tasks: Dict[str, Dict[str, object]] = {}
        max_task_counter = 0

        for task_node in tasks_node.findall("./Task"):
            task_id = (task_node.get("task_id") or "").strip()
            if not task_id:
                continue

            task_counter = self._task_counter_from_task_id(task_id)
            if task_counter is not None and task_counter > max_task_counter:
                max_task_counter = task_counter

            task_name_raw = task_node.get("task_name")
            task_name = task_name_raw.strip() if isinstance(task_name_raw, str) else ""
            task_meta = {
                "task_name": task_name or None,
                "created_at": (task_node.get("created_at") or "").strip(),
                "updated_at": (task_node.get("updated_at") or "").strip(),
            }

            versions: list[dict[str, object]] = []
            versions_node = task_node.find("./Versions")
            if versions_node is not None:
                for version_node in versions_node.findall("./Version"):
                    version_id = (version_node.get("version_id") or "").strip()
                    if not version_id:
                        continue
                    versions.append({
                        "version_id": version_id,
                        "metadata": {
                            "summary": (version_node.get("summary") or "").strip() or None,
                            "created_at": (version_node.get("created_at") or "").strip(),
                        },
                    })

            active_version_id = (task_node.get("active_version_id") or "").strip()
            if not active_version_id and versions:
                active_version_id = str(versions[-1]["version_id"])
            if active_version_id and not any(
                str(v["version_id"]) == active_version_id for v in versions
            ):
                active_version_id = str(versions[-1]["version_id"]) if versions else ""
            if not active_version_id:
                continue

            loaded_tasks[task_id] = {
                "active_version_id": active_version_id,
                "versions": versions,
                "metadata": task_meta,
            }

        self._tasks = loaded_tasks
        self._task_counter = max_task_counter

        active_task_id = (tasks_node.get("active_task_id") or "").strip()
        if active_task_id and active_task_id in self._tasks:
            self._active_task_id = active_task_id
        elif self._tasks:
            self._active_task_id = sorted(self._tasks.keys())[0]
        else:
            self._active_task_id = None

        self._refresh_registry_xml_cache()

    @staticmethod
    def _task_counter_from_task_id(task_id: str) -> Optional[int]:
        if not task_id.startswith("t"):
            return None
        tail = task_id[1:]
        if not tail.isdigit():
            return None
        return int(tail)
