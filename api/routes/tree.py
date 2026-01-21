"""
Tree state endpoints.

GET /api/tree - Get current tree state
GET /api/tree/versions - List all tree versions  
GET /api/tree/version/<id> - Get specific version
POST /api/tree/reset - Reset tree to original state
"""

from flask import Blueprint, jsonify, current_app
from pathlib import Path
import json

from pipeline.serializers import serialize_tree

bp = Blueprint("tree", __name__)


@bp.route("", methods=["GET"])
def get_tree():
    """
    Get the current tree state as JSON.
    
    Returns:
        Serialized tree with node structure
    """
    pipeline = current_app.pipeline
    
    try:
        tree_data = serialize_tree(pipeline.executor.tree.getroot())
        return jsonify({
            "success": True,
            "tree": tree_data,
            "dataFile": pipeline.executor.memory_path.name
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@bp.route("/versions", methods=["GET"])
def list_versions():
    """
    List all saved tree versions.
    
    Returns:
        List of version metadata
    """
    pipeline = current_app.pipeline
    
    try:
        # Get versions from the version manager
        versions = pipeline.executor.version_manager.list_versions(
            pipeline.executor.memory_path
        )
        
        return jsonify({
            "success": True,
            "versions": versions
        })
    except Exception as e:
        # If no versions exist yet, return empty list
        return jsonify({
            "success": True,
            "versions": []
        })


@bp.route("/version/<int:version_id>", methods=["GET"])
def get_version(version_id: int):
    """
    Get a specific tree version.
    
    Args:
        version_id: Version number to retrieve
        
    Returns:
        Serialized tree at that version
    """
    pipeline = current_app.pipeline
    
    try:
        # Build version file path
        base_name = pipeline.executor.memory_path.stem
        result_dir = Path(__file__).parent.parent.parent / "result" / "demo"
        version_file = result_dir / f"{base_name}_v{version_id}.xml"
        
        if not version_file.exists():
            return jsonify({
                "error": f"Version {version_id} not found",
                "success": False
            }), 404
        
        import xml.etree.ElementTree as ET
        tree = ET.parse(version_file)
        tree_data = serialize_tree(tree.getroot())
        
        return jsonify({
            "success": True,
            "version": version_id,
            "tree": tree_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@bp.route("/reset", methods=["POST"])
def reset_tree():
    """
    Reset the tree to its original state.
    
    Returns:
        Fresh tree state
    """
    pipeline = current_app.pipeline
    
    try:
        # Reload from original file
        pipeline.executor.reload_tree()
        
        # Get fresh tree state
        tree_data = serialize_tree(pipeline.executor.tree.getroot())
        
        return jsonify({
            "success": True,
            "message": "Tree reset to original state",
            "tree": tree_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500
