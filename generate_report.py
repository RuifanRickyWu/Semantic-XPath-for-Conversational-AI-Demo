import argparse
import json
import glob
import os
from pathlib import Path
from typing import Dict, List, Any
import yaml

def load_result_json(file_path: Path) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_token_usage(usage: Dict[str, int]) -> str:
    if not usage:
        return "-"
    p = usage.get('prompt_tokens', 0)
    c = usage.get('completion_tokens', 0)
    t = usage.get('total_tokens', 0)
    return f"{t:,} ({p:,} / {c:,})"

def format_node_details(node: Dict[str, Any], indent: str = "") -> List[str]:
    """Format a node's details as markdown lines."""
    lines = []
    if "name" in node:
        lines.append(f"{indent}- **Name:** {node['name']}")
    if "type" in node:
        lines.append(f"{indent}- **Type:** {node['type']}")
    elif "node_type" in node:
        lines.append(f"{indent}- **Type:** {node['node_type']}")
    if "time_block" in node:
        lines.append(f"{indent}- **Time:** {node['time_block']}")
    if "expected_cost" in node:
        lines.append(f"{indent}- **Cost:** {node['expected_cost']}")
    if "description" in node:
        lines.append(f"{indent}- **Description:** {node['description']}")
    if "highlights" in node and node["highlights"]:
        highlights_str = ", ".join(node["highlights"])
        lines.append(f"{indent}- **Highlights:** {highlights_str}")
    if "reasoning" in node:
        lines.append(f"{indent}- **Reasoning:** {node['reasoning']}")
    if "tree_path" in node:
        lines.append(f"{indent}- **Path:** `{node['tree_path']}`")
    elif "path" in node:
        lines.append(f"{indent}- **Path:** `{node['path']}`")
    return lines


def format_scoring_table(execution_trace: Dict[str, Any]) -> List[str]:
    """Format scoring details as a markdown table."""
    lines = []
    
    # 1. Find the scoring result (try robust paths)
    scoring_result = None
    
    # Path A: explicit scoring_traces list (execution report)
    if "scoring_traces" in execution_trace and execution_trace["scoring_traces"]:
        scoring_result = execution_trace["scoring_traces"][0]
    
    # Path B: traversal steps
    elif "traversal_steps" in execution_trace:
        steps = execution_trace["traversal_steps"]
        if steps and "details" in steps[-1] and "scoring_result" in steps[-1]["details"]:
            scoring_result = steps[-1]["details"]["scoring_result"]
            
    if not scoring_result:
        return lines

    # 2. Extract key metadata
    predicate = scoring_result.get("predicate", "N/A")
    threshold = scoring_result.get("config", {}).get("score_threshold", 0.0)
    
    semantic_values = []
    if "batch_scoring" in scoring_result and "semantic_values" in scoring_result["batch_scoring"]:
        semantic_values = scoring_result["batch_scoring"]["semantic_values"]
    
    # 3. Build Table Header
    # Columns: Node Name | C1 (Value1) | C2 (Value2) | ... | Final Score | Result
    
    # Fallback if no node scores
    node_scores = scoring_result.get("node_scores", [])
    if not node_scores:
        return lines
        
    first_node = node_scores[0]
    
    # Analyze scoring structure of the first node to determine columns
    # Common patterns:
    # 1. AND/OR node: has 'child_scores' list (e.g. [score_a, score_b])
    # 2. NOT node: has 'inner_score' (single value)
    
    scoring_steps = first_node.get("scoring_steps", [])
    child_scores_count = 0
    column_type = "child" # or "inner" or "atomic" or "result_only"
    
    if scoring_steps:
        first_step = scoring_steps[0] # The top-level composition
        if "child_scores" in first_step:
            child_scores_count = len(first_step["child_scores"])
            column_type = "child"
        elif "inner_score" in first_step:
            child_scores_count = 1
            column_type = "inner"
        elif "score" in first_step:
            child_scores_count = 1
            column_type = "atomic"
        elif "result" in first_step:
            child_scores_count = 1
            column_type = "result_only"
    
    # Try to map to semantic values if available
    conditions_header = []
    if semantic_values and len(semantic_values) == child_scores_count:
        for i, val in enumerate(semantic_values):
            conditions_header.append(f"C{i+1} ({val})")
    else:
        # Generic headers if no semantic map or mismatch
        for i in range(child_scores_count):
            if column_type == "inner":
                conditions_header.append("Inner Score")
            elif column_type == "atomic":
                conditions_header.append("Pred Score")
            elif column_type == "result_only":
                conditions_header.append("Agg Score")
            else:
                conditions_header.append(f"C{i+1}")
        
    header = "| Node | " + " | ".join(conditions_header) + " | Final Score | Result |"
    separator = "|---| " + " | ".join(["---"] * len(conditions_header)) + " |---|---|"
    
    lines.append(f"**Predicate:** `{predicate}`")
    lines.append(f"**Threshold:** `{threshold}`")
    lines.append("")
    lines.append(header)
    lines.append(separator)
    
    # 4. detailed rows
    # Sort by node index to keep original order (Day 1, Day 2...)
    sorted_nodes = sorted(node_scores, key=lambda x: x.get("node_idx", 0))
    
    for node in sorted_nodes:
        name = node.get("node_name", "Unknown")
        final_score = node.get("final_score", 0.0)
        
        # Get intermediate scores
        scores_to_display = []
        if "scoring_steps" in node and node["scoring_steps"]:
             step = node["scoring_steps"][0]
             if column_type == "child":
                 scores_to_display = step.get("child_scores", [])
             elif column_type == "inner":
                 scores_to_display = [step.get("inner_score", 0.0)]
             elif column_type == "atomic":
                 scores_to_display = [step.get("score", 0.0)]
             elif column_type == "result_only":
                 scores_to_display = [step.get("result", 0.0)]
        
        # Format scores
        scores_str = [f"{s:.4f}" for s in scores_to_display]
        # Padding if missing
        while len(scores_str) < len(conditions_header):
            scores_str.append("-")
            
        final_score_str = f"{final_score:.4f}"
        
        # Determine Result Status
        passed = final_score >= threshold
        if passed:
            status = "✅ Pass"
        else:
            # Try to identify WHY it failed
            status = "❌ Filtered Out"
            
            # If we have breakdown, find the bottleneck
            if column_type == "child" and scores_to_display:
                 min_val = min(scores_to_display)
                 if abs(min_val - final_score) < 1e-6:
                     # Find which index caused failure
                     for i, s in enumerate(scores_to_display):
                         if s == min_val:
                             if i < len(semantic_values):
                                 status += f" ({semantic_values[i]})"
                             else:
                                 status += f" (C{i+1})"
                             break
            elif column_type == "inner":
                 # For NOT(X), if final score is low, it means inner score was high
                 # so it was filtered out because of specific content
                 if scores_to_display[0] > (1.0 - threshold):
                      status += " (Matches constraint)"
            elif column_type == "atomic":
                 # Simple atomic fail
                 pass 
            elif column_type == "result_only":
                 pass

        row = f"| {name} | " + " | ".join(scores_str) + f" | {final_score_str} | {status} |"
        lines.append(row)

    lines.append("")
    return lines


def extract_semantic_xpath_data(data: Dict[str, Any]) -> Dict[str, Any]:
    raw = data.get("raw_result", {})
    
    # Extract XPath
    xpath = "N/A"
    parsed = raw.get("parsed_query", {})
    if "xpath" in parsed:
        xpath = parsed["xpath"]
    elif "xpath_execution" in raw and "query" in raw["xpath_execution"]:
        xpath = raw["xpath_execution"]["query"]

    # Extract Result Summary
    operation = data.get("operation", "UNKNOWN")
    summary = ""
    
    # Handler output (commonly used for reasoning/details)
    handler_output = raw.get("handler_result", {}).get("output", {})

    if operation == "READ":
        # READ results are typically promoted to top-level "selected_nodes"
        if "selected_nodes" in data and data["selected_nodes"]:
            count = len(data["selected_nodes"])
        elif "selected_nodes" in handler_output:
             count = len(handler_output["selected_nodes"])
        else:
            count = data.get("selected_count", 0)
        summary = f"Selected {count} nodes"
        
    elif operation == "DELETE":
        # DELETE count/paths often in raw_result or handler output
        if "deleted_count" in raw and raw["deleted_count"]:
            count = raw["deleted_count"]
        elif "deleted_paths" in raw and raw["deleted_paths"]:
            count = len(raw["deleted_paths"])
        elif "nodes_to_delete" in handler_output:
            count = len(handler_output["nodes_to_delete"])
        elif "deleted_paths" in handler_output:
             count = len(handler_output["deleted_paths"])
        else:
             count = data.get("deleted_count", 0)
        summary = f"Deleted {count} nodes"
        
    elif operation == "UPDATE":
        if "updated_count" in raw and raw["updated_count"]:
            count = raw["updated_count"]
        elif "updated_paths" in raw and raw["updated_paths"]:
            count = len(raw["updated_paths"])
        elif "updates" in handler_output:
            count = len(handler_output["updates"])
        else:
            count = data.get("updated_count", 0)
        summary = f"Updated {count} nodes"
        
    elif operation == "CREATE":
        path = raw.get("created_path")
        if not path:
             path = data.get("created_path")
        if not path and "parent_path" in handler_output and "node_type" in handler_output:
             path = f"{handler_output['parent_path']}/{handler_output['node_type']}"
        
        if not path:
             path = "unknown"
        summary = f"Created at {path}"
    else:
        summary = data.get("error", "Unknown result")

    # Extract Tokens
    token_usage = {}
    if "timing" in data and "total_tokens" in data["timing"]:
        token_usage = data["timing"]["total_tokens"]
    elif "token_usage" in data:
        token_usage = data["token_usage"]

    # Extract Time
    time_ms = 0
    if "timing" in data:
        time_ms = data["timing"].get("pipeline_total_ms", 0)
        if time_ms == 0:
            time_ms = data["timing"].get("total_time_ms", 0)
    else:
        time_ms = data.get("execution_time_ms", 0)

    return {
        "xpath": xpath,
        "result": summary,
        "token_usage": token_usage,
        "time_ms": time_ms,
        "operation": operation
    }

def extract_incontext_data(data: Dict[str, Any]) -> Dict[str, Any]:
    # XPath is N/A for incontext
    xpath = "N/A (Full Tree)"

    # Extract Result Summary
    operation = data.get("operation", "UNKNOWN")
    summary = ""
    
    if "diff" in data and data["diff"]:
        summary = data["diff"].get("summary", "")
    elif "error" in data:
        summary = f"Error: {data['error']}"
    else:
        summary = data.get("reasoning", "")

    # Extract Tokens
    token_usage = data.get("token_usage", {})

    # Extract Time
    time_ms = data.get("execution_time_ms", 0)

    return {
        "xpath": xpath,
        "result": summary,
        "token_usage": token_usage,
        "time_ms": time_ms,
        "operation": operation
    }

def generate_markdown_report(experiment_name: str, pipelines: List[str]):
    base_dir = Path(__file__).parent / "experiment_results" / experiment_name
    
    if not base_dir.exists():
        print(f"Experiment directory not found: {base_dir}")
        return

    output_lines = [
        f"# Experiment Report: {experiment_name}",
        "",
        "## Summary",
        "",
        "| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |",
        "|---|---|---|---|---|---|---|"
    ]

    # Find all unique query folders across pipelines to order them
    query_folders = set()
    for pipeline in pipelines:
        pipeline_dir = base_dir / pipeline
        if pipeline_dir.exists():
            # New structure: query_XXX/result.json
            folders = glob.glob(str(pipeline_dir / "query_*"))
            for folder in folders:
                if Path(folder).is_dir():
                    query_folders.add(Path(folder).name)
            # Also check for legacy flat structure: query_XXX_result.json
            files = glob.glob(str(pipeline_dir / "query_*_result.json"))
            for f in files:
                # Extract query number and convert to folder name format
                query_num = Path(f).name.split('_')[1]
                query_folders.add(f"query_{query_num}")
    
    sorted_folders = sorted(list(query_folders))

    for folder_name in sorted_folders:
        query_id = folder_name.split('_')[1]
        
        for pipeline in pipelines:
            # Try new structure first: query_XXX/result.json
            file_path = base_dir / pipeline / folder_name / "result.json"
            if not file_path.exists():
                # Fall back to legacy structure: query_XXX_result.json
                file_path = base_dir / pipeline / f"{folder_name}_result.json"
            if not file_path.exists():
                continue
            
            data = load_result_json(file_path)
            
            if pipeline == "semantic_xpath":
                info = extract_semantic_xpath_data(data)
            elif pipeline == "incontext":
                info = extract_incontext_data(data)
            else:
                info = {
                    "xpath": "-", 
                    "result": "Unknown Pipeline", 
                    "token_usage": {}, 
                    "time_ms": 0, 
                    "operation": "?"
                }
            
            # Format row
            query_preview = data.get("query", "")[:50].replace("\n", " ") + "..." if len(data.get("query", "")) > 50 else data.get("query", "")
            if "|" in query_preview:
                query_preview = query_preview.replace("|", r"\|")
            
            xpath_code = f"`{info['xpath']}`" if info['xpath'] != "N/A" else "Full Tree"
            if len(xpath_code) > 60:
                 xpath_code = xpath_code[:50] + "...`"

            result_str = info['result']
            if len(result_str) > 50:
                result_str = result_str[:47] + "..."
            
            token_str = format_token_usage(info['token_usage'])
            time_str = f"{info['time_ms'] / 1000:.2f}"
            
            row = f"| {query_id} | {pipeline} | {info['operation']} | {xpath_code} | {result_str} | {token_str} | {time_str} |"
            output_lines.append(row)
            
            # Add a row for the full query text if desired, or keep it compact. 
            # For now, let's just keep the table row.

    # Detailed sections (Optional)
    output_lines.append("")
    output_lines.append("## Detailed Results")
    
    for folder_name in sorted_folders:
        query_id = folder_name.split('_')[1]
        output_lines.append(f"### Query {query_id}")
        
        # Get query text from first available pipeline
        query_text = ""
        for pipeline in pipelines:
            # Try new structure first
            file_path = base_dir / pipeline / folder_name / "result.json"
            if not file_path.exists():
                # Fall back to legacy structure
                file_path = base_dir / pipeline / f"{folder_name}_result.json"
            if file_path.exists():
                data = load_result_json(file_path)
                query_text = data.get("query", "")
                break
        
        output_lines.append(f"**Query:** {query_text}")
        output_lines.append("")
        
        for pipeline in pipelines:
            # Try new structure first
            file_path = base_dir / pipeline / folder_name / "result.json"
            if not file_path.exists():
                # Fall back to legacy structure
                file_path = base_dir / pipeline / f"{folder_name}_result.json"
            if not file_path.exists():
                continue
                
            data = load_result_json(file_path)
            if pipeline == "semantic_xpath":
                info = extract_semantic_xpath_data(data)
            else:
                info = extract_incontext_data(data)

            output_lines.append(f"#### {pipeline}")
            output_lines.append(f"- **Operation:** {info['operation']}")
            output_lines.append(f"- **Logic/XPath:** `{info['xpath']}`")
            output_lines.append(f"- **Result:** {info['result']}")
            output_lines.append(f"- **Time:** {info['time_ms'] / 1000:.2f}s")
            output_lines.append(f"- **Tokens:** {format_token_usage(info['token_usage'])}")
            if "error" in data:
                output_lines.append(f"- **Error:** {data['error']}")
            output_lines.append("")

            # Display relevant nodes based on operation type
            operation = data.get("operation", "")
            
            if operation == "READ" and "selected_nodes" in data and data["selected_nodes"]:
                
                # Check if nodes need parsing (incontext pipeline returns raw XML)
                nodes_to_display = []
                for node in data["selected_nodes"]:
                    if "xml" in node and len(node) == 1:
                         # Parse the XML content
                         import xml.etree.ElementTree as ET
                         try:
                             # Wrap in wrapper to allow multiple roots
                             xml_content = node["xml"]
                             if xml_content.startswith("```"):
                                 xml_content = xml_content.split("\n", 1)[1].rsplit("\n", 1)[0]
                             
                             root = ET.fromstring(f"<wrapper>{xml_content}</wrapper>")
                             
                             def generic_element_to_dict(elem):
                                 """Recursively convert XML element to dict."""
                                 data = {}
                                 # Attributes
                                 data.update(elem.attrib)
                                 
                                 # Children
                                 child_counts = {}
                                 for child in elem:
                                     child_counts[child.tag] = child_counts.get(child.tag, 0) + 1
                                 
                                 for child in elem:
                                     # Check if this child tag appears multiple times (structurally a list)
                                     is_list_item = child_counts[child.tag] > 1
                                     
                                     child_val = None
                                     if len(child) == 0:
                                         child_val = child.text.strip() if child.text else ""
                                     else:
                                         child_val = generic_element_to_dict(child)
                                     
                                     if is_list_item:
                                         if child.tag not in data:
                                             data[child.tag] = []
                                         if isinstance(data[child.tag], list):
                                             data[child.tag].append(child_val)
                                         else:
                                              data[child.tag] = [data[child.tag], child_val]
                                     else:
                                         data[child.tag] = child_val
                                 return data

                             for child in root:
                                 # Top level nodes (e.g. Day, or POI)
                                 node_data = generic_element_to_dict(child)
                                 node_data["type"] = child.tag
                                 
                                 # If it has sub-children that look like nodes, extract them for better display
                                 sub_nodes = []
                                 keys_to_remove = []
                                 
                                 for key, val in node_data.items():
                                     if isinstance(val, list):
                                         # Check if list of dicts (complex objects)
                                         if val and isinstance(val[0], dict):
                                            # Treat as sub-nodes to display indented
                                            for item in val:
                                                item["type"] = key  # Use tag as type
                                                item["indent"] = True
                                                sub_nodes.append(item)
                                            keys_to_remove.append(key)
                                     elif isinstance(val, dict):
                                         # complex child
                                         val["type"] = key
                                         val["indent"] = True
                                         sub_nodes.append(val)
                                         keys_to_remove.append(key)
                                 
                                 # Remove the moved keys so they don't duplicate
                                 for k in keys_to_remove:
                                     del node_data[k]
                                     
                                 nodes_to_display.append(node_data)
                                 nodes_to_display.extend(sub_nodes)

                         except Exception as e:
                             nodes_to_display.append({"name": "Error Parsing XML Node", "description": str(e)})
                    else:
                        nodes_to_display.append(node)

                output_lines.append("**Selected Nodes:**")
                output_lines.append("")
                
                for idx, node in enumerate(nodes_to_display):
                    indent = node.get("indent", False)
                    prefix_num = f"{idx + 1}."
                    
                    type_str = node.get('type', 'Node')
                    name_str = node.get('name', 'Unknown')
                    
                    # Construct Identity
                    identity = ""
                    if name_str and name_str != "Unknown":
                        identity = name_str
                    elif "index" in node:
                        identity = f"Index: {node['index']}"
                    
                    # Construct Details (everything else)
                    details = []
                    # Common keys to show first
                    priority_keys = ["time_block", "cost", "expected_cost", "travel_method"]
                    for k in priority_keys:
                        if k in node and node[k]:
                            details.append(f"{node[k]}")
                    
                    # Add other short keys
                    for k, v in node.items():
                        ignore_keys = ["name", "type", "indent", "node_type", "xml", "highlights", "description", "index", "id"]
                        if k not in ignore_keys and k not in priority_keys:
                             val_str = str(v)
                             if len(val_str) < 30: # Only show short values
                                 details.append(f"{val_str}")
                    
                    details_str = f" ({', '.join(details)})" if details else ""
                    
                    # Format
                    if indent:
                         display_line = f"{prefix_num}   - **{type_str}** -> {identity}{details_str}"
                    else:
                         display_line = f"{prefix_num} **{type_str}** -> {identity}{details_str}"
                    
                    output_lines.append(display_line)
                
                output_lines.append("")
            
            elif operation == "DELETE" and "changes" in data and data["changes"]:
                output_lines.append("**Deleted Nodes:**")
                output_lines.append("")
                for change in data["changes"]:
                    if change.get("change_type") == "deleted":
                        path = change.get("path", "Unknown path")
                        output_lines.append(f"- `{path}`")
                output_lines.append("")
            
            elif operation == "CREATE" and "changes" in data and data["changes"]:
                output_lines.append("**Created Nodes:**")
                output_lines.append("")
                for change in data["changes"]:
                    if change.get("change_type") == "created" and "new_node" in change:
                        new_node = change["new_node"]
                        path = change.get("path", "")
                        output_lines.append(f"**Path:** `{path}`")
                        if "fields" in new_node:
                            output_lines.extend(format_node_details(new_node["fields"]))
                        output_lines.append("")

            # Special section for XPath execution details
            if pipeline == "semantic_xpath":
                # Look for execution trace file to get scoring details
                # It should be in query_XXX/reasoning_traces/execution_*.json
                
                # Check current directory structure first
                trace_dir = base_dir / pipeline / folder_name / "reasoning_traces"
                execution_trace = None
                
                if trace_dir.exists():
                    trace_files = glob.glob(str(trace_dir / "execution_*.json"))
                    if trace_files:
                        # Sort by name (timestamp) and take the last one
                        trace_files.sort()
                        execution_trace = load_result_json(Path(trace_files[-1]))
                
                if execution_trace:
                     scoring_table = format_scoring_table(execution_trace)
                     if scoring_table:
                         output_lines.append("**Scoring Analysis:**")
                         output_lines.append("")
                         output_lines.extend(scoring_table)
                if "xpath_execution" in data:
                    output_lines.append("<details>")
                    output_lines.append("<summary>Execution Details</summary>")
                    output_lines.append("")
                    output_lines.append(f"- Matched Nodes: {data['xpath_execution'].get('matched_count', 0)}")
                    output_lines.append(f"- Execution Time: {data['xpath_execution'].get('execution_time_ms', 0)}ms")
                    output_lines.append("</details>")
                output_lines.append("")

    report_path = base_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    
    print(f"Report generated at: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Markdown report from experiment results.")
    parser.add_argument("--experiment_name", type=str, required=True, help="Name of the experiment folder")
    parser.add_argument("--pipelines", type=str, nargs="+", default=["semantic_xpath", "incontext"], help="List of pipelines to include")
    
    args = parser.parse_args()
    
    generate_markdown_report(args.experiment_name, args.pipelines)
