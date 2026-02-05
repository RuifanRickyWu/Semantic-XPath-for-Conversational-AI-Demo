"""
Shared JSON serializers for the Semantic XPath pipeline.

Used by both:
- Direct pipeline access (eval mode) for JSON trace output
- Flask API (demo mode) for HTTP responses

Provides consistent JSON representation of:
- XML trees with optional score annotations
- Pipeline execution results
- CRUD operation traces
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List


def build_tree_path(element: ET.Element, parent_path: str = "") -> str:
    """
    Build a human-readable tree path for an element.
    
    Args:
        element: The XML element
        parent_path: Path of the parent element
        
    Returns:
        Path string like "Itinerary > Day 1 > POI: CN Tower"
    """
    # Get the element's display name
    name_elem = element.find("name")
    if name_elem is not None and name_elem.text:
        display = f"{element.tag}: {name_elem.text}"
    elif element.attrib.get("index"):
        display = f"{element.tag} {element.attrib['index']}"
    else:
        display = element.tag
    
    if parent_path:
        return f"{parent_path} > {display}"
    return display


def serialize_tree(
    root: ET.Element, 
    scores: Optional[Dict[str, float]] = None,
    parent_path: str = ""
) -> Dict[str, Any]:
    """
    Convert XML tree to JSON with optional score annotations.
    
    Args:
        root: The XML element to serialize
        scores: Optional dict mapping tree paths to scores
        parent_path: Path of parent for building full paths
        
    Returns:
        JSON-serializable dictionary representing the tree
    """
    scores = scores or {}
    current_path = build_tree_path(root, parent_path)
    
    # Separate fields (leaf text nodes) from children (container nodes)
    fields = {}
    children = []
    
    for child in root:
        if len(list(child)) == 0 and child.text:
            # Leaf node with text - it's a field
            if child.tag == "highlights":
                # Special handling for highlights list
                fields[child.tag] = child.text
            else:
                fields[child.tag] = child.text
        elif child.tag == "highlights":
            # Handle highlights as a list
            highlights = [h.text for h in child.findall("highlight") if h.text]
            fields["highlights"] = highlights
        else:
            # Container node - recurse
            children.append(serialize_tree(child, scores, current_path))
    
    result = {
        "tag": root.tag,
        "path": current_path,
        "attributes": dict(root.attrib) if root.attrib else {},
    }
    
    if fields:
        result["fields"] = fields
    
    if children:
        result["children"] = children
    
    # Add score if available
    score = scores.get(current_path)
    if score is not None:
        result["score"] = round(score, 4)
    
    return result


def serialize_node(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize a matched node from pipeline results.
    
    Args:
        node_data: Node data from MatchedNode.to_dict()
        
    Returns:
        Cleaned up node data for API response
    """
    result = {
        "path": node_data.get("tree_path", ""),
        "score": round(node_data.get("score", 0), 4),
        "type": node_data.get("node", {}).get("type", ""),
        "name": node_data.get("node", {}).get("name", ""),
    }
    
    # Add optional fields if present
    node = node_data.get("node", {})
    if node.get("description"):
        result["description"] = node["description"]
    if node.get("time_block"):
        result["timeBlock"] = node["time_block"]
    if node.get("expected_cost"):
        result["expectedCost"] = node["expected_cost"]
    if node.get("highlights"):
        result["highlights"] = node["highlights"]
    
    return result


def serialize_timing(timing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize timing information from pipeline execution.
    
    Args:
        timing: Timing dict from StepTimer.to_dict()
        
    Returns:
        Formatted timing data for API response
    """
    steps = timing.get("steps", [])
    return {
        "steps": [
            {
                "step": step.get("step", ""),
                "timeMs": round(step.get("time_ms", 0), 1)
            }
            for step in steps
        ],
        "totalMs": round(timing.get("total_ms", 0), 1)
    }


def serialize_traversal_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize a single traversal step for visualization.
    
    Args:
        step: TraversalStep.to_dict() data
        
    Returns:
        Formatted step data for frontend
    """
    return {
        "stepIndex": step.get("step_index", 0),
        "stepQuery": step.get("step_query", ""),
        "action": step.get("action", ""),
        "nodesBeforeCount": step.get("nodes_before_count", 0),
        "nodesAfterCount": step.get("nodes_after_count", 0),
        "nodesBefore": step.get("nodes_before", []),
        "nodesAfter": step.get("nodes_after", []),
        "details": step.get("details", {})
    }


def serialize_score_fusion(fusion_trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize score fusion trace for visualization.
    
    Args:
        fusion_trace: ScoreFusionTrace.to_dict() data
        
    Returns:
        Formatted fusion data showing per-node score breakdown
    """
    per_node = fusion_trace.get("per_node", [])
    return {
        "perNode": [
            {
                "path": node.get("node_path", ""),
                "type": node.get("node_type", ""),
                "stepContributions": [
                    {
                        "stepIndex": contrib.get("step_index", 0),
                        "predicate": contrib.get("predicate", ""),
                        "score": round(contrib.get("score", 0), 4)
                    }
                    for contrib in node.get("step_contributions", [])
                ],
                "accumulatedProduct": round(node.get("accumulated_product", 1.0), 4),
                "finalScore": round(node.get("final_score", 0), 4)
            }
            for node in per_node
        ]
    }


def serialize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize full pipeline result for API response.
    
    Args:
        result: Result dict from SemanticXPathPipeline.process_request()
        
    Returns:
        JSON-serializable dict for API response
    """
    response = {
        "success": result.get("success", False),
        "operation": result.get("operation", "UNKNOWN"),
        "fullQuery": result.get("full_query", ""),
        "userQuery": result.get("user_query", ""),
        "xpathQuery": result.get("xpath_query", ""),
        "timestamp": result.get("timestamp", ""),
    }
    
    # Add timing
    if "timing" in result:
        response["timing"] = serialize_timing(result["timing"])
    
    # Add intent classification
    if "intent" in result:
        intent = result["intent"]
        response["intent"] = {
            "type": intent.get("intent", ""),
            "confidence": intent.get("confidence", 0),
            "xpathHint": intent.get("xpath_hint", ""),
            "operationDetails": intent.get("operation_details", {})
        }
    
    # Add execution details
    execution = {}
    
    # Candidates and selected nodes
    if "candidates_count" in result:
        execution["candidatesCount"] = result["candidates_count"]
    if "selected_count" in result:
        execution["selectedCount"] = result["selected_count"]
    if "selected_nodes" in result:
        execution["selectedNodes"] = [
            serialize_node({"tree_path": n.get("tree_path", ""), "score": 1.0, "node": n})
            if "tree_path" not in n else serialize_node(n)
            for n in result["selected_nodes"]
        ]
    
    # Reasoning trace
    if "reasoning_trace" in result:
        trace = result["reasoning_trace"]
        execution["reasoning"] = {
            "selectedCount": trace.get("selected_count", 0),
            "rejectedCount": trace.get("rejected_count", 0),
            "decisions": trace.get("decisions", [])
        }
    
    if execution:
        response["execution"] = execution
    
    # Add operation-specific results
    if result.get("operation") == "DELETE":
        response["modification"] = {
            "deletedCount": result.get("deleted_count", 0),
            "deletedPaths": result.get("deleted_paths", [])
        }
    elif result.get("operation") == "UPDATE":
        response["modification"] = {
            "updatedCount": result.get("updated_count", 0),
            "updatedPaths": result.get("updated_paths", []),
            "updateResults": result.get("update_results", [])
        }
    elif result.get("operation") == "CREATE":
        response["modification"] = {
            "createdPath": result.get("created_path"),
            "insertionPoint": result.get("insertion_point", {}),
            "contentResult": result.get("content_result", {})
        }
    
    # Add tree version info
    if "tree_version" in result and result["tree_version"]:
        tv = result["tree_version"]
        response["treeVersion"] = {
            "version": tv.get("version"),
            "path": tv.get("path", ""),
            "operation": tv.get("operation", ""),
            "timestamp": tv.get("timestamp", "")
        }
    
    return response


def serialize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize pipeline configuration for API response.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Formatted config for frontend
    """
    executor_config = config.get("xpath_executor", {})
    return {
        "activeSchema": config.get("active_schema", "itinerary"),
        "activeData": config.get("active_data", ""),
        "mode": config.get("mode", "demo"),
        "executor": {
            "topK": executor_config.get("top_k", 5),
            "scoreThreshold": executor_config.get("score_threshold", 0.5),
            "scoringMethod": executor_config.get("scoring_method", "entailment")
        }
    }
