"""
Cold Start Client - Generates task schema, domain schema, and initial XML tree
from a user request using a two-step LLM process:
1) Generate task metadata + schema + user-facing response
2) Generate content from the request and schema

Adapted from Semantic_Xpath_prev_exp/pipeline_execution/cold_start/task_bootstrapper.py
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import yaml

from client import get_default_client


# Resolve paths relative to Semantic_Xpath_BE root
_BASE_DIR = Path(__file__).resolve().parents[2]
_STORAGE_DIR = _BASE_DIR / "storage"
_PLAN_PROMPT_PATH = _STORAGE_DIR / "prompts" / "cold_start" / "plan_generator.txt"
_SCHEMA_PROMPT_PATH = _STORAGE_DIR / "prompts" / "cold_start" / "schema_generator.txt"
_CONTENT_PROMPT_PATH = _STORAGE_DIR / "prompts" / "cold_start" / "content_generator.txt"


@dataclass
class ColdStartArtifacts:
    """Container for all artifacts produced by a cold start generation."""
    success: bool
    domain: Dict[str, Any]
    task: Dict[str, Any]
    task_schema: Dict[str, Any]
    domain_schema: Dict[str, Any]
    memory_xml: str
    paths: Dict[str, str]
    warnings: List[str]
    token_usage: Optional[Dict[str, int]] = None


class ColdStartClient:
    """
    Generate schemas and an initial memory tree for a new task.

    Returns:
      - task schema (task-specific, Root-based)
      - fixed domain schema (Root -> Task -> Version)
      - XML memory tree (Root -> Task -> Version -> ...)
    """

    def __init__(self, client=None):
        self._client = client or get_default_client()
        self._plan_prompt = None
        self._schema_prompt = None
        self._content_prompt = None

    # ------------------------------------------------------------------
    # Prompt loading (lazy)
    # ------------------------------------------------------------------

    @property
    def plan_prompt(self) -> str:
        if self._plan_prompt is None:
            with open(_PLAN_PROMPT_PATH, "r", encoding="utf-8") as f:
                self._plan_prompt = f.read()
        return self._plan_prompt

    @property
    def schema_prompt(self) -> str:
        if self._schema_prompt is None:
            with open(_SCHEMA_PROMPT_PATH, "r", encoding="utf-8") as f:
                self._schema_prompt = f.read()
        return self._schema_prompt

    @property
    def content_prompt(self) -> str:
        if self._content_prompt is None:
            with open(_CONTENT_PROMPT_PATH, "r", encoding="utf-8") as f:
                self._content_prompt = f.read()
        return self._content_prompt

    # ------------------------------------------------------------------
    # Main generation entry point
    # ------------------------------------------------------------------

    def generate(
        self,
        user_request: str,
        save: bool = True,
        activate: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the two-step cold start generation.

        Args:
            user_request: The user's natural language request.
            save: Whether to persist artifacts to storage.
            activate: Whether to activate the generated schema in config.

        Returns:
            Dict with success status, generated artifacts, and display data.
        """
        if not user_request or not user_request.strip():
            return {"success": False, "error": "User request cannot be empty"}

        # Step 1: Plan generation
        plan_result = self._client.complete_with_usage(
            f"User: {user_request.strip()}",
            system_prompt=self.plan_prompt,
            temperature=0.2,
            max_tokens=getattr(self._client, "max_tokens", 16384),
        )
        plan_raw = (plan_result.content or "").strip()

        try:
            plan_parsed = self._extract_json(plan_raw)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Failed to parse plan output: {e}",
                "raw_output": plan_raw,
            }

        user_facing = self._normalize_user_facing(
            plan_parsed.get("user_facing", {}), plan_parsed.get("task", {})
        )

        schema_parsed = {"schema": plan_parsed.get("schema", {})}

        # Step 2: Content generation
        content_prompt_text = self.content_prompt.replace(
            "<<USER_REQUEST>>",
            self._to_ascii(user_request.strip()),
        ).replace(
            "<<SCHEMA_JSON>>",
            json.dumps(schema_parsed.get("schema", {}), ensure_ascii=True),
        ).replace(
            "<<USER_FACING>>",
            self._to_ascii(user_facing or ""),
        )

        content_result = self._client.complete_with_usage(
            "Generate content from the request and schema.",
            system_prompt=content_prompt_text,
            temperature=0.2,
            max_tokens=getattr(self._client, "max_tokens", 16384),
        )
        content_raw = (content_result.content or "").strip()

        try:
            content_parsed = self._extract_json(content_raw)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Failed to parse content output: {e}",
                "raw_output": content_raw,
            }

        # Build artifacts
        artifacts = self._build_artifacts_from_split(
            plan_parsed, schema_parsed, content_parsed, user_request
        )
        artifacts.token_usage = {
            "plan": plan_result.usage.to_dict() if plan_result.usage else None,
            "content": content_result.usage.to_dict() if content_result.usage else None,
        }

        if save and artifacts.success:
            self._save_artifacts(artifacts)
            if activate:
                self._activate_config(artifacts)

        user_facing = self._normalize_user_facing(
            plan_parsed.get("user_facing", {}), artifacts.task
        )

        return {
            "success": artifacts.success,
            "plan_output": plan_parsed,
            "schema_output": schema_parsed,
            "content_output": content_parsed,
            "user_facing": user_facing,
            "domain": artifacts.domain,
            "task": artifacts.task,
            "task_schema": artifacts.task_schema,
            "domain_schema": artifacts.domain_schema,
            "memory_xml": artifacts.memory_xml,
            "paths": artifacts.paths,
            "warnings": artifacts.warnings,
            "token_usage": artifacts.token_usage,
            "display": self._build_display(artifacts),
        }

    # ------------------------------------------------------------------
    # JSON extraction
    # ------------------------------------------------------------------

    def _extract_json(self, text: str) -> Dict[str, Any]:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            raise ValueError("No JSON object found")
        json_str = text[json_start:json_end]
        return json.loads(json_str)

    # ------------------------------------------------------------------
    # Artifact building
    # ------------------------------------------------------------------

    def _build_artifacts_from_split(
        self,
        plan_parsed: Dict[str, Any],
        schema_parsed: Dict[str, Any],
        content_parsed: Dict[str, Any],
        user_request: str,
    ) -> ColdStartArtifacts:
        warnings: List[str] = []

        domain = self._normalize_domain(plan_parsed.get("domain", {}), warnings)
        task = self._normalize_task(plan_parsed.get("task", {}), domain, warnings)
        schema_input = schema_parsed.get("schema", schema_parsed)

        task_schema, schema_meta = self._normalize_task_schema(schema_input, task, warnings)
        content_root_tag = self._get_content_root_tag(task_schema)
        content = self._normalize_content(
            content_parsed.get("content", content_parsed), task_schema, warnings, content_root_tag
        )

        domain_schema = self._fixed_domain_schema(domain)
        memory_xml = self._build_memory_xml(task_schema, content, user_request, task)
        paths = self._compute_paths(domain, task, task_schema)

        return ColdStartArtifacts(
            success=True,
            domain=domain,
            task=task,
            task_schema=task_schema,
            domain_schema=domain_schema,
            memory_xml=memory_xml,
            paths=paths,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    def _normalize_domain(self, domain: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        name_raw = str(domain.get("name", "domain"))
        name = self._to_snake_case(name_raw)
        if name != name_raw:
            warnings.append(f"Normalized domain name '{name_raw}' -> '{name}'")
        desc = self._to_ascii(str(domain.get("description", "")))
        return {"name": name, "description": desc}

    def _normalize_task(
        self, task: Dict[str, Any], domain: Dict[str, Any], warnings: List[str]
    ) -> Dict[str, Any]:
        name_raw = str(task.get("name", "task"))
        name = self._to_snake_case(name_raw)
        if name != name_raw:
            warnings.append(f"Normalized task name '{name_raw}' -> '{name}'")
        title = self._to_ascii(str(task.get("title", "")))
        if not title:
            title = self._to_title_case_words(name)
        desc = self._to_ascii(str(task.get("description", "")))
        return {
            "name": name,
            "title": title,
            "description": desc,
            "domain": domain.get("name"),
        }

    def _normalize_task_schema(
        self,
        schema: Dict[str, Any],
        task: Dict[str, Any],
        warnings: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        raw_name = schema.get("name") or task.get("name") or "task_schema"
        schema_name = self._to_snake_case(str(raw_name))
        root_tag = "Root"
        reserved_tags = {"Task", "Version"}

        nodes_input = schema.get("nodes", {})
        if not nodes_input:
            nodes_input = {root_tag: {"type": "root", "fields": [], "children": []}}
            warnings.append("Schema nodes missing; created root-only schema")
        else:
            filtered_nodes = {}
            for k, v in nodes_input.items():
                tag = self._to_title_case_tag(str(k))
                if tag in reserved_tags:
                    continue
                filtered_nodes[k] = v
            nodes_input = filtered_nodes or {
                root_tag: {"type": "root", "fields": [], "children": []}
            }

        tag_map: Dict[str, str] = {}
        for key in nodes_input.keys():
            tag_map[key] = self._to_title_case_tag(str(key))
        if schema.get("root") or schema.get("root_tag"):
            tag_map[schema.get("root") or schema.get("root_tag")] = root_tag
        elif nodes_input:
            first_key = next(iter(nodes_input.keys()))
            tag_map[first_key] = root_tag

        nodes: Dict[str, Any] = {}
        for raw_tag, raw_config in nodes_input.items():
            tag = tag_map.get(raw_tag, self._to_title_case_tag(raw_tag))
            if tag in reserved_tags:
                continue
            cfg = raw_config or {}
            node_type = str(cfg.get("type", "leaf")).lower()
            if node_type not in ("root", "container", "leaf"):
                node_type = "leaf"

            fields_raw = cfg.get("fields", []) or []
            fields = [self._to_snake_case(str(f)) for f in fields_raw if f]

            children_raw = cfg.get("children", []) or []
            children = []
            for c in children_raw:
                child_tag = tag_map.get(str(c), self._to_title_case_tag(str(c)))
                if child_tag in reserved_tags:
                    continue
                children.append(child_tag)

            node_cfg: Dict[str, Any] = {
                "type": node_type,
                "fields": fields,
                "children": children,
            }
            if node_type == "container" and cfg.get("index_attr"):
                node_cfg["index_attr"] = self._to_snake_case(str(cfg.get("index_attr")))
            elif node_type == "container" and cfg.get("index_attr") is None and cfg.get("index"):
                node_cfg["index_attr"] = self._to_snake_case(str(cfg.get("index")))

            nodes[tag] = node_cfg

        if root_tag not in nodes:
            nodes[root_tag] = {"type": "root", "fields": [], "children": []}
            warnings.append(f"Added missing root node '{root_tag}' to schema")
        else:
            nodes[root_tag]["type"] = "root"

        for node_tag, node_cfg in list(nodes.items()):
            for child in node_cfg.get("children", []):
                if child not in nodes:
                    nodes[child] = {"type": "leaf", "fields": ["name", "description"], "children": []}
                    warnings.append(f"Added placeholder child node '{child}' to schema")

        description = f"{task.get('title', 'Task')} structure"
        hierarchy = self._build_hierarchy_tree(root_tag, nodes)
        syntax_rules = self._build_syntax_rules(root_tag, nodes)

        task_schema: Dict[str, Any] = {
            "name": schema_name,
            "description": description,
            "hierarchy": hierarchy,
            "nodes": nodes,
            "root": root_tag,
            "content_root": root_tag,
            "data_files": {},
            "default_data": "",
            "examples_file": "",
            "syntax_rules": syntax_rules,
        }

        return task_schema, {"schema_name": schema_name, "root_tag": root_tag}

    def _normalize_user_facing(self, user_facing: Any, task: Optional[Dict[str, Any]]) -> str:
        if isinstance(user_facing, str):
            text = self._to_ascii(user_facing.strip())
            if text:
                return text
        if isinstance(user_facing, dict):
            title = self._to_ascii(str(user_facing.get("title", "")))
            if not title:
                fallback = (task or {}).get("title", "Plan")
                title = self._to_ascii(str(fallback))
            overview = self._to_ascii(str(user_facing.get("overview", "")))
            sections_raw = user_facing.get("sections", []) or []
            lines: List[str] = []
            if title:
                lines.append(f"- {title}")
            if overview:
                lines.append(f"- {overview}")
            for section in sections_raw:
                if not isinstance(section, dict):
                    continue
                sec_title = self._to_ascii(str(section.get("title", "")))
                sec_summary = self._to_ascii(str(section.get("summary", "")))
                bullets_raw = section.get("bullets", []) or []
                bullets = [self._to_ascii(str(b)) for b in bullets_raw if b]
                if sec_title:
                    lines.append(f"- {sec_title}")
                if sec_summary:
                    lines.append(f"- {sec_summary}")
                for b in bullets:
                    lines.append(f"- {b}")
            if lines:
                return "\n".join(lines).strip()
        fallback = (task or {}).get("title", "Plan")
        return f"- {self._to_ascii(str(fallback))}"

    def _normalize_content(
        self,
        content: Dict[str, Any],
        task_schema: Dict[str, Any],
        warnings: List[str],
        content_root_tag: str,
    ) -> Dict[str, Any]:
        nodes = task_schema.get("nodes", {})
        root_tag = content_root_tag

        root_fields = content.get("root_fields", {}) or {}
        root_attrs = content.get("root_attrs", {}) or {}

        allowed_root_fields = set(nodes.get(root_tag, {}).get("fields", []))
        filtered_root_fields = {
            self._to_snake_case(str(k)): self._sanitize_field_value(v)
            for k, v in root_fields.items()
            if self._to_snake_case(str(k)) in allowed_root_fields
        }

        if allowed_root_fields and not filtered_root_fields and root_fields:
            warnings.append("Root fields did not match schema; ignored mismatched fields")

        children = content.get("children", []) or []
        normalized_children = self._normalize_children(children, nodes, warnings)

        return {
            "root_tag": root_tag,
            "root_fields": filtered_root_fields,
            "root_attrs": self._sanitize_attrs(root_attrs),
            "children": normalized_children,
        }

    def _get_content_root_tag(self, task_schema: Dict[str, Any]) -> str:
        root_tag = task_schema.get("root")
        if root_tag:
            return root_tag
        nodes = task_schema.get("nodes", {})
        for name in nodes.keys():
            return name
        return "Content"

    def _normalize_children(
        self,
        children: List[Dict[str, Any]],
        nodes: Dict[str, Any],
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        index_counters: Dict[str, int] = {}

        for child in children:
            tag_raw = child.get("tag", "")
            tag = self._to_title_case_tag(str(tag_raw))
            if tag not in nodes:
                warnings.append(f"Dropped unknown node tag '{tag_raw}'")
                continue

            node_cfg = nodes.get(tag, {})
            fields_cfg = node_cfg.get("fields", [])
            allowed_fields = set(fields_cfg)

            attrs = self._sanitize_attrs(child.get("attrs", {}) or {})
            index_attr = node_cfg.get("index_attr")
            if index_attr:
                if index_attr not in attrs:
                    index_counters[tag] = index_counters.get(tag, 0) + 1
                    attrs[index_attr] = str(index_counters[tag])

            fields_raw = child.get("fields", {}) or {}
            fields: Dict[str, Any] = {}
            for k, v in fields_raw.items():
                key = self._to_snake_case(str(k))
                if key in allowed_fields:
                    fields[key] = self._sanitize_field_value(v)

            nested_children = child.get("children", []) or []
            normalized_nested = self._normalize_children(nested_children, nodes, warnings)

            results.append({
                "tag": tag,
                "attrs": attrs,
                "fields": fields,
                "children": normalized_nested,
            })

        return results

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _fixed_domain_schema(self, domain: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": "root_task_version",
            "description": "Global container for tasks with versions",
            "hierarchy": (
                "Root (root)\n"
                "  `-- Task (container, indexed by @number)\n"
                "      `-- Version (version, indexed by @number)"
            ),
            "nodes": {
                "Root": {"type": "root", "fields": [], "children": ["Task"]},
                "Task": {
                    "type": "container",
                    "index_attr": "number",
                    "fields": ["title", "description"],
                    "children": ["Version"],
                },
                "Version": {
                    "type": "version",
                    "index_attr": "number",
                    "fields": ["description"],
                    "children": [],
                },
            },
        }

    # ------------------------------------------------------------------
    # XML building
    # ------------------------------------------------------------------

    def _build_memory_xml(
        self,
        task_schema: Dict[str, Any],
        content: Dict[str, Any],
        user_request: str,
        task: Dict[str, Any],
    ) -> str:
        root = ET.Element("Root")

        for k, v in content.get("root_attrs", {}).items():
            root.set(str(k), str(v))

        for field_name, value in content.get("root_fields", {}).items():
            self._append_field(root, field_name, value)

        for child in content.get("children", []):
            root.append(self._build_xml_node(child))

        tree = ET.ElementTree(root)
        return self._xml_to_string(tree)

    def _build_xml_node(self, node: Dict[str, Any]) -> ET.Element:
        element = ET.Element(node.get("tag", "Node"))
        for k, v in (node.get("attrs", {}) or {}).items():
            element.set(str(k), str(v))
        for field_name, value in (node.get("fields", {}) or {}).items():
            self._append_field(element, field_name, value)
        for child in node.get("children", []) or []:
            element.append(self._build_xml_node(child))
        return element

    def _append_field(self, element: ET.Element, field_name: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, list):
            container = ET.SubElement(element, field_name)
            item_name = field_name.rstrip("s") or "item"
            for item in value:
                child = ET.SubElement(container, item_name)
                child.text = str(item)
        else:
            child = ET.SubElement(element, field_name)
            child.text = str(value)

    def _xml_to_string(self, tree: ET.ElementTree) -> str:
        buffer = BytesIO()
        try:
            ET.indent(tree.getroot())
        except AttributeError:
            pass
        tree.write(buffer, encoding="utf-8", xml_declaration=True)
        return buffer.getvalue().decode("utf-8")

    # ------------------------------------------------------------------
    # Path computation & persistence
    # ------------------------------------------------------------------

    def _compute_paths(
        self,
        domain: Dict[str, Any],
        task: Dict[str, Any],
        task_schema: Dict[str, Any],
    ) -> Dict[str, str]:
        task_name = task.get("name", "task")
        schema_dir = _STORAGE_DIR / "schemas" / "task"
        memory_path = _STORAGE_DIR / "memory" / "task" / f"{task_name}.xml"
        examples_path = (
            _STORAGE_DIR / "prompts" / "query_generator" / "domains"
            / f"xpath_examples_{task_name}.txt"
        )
        domain_schema_path = _STORAGE_DIR / "schemas" / "global" / "root_task_version.yaml"
        global_memory_path = _STORAGE_DIR / "memory" / "global" / "root_task_version.xml"

        return {
            "task_schema": str(schema_dir / f"{task_name}.yaml"),
            "domain_schema": str(domain_schema_path),
            "memory_xml": str(memory_path),
            "examples": str(examples_path),
            "global_memory_xml": str(global_memory_path),
        }

    def _save_artifacts(self, artifacts: ColdStartArtifacts) -> None:
        paths = artifacts.paths
        schema_path = Path(paths["task_schema"])
        domain_schema_path = Path(paths["domain_schema"])
        memory_path = Path(paths["memory_xml"])
        examples_path = Path(paths["examples"])
        global_memory_path = Path(paths["global_memory_xml"])

        schema_dir = schema_path.parent
        schema_dir.mkdir(parents=True, exist_ok=True)
        domain_schema_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        examples_path.parent.mkdir(parents=True, exist_ok=True)
        global_memory_path.parent.mkdir(parents=True, exist_ok=True)

        if schema_path.exists():
            base = schema_dir.name
            idx = 1
            while True:
                candidate = schema_dir.parent / f"{base}_cs{idx}"
                if not candidate.exists():
                    schema_dir = candidate
                    schema_path = candidate / f"{candidate.name}.yaml"
                    artifacts.paths["task_schema"] = str(schema_path)
                    new_examples = (
                        _STORAGE_DIR / "prompts" / "query_generator" / "domains"
                        / f"xpath_examples_{candidate.name}.txt"
                    )
                    artifacts.paths["examples"] = str(new_examples)
                    artifacts.task_schema["name"] = candidate.name
                    break
                idx += 1
            schema_dir.mkdir(parents=True, exist_ok=True)

        examples_path = Path(artifacts.paths["examples"])

        data_name = Path(artifacts.paths["memory_xml"]).stem
        artifacts.task_schema["data_files"] = {
            data_name: self._relative_storage_path(Path(artifacts.paths["memory_xml"]))
        }
        artifacts.task_schema["default_data"] = data_name
        artifacts.task_schema["examples_file"] = self._relative_storage_path(
            Path(artifacts.paths["examples"])
        )

        with open(schema_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(artifacts.task_schema, f, sort_keys=False, default_flow_style=False, indent=2)

        with open(domain_schema_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(artifacts.domain_schema, f, sort_keys=False, default_flow_style=False, indent=2)

        examples_text = self._build_examples_text(artifacts.task_schema)
        with open(examples_path, "w", encoding="utf-8") as f:
            f.write(examples_text)

        memory_path.write_text(artifacts.memory_xml, encoding="utf-8")
        self._update_global_memory(artifacts, global_memory_path)

    def _update_global_memory(self, artifacts: ColdStartArtifacts, global_memory_path: Path) -> None:
        if global_memory_path.exists():
            try:
                tree = ET.parse(global_memory_path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("Root")
                tree = ET.ElementTree(root)
        else:
            root = ET.Element("Root")
            tree = ET.ElementTree(root)

        task_title = artifacts.task.get("title", "")
        task_desc = artifacts.task.get("description", "")
        task_name = artifacts.task.get("name", "")

        existing_tasks = [c for c in list(root) if c.tag == "Task"]
        task_number = len(existing_tasks) + 1

        task_node = ET.SubElement(root, "Task")
        task_node.set("number", str(task_number))
        if task_name:
            task_node.set("name", self._to_snake_case(task_name))
        ET.SubElement(task_node, "title").text = task_title
        ET.SubElement(task_node, "description").text = task_desc

        version_node = ET.SubElement(task_node, "Version")
        version_node.set("number", "1")
        ET.SubElement(version_node, "description").text = "original version"

        try:
            task_tree = ET.ElementTree(ET.fromstring(artifacts.memory_xml))
            task_root = task_tree.getroot()
            for child in list(task_root):
                version_node.append(copy.deepcopy(child))
        except ET.ParseError:
            pass

        try:
            ET.indent(tree.getroot())
        except AttributeError:
            pass
        tree.write(global_memory_path, encoding="utf-8", xml_declaration=True)

    def _activate_config(self, artifacts: ColdStartArtifacts) -> None:
        config_path = _BASE_DIR / "config.yaml"
        if not config_path.exists():
            return
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        config["active_schema"] = artifacts.task_schema.get("name")
        config["active_data"] = Path(artifacts.paths.get("memory_xml", "")).stem

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False, indent=2)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _build_display(self, artifacts: ColdStartArtifacts) -> Dict[str, str]:
        summary_lines = [
            "Cold Start Result",
            f"Domain: {artifacts.domain.get('name')} - {artifacts.domain.get('description')}",
            f"Task: {artifacts.task.get('name')} - {artifacts.task.get('title')}",
            f"Schema: {artifacts.task_schema.get('name')}",
        ]
        if artifacts.warnings:
            summary_lines.append("Warnings: " + "; ".join(artifacts.warnings))

        paths_lines = [
            "Paths",
            f"Task schema: {artifacts.paths.get('task_schema')}",
            f"Domain schema: {artifacts.paths.get('domain_schema')}",
            f"Examples: {artifacts.paths.get('examples')}",
            f"Memory XML: {artifacts.paths.get('memory_xml')}",
            f"Global memory XML: {artifacts.paths.get('global_memory_xml')}",
        ]

        domain_schema_text = yaml.safe_dump(
            artifacts.domain_schema, sort_keys=False, default_flow_style=False, indent=2
        )
        task_schema_text = yaml.safe_dump(
            artifacts.task_schema, sort_keys=False, default_flow_style=False, indent=2
        )
        pretty_xml = self._pretty_xml(artifacts.memory_xml)

        return {
            "summary": "\n".join(summary_lines),
            "paths": "\n".join(paths_lines),
            "domain_schema": domain_schema_text.strip(),
            "task_schema": task_schema_text.strip(),
            "memory_xml": pretty_xml.strip(),
        }

    def _pretty_xml(self, xml_text: str) -> str:
        try:
            import xml.dom.minidom as minidom
            parsed = minidom.parseString(xml_text.encode("utf-8"))
            return parsed.toprettyxml(indent="  ")
        except Exception:
            return xml_text

    # ------------------------------------------------------------------
    # Examples builder
    # ------------------------------------------------------------------

    def _build_examples_text(self, task_schema: Dict[str, Any]) -> str:
        nodes = task_schema.get("nodes", {})
        root_tag = next((k for k, v in nodes.items() if v.get("type") == "root"), "Root")
        leaf_tags = [k for k, v in nodes.items() if v.get("type") == "leaf"]
        container_tags = [k for k, v in nodes.items() if v.get("type") == "container"]
        leaf = leaf_tags[0] if leaf_tags else root_tag
        container = container_tags[0] if container_tags else root_tag

        lines = [
            "## Examples",
            "",
            "### Basic Queries",
            "User: find items related to a topic",
            f'Output: /{root_tag}//{leaf}[atom(content =~ "topic")]',
            "",
            f"User: show me the second {container}",
            f"Output: /{root_tag}/{container}[2]",
            "",
            "### Local Index Queries",
            f"User: everything under the first {container}",
            f"Output: /{root_tag}/{container}[1]/*",
            "",
            "### Global Index Queries",
            f"User: the first 3 {leaf} overall",
            f"Output: (/{root_tag}//{leaf})[1:3]",
            "",
            "### Descendant Axis Queries",
            f"User: all {leaf} in the structure",
            f"Output: /{root_tag}//{leaf}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Hierarchy / syntax
    # ------------------------------------------------------------------

    def _build_hierarchy_tree(self, root_tag: str, nodes: Dict[str, Any]) -> Dict[str, Any]:
        def build(tag: str) -> Dict[str, Any]:
            children = nodes.get(tag, {}).get("children", [])
            return {tag: {child: build(child)[child] for child in children}}

        if root_tag not in nodes:
            return {}
        return build(root_tag)

    def _build_syntax_rules(self, root_tag: str, nodes: Dict[str, Any]) -> str:
        node_types = ", ".join(nodes.keys())
        rules = [
            f"- Paths start with /{root_tag}",
            f"- Node types: {node_types}",
            "- Indices: Node[1], Node[-1], Node[1:3]",
            "- Logical: AND / OR / not() combine predicates WITHIN brackets",
        ]
        return "\n".join(rules)

    # ------------------------------------------------------------------
    # Sanitization utilities
    # ------------------------------------------------------------------

    def _sanitize_field_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._to_ascii(str(v)) for v in value if v is not None]
        if isinstance(value, (int, float)):
            return value
        return self._to_ascii(str(value))

    def _sanitize_attrs(self, attrs: Dict[str, Any]) -> Dict[str, str]:
        return {self._to_snake_case(str(k)): self._to_ascii(str(v)) for k, v in attrs.items()}

    def _relative_storage_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(_STORAGE_DIR))
        except ValueError:
            return str(path)

    @staticmethod
    def _to_ascii(text: str) -> str:
        return "".join(ch for ch in text if ord(ch) < 128)

    @staticmethod
    def _to_snake_case(text: str) -> str:
        text = re.sub(r"[^A-Za-z0-9]+", "_", text)
        text = text.strip("_")
        return text.lower() if text else "item"

    @staticmethod
    def _to_title_case_tag(text: str) -> str:
        text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
        if not text:
            return "Node"
        parts = [p for p in text.split("_") if p]
        return "_".join(p[:1].upper() + p[1:] for p in parts)

    @staticmethod
    def _to_title_case_words(text: str) -> str:
        words = re.split(r"[_\\s]+", text.strip())
        words = [w for w in words if w]
        return " ".join(w[:1].upper() + w[1:] for w in words)
