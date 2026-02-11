"""
Global Info Resolver - resolves global task/version numbers and manages state.
Combines selection with a needs_data flag for early exits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import xml.etree.ElementTree as ET

from pipeline_execution.task_version_resolver.version_selector_model import ResolvedVersion, VersionSelector, CRUDOperation
from pipeline_execution.semantic_xpath_execution import DenseXPathExecutor
from client import get_default_client
from pipeline_execution.semantic_xpath_execution import get_schema_summary_for_prompt
from pipeline_execution.semantic_xpath_util.schema_loader import load_schema
from pipeline_execution.crud.read_handler import ReadHandler
from pipeline_execution.crud.delete_handler import DeleteHandler
from pipeline_execution.crud.update_handler import UpdateHandler
from pipeline_execution.crud.create_handler import CreateHandler
from utils.tree_modification.base import find_node_by_path


import re

class GlobalInfoResolver:
    RESPONSE_PATTERN = re.compile(
        r'task\s*\(\s*(.+?)\s*\)\s*,\s*version\s*\(\s*(.+?)\s*\)\s*,\s*'
        r'(READ|CREATE|UPDATE|DELETE|STATE)',
        re.IGNORECASE
    )
    TASK_PATTERN = re.compile(r'task:\s*(.+)', re.IGNORECASE)
    SELECTOR_PATTERN = re.compile(
        r'^(at|before)\s*\(\s*(.+?)\s*\)$',
        re.IGNORECASE
    )
    INDEX_ONLY_PATTERN = re.compile(r'^\[\s*(-?\d+)\s*\]\s*$')
    NUMBER_ONLY_PATTERN = re.compile(r'^-?\d+\s*$')
    NEGATIVE_I_PATTERN = re.compile(r'^-i$', re.IGNORECASE)
    BRACKET_NEGATIVE_I_PATTERN = re.compile(r'^\[\s*-\s*i\s*\]\s*$', re.IGNORECASE)
    NODE_INDEX_PATTERN = re.compile(r'^(?:/|//)?(Task|Version)\s*\[\s*(-?\d+)\s*\]\s*$', re.IGNORECASE)
    NODE_NEGATIVE_I_PATTERN = re.compile(r'^(?:/|//)?(Task|Version)\s*\[\s*-\s*i\s*\]\s*$', re.IGNORECASE)
    NODE_ATOM_PATTERN = re.compile(
        r"^(?:/|//)?(Task|Version)\s*\[\s*atom\s*\(\s*content\s*~=\s*[\"']([^\"']+)[\"']\s*\)\s*\]\s*$",
        re.IGNORECASE
    )

    
    def __init__(
        self,
        executor: DenseXPathExecutor,
        task_schema_dir: Path,
        task_memory_dir: Path,
        global_memory_path: Path,
        traces_path: Optional[Path] = None,
        schema_name: Optional[str] = None,
        client=None,
    ):
        self.executor = executor
        self._task_schema_dir = task_schema_dir
        self._task_memory_dir = task_memory_dir
        self._global_memory_path = global_memory_path
        self._traces_path = traces_path
        self._schema_name = schema_name
        self._client = client
        self._system_prompt = None

        self._task_schema_name: Optional[str] = None
        self._state_task_index: Optional[int] = None
        self._state_version_index: Optional[int] = None
        self._tree: Optional[ET.ElementTree] = None
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._task_schema_cache: Dict[int, str] = {}

        # Handlers and query generator initialized by caller
        self.query_generator: Optional[object] = None
        self.read_handler: Optional[ReadHandler] = None
        self.delete_handler: Optional[DeleteHandler] = None
        self.update_handler: Optional[UpdateHandler] = None
        self.create_handler: Optional[CreateHandler] = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_default_client()
        return self._client

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            base_dir = Path(__file__).resolve().parents[2]
            prompt_path = base_dir / "storage" / "prompts" / "query_generator" / "version_resolver.txt"
            template = prompt_path.read_text(encoding="utf-8")
            grammar_path = prompt_path.parent / "xpath_grammar.txt"
            grammar = grammar_path.read_text(encoding="utf-8").strip() if grammar_path.exists() else ""
            schema_summary = ""
            try:
                schema_summary = get_schema_summary_for_prompt(self._schema_name)
            except Exception:
                schema_summary = ""
            self._system_prompt = template.format(grammar=grammar, schema=schema_summary, schema_name=self._schema_name)
        return self._system_prompt

    def resolve(self, user_query: str) -> ResolvedVersion:
        prompt = f"User: {user_query}"
        result = self.client.complete_with_usage(
            prompt,
            system_prompt=self.system_prompt,
        )
        raw = (result.content or "").strip()
        if raw.lower().startswith("output:"):
            raw = raw[7:].strip()
        resolved = self._parse_response(raw, user_query)
        resolved.token_usage = result.usage.to_dict() if result.usage else None
        return resolved


    def _parse_response(self, response: str, original_query: str) -> ResolvedVersion:
        match = self.RESPONSE_PATTERN.search(response)
        task_match = self.TASK_PATTERN.search(response)
        task_query = task_match.group(1).strip() if task_match else original_query

        task_selector_raw = None
        version_selector_raw = None
        crud_str = None

        if match:
            task_selector_raw = match.group(1).strip()
            version_selector_raw = match.group(2).strip()
            crud_str = match.group(3).upper()
        else:
            lines = [ln.strip() for ln in response.splitlines() if ln.strip()]
            for line in lines:
                lower = line.lower()
                if lower.startswith("task selector:"):
                    task_selector_raw = line.split(":", 1)[1].strip()
                elif lower.startswith("version selector:"):
                    version_selector_raw = line.split(":", 1)[1].strip()
                elif lower.startswith("operation:"):
                    crud_str = line.split(":", 1)[1].strip().upper()
                elif lower in ("read", "create", "update", "delete", "state"):
                    crud_str = line.upper()
                elif lower.startswith("task("):
                    task_selector_raw = line
                elif lower.startswith("version("):
                    version_selector_raw = line

            if task_selector_raw and task_selector_raw.lower().startswith("task("):
                task_selector_raw = task_selector_raw[len("task("):-1].strip()
            if version_selector_raw and version_selector_raw.lower().startswith("version("):
                version_selector_raw = version_selector_raw[len("version("):-1].strip()

        task_selector_type = VersionSelector.AT
        version_selector_type = VersionSelector.AT
        task_index = None
        task_semantic_query = None
        index = None
        semantic_query = None

        if task_selector_raw and task_selector_raw.lower() != "none":
            task_match_sel = self.SELECTOR_PATTERN.match(task_selector_raw)
            if task_match_sel:
                task_selector_str = task_match_sel.group(1).lower()
                inner = task_match_sel.group(2).strip()
                task_selector_type = VersionSelector.AT if task_selector_str == "at" else VersionSelector.BEFORE
                idx_match = self.NODE_INDEX_PATTERN.match(inner)
                neg_i_match = self.NODE_NEGATIVE_I_PATTERN.match(inner)
                bracket_match = self.INDEX_ONLY_PATTERN.match(inner)
                number_match = self.NUMBER_ONLY_PATTERN.match(inner)
                if idx_match:
                    task_index = int(idx_match.group(2))
                elif neg_i_match or self.BRACKET_NEGATIVE_I_PATTERN.match(inner) or self.NEGATIVE_I_PATTERN.match(inner):
                    task_index = -1
                elif bracket_match:
                    task_index = int(bracket_match.group(1))
                elif number_match:
                    task_index = int(number_match.group(0).strip())
                else:
                    task_semantic_query = inner

        if version_selector_raw and version_selector_raw.lower() != "none":
            version_match_sel = self.SELECTOR_PATTERN.match(version_selector_raw)
            if version_match_sel:
                version_selector_str = version_match_sel.group(1).lower()
                inner = version_match_sel.group(2).strip()
                version_selector_type = VersionSelector.AT if version_selector_str == "at" else VersionSelector.BEFORE
                idx_match = self.NODE_INDEX_PATTERN.match(inner)
                neg_i_match = self.NODE_NEGATIVE_I_PATTERN.match(inner)
                bracket_match = self.INDEX_ONLY_PATTERN.match(inner)
                number_match = self.NUMBER_ONLY_PATTERN.match(inner)
                if idx_match:
                    index = int(idx_match.group(2))
                elif neg_i_match or self.BRACKET_NEGATIVE_I_PATTERN.match(inner) or self.NEGATIVE_I_PATTERN.match(inner):
                    index = -1
                elif bracket_match:
                    index = int(bracket_match.group(1))
                elif number_match:
                    index = int(number_match.group(0).strip())
                else:
                    semantic_query = inner

        try:
            crud_operation = CRUDOperation(crud_str.capitalize()) if crud_str else CRUDOperation.READ
        except ValueError:
            crud_operation = CRUDOperation.READ

        return ResolvedVersion(
            selector_type=version_selector_type,
            semantic_query=semantic_query,
            index=index,
            task_selector_type=task_selector_type,
            task_semantic_query=task_semantic_query,
            task_index=task_index,
            crud_operation=crud_operation,
            raw_response=response,
            task_query=task_query,
        )

    def apply_task_schema(self, schema_name: Optional[str], task_number: Optional[int] = None) -> None:
        if not schema_name:
            # Try cached schema for current task
            if task_number is not None:
                cached = self._task_schema_cache.get(task_number)
                if cached:
                    schema_name = cached
            if not schema_name:
                return
        schema_path = Path(schema_name)
        if not (schema_path.exists() and schema_path.is_file()):
            candidate = self._task_schema_dir / f"{schema_name}.yaml"
            if candidate.exists() and candidate.is_file():
                schema_path = candidate
        if not (schema_path.exists() and schema_path.is_file()):
            return
        schema_path_str = str(schema_path)
        if task_number is not None:
            self._task_schema_cache[task_number] = schema_path_str
        if self._task_schema_name == schema_path_str:
            return
        self._task_schema_name = schema_path_str
        if self.query_generator is None:
            from pipeline_execution.query_generation.xpath_query_generator import XPathQueryGenerator
            self.query_generator = XPathQueryGenerator()
        self.query_generator.set_schema(schema_path_str)
        if schema_path_str in self._schema_cache:
            schema = self._schema_cache[schema_path_str]
        else:
            schema = load_schema(schema_path_str)
            self._schema_cache[schema_path_str] = schema
        handler_traces_path = self._traces_path / "reasoning_traces" if self._traces_path else None
        self.read_handler = ReadHandler(schema=schema, traces_path=handler_traces_path)
        self.delete_handler = DeleteHandler(schema=schema, traces_path=handler_traces_path)
        self.update_handler = UpdateHandler(schema=schema, traces_path=handler_traces_path)
        self.create_handler = CreateHandler(schema=schema, traces_path=handler_traces_path)

    def set_tree(self, tree: Optional[ET.ElementTree]) -> None:
        """Set the in-memory tree used for task/version resolution."""
        self._tree = tree

    def get_task_schema_path(self) -> Optional[str]:
        return self._task_schema_name

    def build_task_schema_path(self, task_name: Optional[str]) -> Optional[str]:
        if not task_name:
            if self._state_task_index is not None:
                cached = self._task_schema_cache.get(self._state_task_index)
                if cached:
                    return cached
            return self._task_schema_name
        candidate = self._task_schema_dir / f"{task_name}.yaml"
        if candidate.exists() and candidate.is_file():
            return str(candidate)
        return self._task_schema_name

    def apply_state_defaults(self, version_result: ResolvedVersion) -> None:
        if self._state_task_index is not None:
            if version_result.task_index is None and not version_result.task_semantic_query:
                version_result.task_index = self._state_task_index
        if self._state_version_index is not None:
            if version_result.index is None and not version_result.semantic_query:
                version_result.index = self._state_version_index

    def update_state(self, task_number: Optional[int], version_number: Optional[int]) -> None:
        if task_number is not None and task_number > 0:
            self._state_task_index = task_number
        if version_number is not None and version_number > 0:
            self._state_version_index = version_number

    def resolve_task_context(self, version_result: ResolvedVersion) -> Optional[Dict[str, Any]]:
        task_elem = self.resolve_task_from_global(version_result)
        if task_elem is None:
            return None
        task_number = self._safe_int(task_elem.get("number"))
        task_name = (task_elem.get("name") or "").strip()
        if task_name:
            schema_path = self._task_schema_dir / f"{task_name}.yaml"
            if schema_path.exists():
                if task_number is not None:
                    self._task_schema_cache[task_number] = str(schema_path)
                return {
                    "schema_name": task_name,
                    "memory_path": self._task_memory_dir / f"{task_name}.xml",
                    "title": (task_elem.findtext("title") or "").strip(),
                    "description": (task_elem.findtext("description") or "").strip(),
                }
        title = (task_elem.findtext("title") or "").strip()
        description = (task_elem.findtext("description") or "").strip()
        candidate = self.match_task_candidate(title, description)
        if candidate and task_number is not None:
            schema_name = candidate.get("schema_name")
            if schema_name:
                schema_path = self._task_schema_dir / f"{schema_name}.yaml"
                if schema_path.exists():
                    self._task_schema_cache[task_number] = str(schema_path)
        return candidate

    def resolve_task_version_elements(self, version_result: ResolvedVersion) -> Tuple[Optional[ET.Element], Optional[int], Optional[int]]:
        task_elem = self.resolve_task_from_global(version_result)
        if task_elem is None:
            return None, None, None

        task_number = self._safe_int(task_elem.get("number"))
        if task_number is not None:
            version_result.task_index = task_number

        versions = [c for c in list(task_elem) if c.tag == "Version"]
        if not versions:
            return task_elem, task_number, None

        version_elem = self.select_version(versions, version_result)
        if version_elem is None:
            return task_elem, task_number, None

        if version_result.selector_type == VersionSelector.BEFORE:
            version_elem = self._select_previous(versions, version_elem)
            if version_elem is None:
                return task_elem, task_number, None

        version_number = self._safe_int(version_elem.get("number"))
        if version_number is not None:
            version_result.index = version_number

        print(f"Selected task number: {task_number}")
        return task_elem, task_number, version_number

    def resolve_task_from_global(self, version_result: ResolvedVersion) -> Optional[ET.Element]:
        tasks = self.load_global_tasks()
        if not tasks:
            return None
        ordered_tasks = self._order_by_number(tasks)
        task_elem = self.select_task(ordered_tasks, version_result)
        if task_elem is None:
            return None
        if version_result.task_selector_type == VersionSelector.BEFORE:
            task_elem = self._select_previous(ordered_tasks, task_elem)
        return task_elem

    @staticmethod
    def _safe_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _select_previous(items: List[ET.Element], current: ET.Element) -> Optional[ET.Element]:
        try:
            idx = items.index(current)
        except ValueError:
            return None
        if idx <= 0:
            return None
        return items[idx - 1]

    def _order_by_number(self, items: List[ET.Element]) -> List[ET.Element]:
        indexed: List[Tuple[int, Optional[int], int, ET.Element]] = []
        for i, elem in enumerate(items):
            num = self._safe_int(elem.get("number"))
            has_num = 0 if num is not None else 1
            indexed.append((has_num, num if num is not None else 0, i, elem))
        indexed.sort(key=lambda t: (t[0], t[1], t[2]))
        return [t[3] for t in indexed]

    def load_global_tasks(self) -> List[ET.Element]:
        if self._tree is not None:
            root = self._tree.getroot()
            return [c for c in list(root) if c.tag == "Task"]
        if not self._global_memory_path.exists():
            return []
        try:
            tree = ET.parse(self._global_memory_path)
        except ET.ParseError:
            return []
        root = tree.getroot()
        return [c for c in list(root) if c.tag == "Task"]

    def match_task_candidate(self, title: str, description: str) -> Optional[Dict[str, Any]]:
        candidates = self.scan_task_candidates()
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        query = " | ".join([p for p in [title, description] if p])
        if not query:
            return candidates[-1]
        nodes = []
        for i, cand in enumerate(candidates):
            desc = " | ".join([p for p in [cand.get("title"), cand.get("description")] if p])
            nodes.append(
                {
                    "id": f"task_{i}",
                    "type": "Task",
                    "description": desc or "(no description)",
                }
            )
        scored = self.executor.scorer.score_batch(nodes, query)
        if scored.results:
            best = max(scored.results, key=lambda r: r.score)
            try:
                best_idx = int(str(best.node_id).split("_")[-1])
                return candidates[best_idx]
            except (ValueError, IndexError):
                pass
        lowered = query.lower()
        for cand in candidates:
            hay = f"{cand.get('title', '')} {cand.get('description', '')}".lower()
            if lowered in hay:
                return cand
        return candidates[-1]

    def scan_task_candidates(self) -> List[Dict[str, Any]]:
        if not self._task_memory_dir.exists():
            return []
        candidates: List[Dict[str, Any]] = []
        if not self._task_schema_dir.exists():
            return []
        for schema_path in sorted(self._task_schema_dir.glob("*.yaml")):
            schema_name = schema_path.stem
            title = ""
            desc = ""
            try:
                schema = load_schema(schema_name)
                desc = (schema.get("description") or "").strip()
            except Exception:
                pass
            candidates.append(
                {
                    "schema_name": schema_name,
                    "title": title,
                    "description": desc,
                }
            )
        return candidates

    def select_task(self, tasks: List[ET.Element], version_result: ResolvedVersion) -> Optional[ET.Element]:
        if len(tasks) == 1:
            return tasks[0]
        if version_result.task_semantic_query:
            matches = self.execute_selector_xpath(version_result.task_semantic_query, "Task")
            if matches:
                return matches[0]
            return tasks[-1]
        if version_result.task_index is None:
            return tasks[-1]
        if version_result.task_index < 0:
            ordered = self._order_by_number(tasks)
            idx = len(ordered) + version_result.task_index
            return ordered[idx] if 0 <= idx < len(ordered) else None
        for task in tasks:
            if task.get("number") == str(version_result.task_index):
                return task
        return None

    def select_version(self, versions: List[ET.Element], version_result: ResolvedVersion) -> Optional[ET.Element]:
        if version_result.semantic_query:
            matches = self.execute_selector_xpath(version_result.semantic_query, "Version")
            if matches:
                return matches[0]
            return versions[-1]
        if version_result.index is None:
            return versions[-1]
        if version_result.index < 0:
            idx = len(versions) + version_result.index
            return versions[idx] if 0 <= idx < len(versions) else None
        for version in versions:
            if version.get("number") == str(version_result.index):
                return version
        return None

    def execute_selector_xpath(self, selector_xpath: str, expected_tag: str) -> List[ET.Element]:
        if not selector_xpath:
            return []
        xpath = selector_xpath.strip()
        if not xpath.startswith("/") and not xpath.startswith("//"):
            if xpath.startswith("Task") or xpath.startswith("Version"):
                xpath = f"//{xpath}"
        try:
            result = self.executor.execute(xpath)
        except Exception:
            return []
        if not result.matched_nodes:
            return []
        root = self.executor.tree.getroot()
        sorted_nodes = sorted(result.matched_nodes, key=lambda n: n.score, reverse=True)
        matches: List[ET.Element] = []
        for node in sorted_nodes:
            elem = find_node_by_path(root, node.tree_path)
            if elem is not None and elem.tag == expected_tag:
                matches.append(elem)
        return matches

    def strip_task_selector(self, version_result: ResolvedVersion, task_index: Optional[int] = None) -> ResolvedVersion:
        return ResolvedVersion(
            selector_type=version_result.selector_type,
            semantic_query=version_result.semantic_query,
            index=version_result.index,
            task_selector_type=VersionSelector.AT,
            task_semantic_query=None,
            task_index=task_index if task_index is not None else -1,
            crud_operation=version_result.crud_operation,
            raw_response=version_result.raw_response,
            task_query=version_result.task_query,
            token_usage=version_result.token_usage,
        )

    def get_state_task_index(self) -> Optional[int]:
        return self._state_task_index


# Backwards compatibility
TaskVersionResolver = GlobalInfoResolver
