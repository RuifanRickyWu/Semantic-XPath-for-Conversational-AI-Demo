"""
Session-scoped registry wrapper.

Each session gets an independent RegistryStore instance persisted at:
storage/xml/sessions/<session_id>/registry.xml
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from common.types import RegistryApplyRequest, RegistryApplyResult
from stores.registry_store import RegistryStore
from stores.session_scope import get_current_session_id, to_safe_session_folder
from stores.xml_manager import XmlManager

_BASE_DIR = Path(__file__).resolve().parents[1]


class SessionScopedRegistryStore:
    def __init__(
        self,
        xml_manager: Optional[XmlManager] = None,
        session_root: Optional[str | Path] = None,
    ) -> None:
        self._xml_manager = xml_manager or XmlManager()
        self._stores: Dict[str, RegistryStore] = {}
        if session_root is None:
            session_root = _BASE_DIR / "storage" / "xml" / "sessions"
        self._session_root = Path(session_root)
        self._session_root.mkdir(parents=True, exist_ok=True)

    def apply(self, req: RegistryApplyRequest) -> RegistryApplyResult:
        return self._current_store().apply(req)

    def get_registry_xml(self) -> str:
        return self._current_store().get_registry_xml()

    def get_registry_schema(self) -> dict:
        return self._current_store().get_registry_schema()

    def clear_all(self) -> None:
        self._current_store().clear_all()

    def clear_session(self, session_id: str) -> None:
        sid = (session_id or "default").strip() or "default"
        store = self._stores.get(sid)
        if store is not None:
            store.clear_all()
        self._stores.pop(sid, None)
        session_dir = self._session_root / to_safe_session_folder(sid)
        if session_dir.exists():
            for child in session_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            # keep folder; task xml cleanup is handled by TaskStateStore

    def _current_store(self) -> RegistryStore:
        sid = get_current_session_id()
        store = self._stores.get(sid)
        if store is not None:
            return store

        registry_path = (
            self._session_root / to_safe_session_folder(sid) / "registry.xml"
        )
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        created = RegistryStore(
            xml_manager=self._xml_manager,
            registry_xml_path=registry_path,
        )
        self._stores[sid] = created
        return created
