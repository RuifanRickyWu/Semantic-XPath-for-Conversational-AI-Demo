"""
Schema Loader - Loads tree schema configurations.

Provides functions to load schema definitions and resolve data file paths.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List


# Base directories
_BASE_DIR = Path(__file__).resolve().parents[2]
_SCHEMA_DIR = _BASE_DIR / "storage" / "schemas"
_STORAGE_DIR = _BASE_DIR / "storage"


def _get_schema_dir(schema_name: str) -> Path:
    """
    Resolve the schema directory for a scenario.
    
    Supports both legacy single-file schemas and new folder-based schemas:
    - storage/schemas/{schema_name}.yaml
    - storage/schemas/{schema_name}/{schema_name}.yaml
    - storage/schemas/global/{schema_name}.yaml
    - storage/schemas/task/{schema_name}.yaml
    """
    # Folder-based schemas (legacy)
    candidate = _SCHEMA_DIR / schema_name
    if candidate.is_dir():
        return candidate

    # Single-file schemas at root
    if (_SCHEMA_DIR / f"{schema_name}.yaml").exists():
        return _SCHEMA_DIR

    # Global schemas
    global_dir = _SCHEMA_DIR / "global"
    if (global_dir / f"{schema_name}.yaml").exists():
        return global_dir

    # Task schemas
    task_dir = _SCHEMA_DIR / "task"
    if (task_dir / f"{schema_name}.yaml").exists():
        return task_dir

    return _SCHEMA_DIR


def _get_schema_path(schema_name: str) -> Path:
    """Get path to the main content schema file."""
    return _get_schema_dir(schema_name) / f"{schema_name}.yaml"


def _get_version_schema_path(schema_name: str) -> Path:
    """Get path to the version schema file for a scenario."""
    return _get_schema_dir(schema_name) / f"{schema_name}_version.yaml"


def load_config() -> Dict[str, Any]:
    """Load the main config.yaml file with optional path overrides."""
    config_path = _BASE_DIR / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Environment overrides (highest precedence)
    env_schema_path = os.getenv("SEMANTIC_XPATH_SCHEMA_PATH")
    env_data_path = os.getenv("SEMANTIC_XPATH_DATA_PATH")
    if env_schema_path:
        config["active_schema_path"] = env_schema_path
    if env_data_path:
        config["active_data_path"] = env_data_path

    # Optional semantic xpath path overrides from config.yaml
    task_schema_path = config.get("task_schema_path")
    data_path = config.get("data_path")
    if task_schema_path and not config.get("active_schema_path"):
        candidate = Path(task_schema_path)
        if candidate.exists() and candidate.is_file():
            config["active_schema_path"] = task_schema_path
    if data_path and not config.get("active_data_path"):
        config["active_data_path"] = data_path

    return config


def load_schema(schema_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load a schema definition by name.
    
    Args:
        schema_name: Name of the schema (e.g., "itinerary"). 
                    If None, uses active_schema from config.
        config: Optional config dict. If not provided, loads from config.yaml.
    
    Returns:
        Schema dictionary with node definitions, data files, etc.
    """
    if config is None:
        config = load_config()

    schema_path = None

    # Allow direct path in schema_name
    if schema_name:
        candidate = Path(schema_name)
        if candidate.exists() and candidate.is_file():
            schema_path = candidate

    # Allow config-specified full path override
    if schema_path is None:
        schema_path_value = config.get("active_schema_path")
        if schema_path_value:
            schema_path = Path(schema_path_value)

    if schema_path is None:
        if schema_name is None:
            schema_name = config.get("active_schema")
        if schema_name:
            schema_path = _get_schema_path(schema_name)
        else:
            # Fallback to task or global schema paths from config
            task_schema_path = config.get("task_schema_path")
            global_schema_path = config.get("global_schema_path")
            if task_schema_path:
                candidate = Path(task_schema_path)
                if candidate.exists() and candidate.is_file():
                    schema_path = candidate
            if schema_path is None and global_schema_path:
                candidate = Path(global_schema_path)
                if candidate.exists() and candidate.is_file():
                    schema_path = candidate
            else:
                raise ValueError("No schema path configured in config.yaml")
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)


def load_version_schema(schema_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the version schema definition by name.
    
    Args:
        schema_name: Name of the schema (e.g., "itinerary").
                    If None, uses active_schema from config.yaml.
    
    Returns:
        Version schema dictionary, or empty dict if not found.
    """
    config = load_config()
    version_path = None

    # If a schema path override exists, look for sibling *_version.yaml
    schema_path_value = config.get("active_schema_path")
    if schema_path_value:
        schema_path = Path(schema_path_value)
        if schema_path.exists():
            candidate = schema_path.with_name(f"{schema_path.stem}_version.yaml")
            if candidate.exists():
                version_path = candidate

    if version_path is None:
        if schema_name is None:
            schema_name = config.get("active_schema")
        if schema_name:
            version_path = _get_version_schema_path(schema_name)
        else:
            # Fallback to global schema path from config
            global_schema_path = config.get("global_schema_path")
            if global_schema_path:
                schema_path = Path(global_schema_path)
                candidate = schema_path.with_name(f"{schema_path.stem}_version.yaml")
                if candidate.exists():
                    version_path = candidate
            else:
                raise ValueError("No global schema path configured in config.yaml")
    
    if version_path is None:
        return {}
    if not version_path.exists():
        return {}
    
    with open(version_path, "r") as f:
        return yaml.safe_load(f)


def _find_node_by_type(nodes: Dict[str, Any], node_type: str) -> Optional[str]:
    for name, config in nodes.items():
        if config.get("type") == node_type:
            return name
    return None


def _find_path_between_nodes(
    nodes: Dict[str, Any], 
    root_name: str, 
    target_name: str
) -> list:
    """Find a path from root to target using children links."""
    if not root_name or not target_name:
        return []
    
    queue = [(root_name, [root_name])]
    visited = set()
    
    while queue:
        current, path = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        
        if current == target_name:
            return path
        
        children = nodes.get(current, {}).get("children", [])
        for child in children:
            if child not in visited:
                queue.append((child, path + [child]))
    
    return []


def get_versioning_info(schema_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get versioning metadata and resolved path info for a schema.
    
    Returns:
        Dict with root tag, version tag, index attr, and path parts.
    """
    version_schema = load_version_schema(schema_name)
    nodes = version_schema.get("nodes", {}) if version_schema else {}
    versioning = version_schema.get("versioning", {}) if version_schema else {}
    
    root_tag = versioning.get("root") or _find_node_by_type(nodes, "root")
    version_tag = versioning.get("version_node") or _find_node_by_type(nodes, "version")
    
    index_attr = (
        versioning.get("version_index_attr")
        or nodes.get(version_tag, {}).get("index_attr")
        or "number"
    )
    
    content_container = versioning.get("content_container")
    
    path_parts = versioning.get("path_parts")
    if not path_parts and root_tag and version_tag:
        path_parts = _find_path_between_nodes(nodes, root_tag, version_tag)
    if not path_parts and root_tag and version_tag:
        path_parts = [root_tag, version_tag]
    
    version_path = "/" + "/".join(path_parts) if path_parts else ""
    
    return {
        "root_tag": root_tag,
        "version_tag": version_tag,
        "version_index_attr": index_attr,
        "content_container": content_container,
        "version_path_parts": path_parts,
        "version_path": version_path,
    }


def get_data_path(
    data_name: Optional[str] = None, 
    schema_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Path:
    """
    Get the full path to a data file.
    
    Args:
        data_name: Name of the data file (e.g., "travel_memory_5day").
                  If None, uses active_data from config or schema's default.
        schema_name: Name of the schema. If None, uses active_schema from config.
        config: Optional config dict. If not provided, loads from config.yaml.
    
    Returns:
        Full Path to the data file.
    """
    if config is None:
        config = load_config()

    # Allow direct path in data_name
    if data_name:
        candidate = Path(data_name)
        if candidate.exists():
            return candidate

    # Allow config-specified full path override
    data_path_value = config.get("active_data_path")
    if data_path_value:
        candidate = Path(data_path_value)
        if candidate.exists():
            return candidate

    schema = load_schema(schema_name, config=config)
    
    # Determine which data file to use
    if data_name is None:
        # First check config for active_data
        data_name = config.get("active_data")
        
        # Fall back to schema's default_data
        if data_name is None:
            data_name = schema.get("default_data")
    
    if data_name is None:
        raise ValueError("No data file specified and no default found")
    
    # Get the relative path from schema
    data_files = schema.get("data_files", {})
    
    if data_name not in data_files:
        raise ValueError(
            f"Data file '{data_name}' not found in schema. "
            f"Available: {list(data_files.keys())}"
        )
    
    relative_path = data_files[data_name]
    return _STORAGE_DIR / relative_path


def get_schema_info(schema_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive schema information including resolved paths.
    
    Args:
        schema_name: Name of the schema. If None, uses active_schema from config.
    
    Returns:
        Dictionary with schema info and resolved paths.
    """
    config = load_config()
    schema = load_schema(schema_name)
    version_schema = load_version_schema(schema_name)
    versioning_info = get_versioning_info(schema_name)
    
    # Get active data name
    active_data = config.get("active_data") or schema.get("default_data")
    
    # Resolve all data file paths
    resolved_data_files = {}
    for name, rel_path in schema.get("data_files", {}).items():
        resolved_data_files[name] = str(_STORAGE_DIR / rel_path)
    
    # Determine content root for prompt guidance
    content_root = _find_node_by_type(schema.get("nodes", {}), "root")
    
    return {
        "schema_name": schema.get("name"),
        "description": schema.get("description"),
        "hierarchy": schema.get("hierarchy"),
        "nodes": schema.get("nodes", {}),
        "active_data": active_data,
        "data_files": resolved_data_files,
        "examples_file": str(_STORAGE_DIR / schema.get("examples_file", "")),
        "syntax_rules": schema.get("syntax_rules", ""),
        "version_resolver_prompt": schema.get(
            "version_resolver_prompt",
            "prompts/query_generator/version_resolver.txt",
        ),
        "version_schema": version_schema,
        "versioning": versioning_info,
        "content_root": content_root,
    }


def get_node_config(schema_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Get node configuration for NodeUtils.
    
    Args:
        schema_name: Name of the schema. If None, uses active_schema from config.
    
    Returns:
        Dictionary mapping node types to their configuration.
    """
    schema = load_schema(schema_name)
    return schema.get("nodes", {})


def list_available_schemas() -> list:
    """List all available schema names."""
    schemas = set()
    
    # Legacy single-file schemas
    for path in _SCHEMA_DIR.glob("*.yaml"):
        schemas.add(path.stem)
    
    # Folder-based schemas
    for item in _SCHEMA_DIR.iterdir():
        if item.is_dir():
            content_path = item / f"{item.name}.yaml"
            if content_path.exists():
                schemas.add(item.name)
    
    return sorted(schemas)


def list_available_data_files(schema_name: Optional[str] = None) -> list:
    """List available data files for a schema."""
    schema = load_schema(schema_name)
    return list(schema.get("data_files", {}).keys())


def get_schema_summary_for_prompt(schema_name: Optional[str] = None) -> str:
    """
    Generate a schema summary for LLM prompts.
    
    Shows the tree hierarchy with node types and their available fields.
    This helps the LLM understand what information is available at each node
    and determine when to use child vs desc axis.
    
    Args:
        schema_name: Name of the schema. If None, uses active_schema from config.
    
    Returns:
        Formatted string describing the schema structure and fields.
    """
    schema = load_schema(schema_name)
    nodes = schema.get("nodes", {})
    hierarchy = schema.get("hierarchy", "")
    content_root = schema.get("content_root")

    def collect_subtree(root_tag: str) -> Dict[str, Any]:
        if not root_tag or root_tag not in nodes:
            return nodes
        visited = set()
        queue = [root_tag]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            children = nodes.get(current, {}).get("children", [])
            for child in children:
                if child not in visited:
                    queue.append(child)
        return {name: nodes[name] for name in visited if name in nodes}

    def build_hierarchy(root_tag: str, subset: Dict[str, Any]) -> str:
        lines = []

        def label(tag: str) -> str:
            cfg = subset.get(tag, {})
            node_type = cfg.get("type", "leaf")
            index_attr = cfg.get("index_attr")
            if node_type == "root":
                return f"{tag} (root)"
            if node_type == "container":
                if index_attr:
                    return f"{tag} (container, indexed by @{index_attr})"
                return f"{tag} (container)"
            return f"{tag} (leaf)"

        def walk(tag: str, prefix: str, is_last: bool):
            if not prefix:
                lines.append(label(tag))
            else:
                branch = "`-- " if is_last else "|-- "
                lines.append(prefix + branch + label(tag))
            children = subset.get(tag, {}).get("children", [])
            if not children:
                return
            next_prefix = prefix + ("    " if is_last else "|   ")
            for i, child in enumerate(children):
                if child in subset:
                    walk(child, next_prefix, i == len(children) - 1)

        walk(root_tag, "", True)
        return "\n".join(lines)

    lines = []

    if content_root:
        nodes_for_prompt = collect_subtree(content_root)
        hierarchy = build_hierarchy(content_root, nodes_for_prompt)
    else:
        nodes_for_prompt = nodes
    
    def _format_hierarchy(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            def walk(node: Dict[str, Any], prefix: str, is_last: bool) -> List[str]:
                if not node:
                    return []
                tag = next(iter(node))
                children = node.get(tag, {})
                line = tag if not prefix else prefix + ("`-- " if is_last else "|-- ") + tag
                lines_local = [line]
                if isinstance(children, dict) and children:
                    child_items = list(children.items())
                    for idx, (child_tag, child_children) in enumerate(child_items):
                        child_prefix = prefix + ("    " if is_last else "|   ")
                        child_node = {child_tag: child_children}
                        lines_local.extend(walk(child_node, child_prefix, idx == len(child_items) - 1))
                return lines_local
            return "\n".join(walk(value, "", True))
        return ""

    # Include hierarchy visualization if available (helps with axis selection)
    if hierarchy:
        lines.append("Tree Hierarchy (use // to skip intermediate levels):")
        lines.append(_format_hierarchy(hierarchy))
        lines.append("")
    
    lines.append("Node Definitions:")
    lines.append("")
    
    for node_name, node_config in nodes_for_prompt.items():
        node_type = node_config.get("type", "unknown")
        fields = node_config.get("fields", [])
        children = node_config.get("children", [])
        index_attr = node_config.get("index_attr")
        
        # Node header
        if node_type == "root":
            lines.append(f"{node_name} (root)")
        elif node_type == "container":
            if index_attr:
                lines.append(f"{node_name} (container, indexed by @{index_attr})")
            else:
                lines.append(f"{node_name} (container)")
        else:
            lines.append(f"{node_name} (leaf)")
        
        # Fields
        if fields:
            lines.append(f"  Fields: {', '.join(fields)}")
        
        # Children - crucial for axis selection
        if children:
            lines.append(f"  Direct children: {', '.join(children)}")
        
        lines.append("")
    
    return "\n".join(lines)
