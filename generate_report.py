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

    # Find all unique query indices across pipelines to order them
    query_files = set()
    for pipeline in pipelines:
        pipeline_dir = base_dir / pipeline
        if pipeline_dir.exists():
            files = glob.glob(str(pipeline_dir / "query_*_result.json"))
            query_files.update([Path(f).name for f in files])
    
    sorted_files = sorted(list(query_files))

    for file_name in sorted_files:
        query_id = file_name.split('_')[1]
        
        for pipeline in pipelines:
            file_path = base_dir / pipeline / file_name
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
    
    for file_name in sorted_files:
        query_id = file_name.split('_')[1]
        output_lines.append(f"### Query {query_id}")
        
        # Get query text from first available pipeline
        query_text = ""
        for pipeline in pipelines:
             file_path = base_dir / pipeline / file_name
             if file_path.exists():
                 data = load_result_json(file_path)
                 query_text = data.get("query", "")
                 break
        
        output_lines.append(f"**Query:** {query_text}")
        output_lines.append("")
        
        for pipeline in pipelines:
            file_path = base_dir / pipeline / file_name
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
                output_lines.append("**Selected Nodes:**")
                output_lines.append("")
                for idx, node in enumerate(data["selected_nodes"]):
                    output_lines.append(f"**{idx + 1}. {node.get('name', node.get('type', 'Node'))}**")
                    output_lines.extend(format_node_details(node))
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
            if pipeline == "semantic_xpath" and "xpath_execution" in data:
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
