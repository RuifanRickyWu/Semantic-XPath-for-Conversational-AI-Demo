"""
Schema Loader - Loads tree schema configurations.

Provides functions to load schema definitions and resolve data file paths.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


# Base directories
_BASE_DIR = Path(__file__).parent.parent
_SCHEMA_DIR = _BASE_DIR / "storage" / "schemas"
_STORAGE_DIR = _BASE_DIR / "storage"


def load_config() -> Dict[str, Any]:
    """Load the main config.yaml file."""
    config_path = _BASE_DIR / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_schema(schema_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a schema definition by name.
    
    Args:
        schema_name: Name of the schema (e.g., "itinerary"). 
                    If None, uses active_schema from config.yaml.
    
    Returns:
        Schema dictionary with node definitions, data files, etc.
    """
    if schema_name is None:
        config = load_config()
        schema_name = config.get("active_schema", "itinerary")
    
    schema_path = _SCHEMA_DIR / f"{schema_name}.yaml"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)


def get_data_path(
    data_name: Optional[str] = None, 
    schema_name: Optional[str] = None
) -> Path:
    """
    Get the full path to a data file.
    
    Args:
        data_name: Name of the data file (e.g., "travel_memory_5day").
                  If None, uses active_data from config.yaml or schema's default.
        schema_name: Name of the schema. If None, uses active_schema from config.
    
    Returns:
        Full Path to the data file.
    """
    config = load_config()
    schema = load_schema(schema_name)
    
    # Determine which data file to use
    if data_name is None:
        # First check config.yaml for active_data
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
    
    # Get active data name
    active_data = config.get("active_data") or schema.get("default_data")
    
    # Resolve all data file paths
    resolved_data_files = {}
    for name, rel_path in schema.get("data_files", {}).items():
        resolved_data_files[name] = str(_STORAGE_DIR / rel_path)
    
    return {
        "schema_name": schema.get("name"),
        "description": schema.get("description"),
        "hierarchy": schema.get("hierarchy"),
        "nodes": schema.get("nodes", {}),
        "active_data": active_data,
        "data_files": resolved_data_files,
        "prompt_file": str(_STORAGE_DIR / schema.get("prompt_file", ""))
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
    schemas = []
    for path in _SCHEMA_DIR.glob("*.yaml"):
        schemas.append(path.stem)
    return schemas


def list_available_data_files(schema_name: Optional[str] = None) -> list:
    """List available data files for a schema."""
    schema = load_schema(schema_name)
    return list(schema.get("data_files", {}).keys())

