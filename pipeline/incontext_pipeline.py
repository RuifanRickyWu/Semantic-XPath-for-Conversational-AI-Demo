"""
In-Context Pipeline - Single-LLM CRUD Pipeline for tree operations.

Provides a simplified CRUD interface that sends the full XML tree to the LLM
in a single call, rather than using multi-stage XPath query processing.

Key Features:
- Single LLM call with full tree in context
- Automatic CRUD intent detection
- XML diff calculation for CUD operations (non-LLM)
- Complete token usage tracking

Pipeline:
1. Load XML tree and system prompt
2. Send user request + full tree to LLM
3. Parse response (operation type + result)
4. For CUD: Calculate diff between original and modified tree
5. Return structured result with token usage
"""

import json
import yaml
import time
import difflib
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_default_client, TokenUsage, CompletionResult
from client.openai_client import load_config


@dataclass
class NodeDiff:
    """Represents a change to a single node (POI or Restaurant)."""
    change_type: str  # "created", "deleted", "modified"
    node_type: str    # "POI" or "Restaurant"
    day: str          # Day index
    name: str         # Node name
    old_data: Optional[Dict[str, Any]] = None  # Full node data before
    new_data: Optional[Dict[str, Any]] = None  # Full node data after
    changed_fields: Optional[Dict[str, Dict[str, str]]] = None  # For modifications
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "change_type": self.change_type,
            "node_type": self.node_type,
            "day": self.day,
            "name": self.name
        }
        if self.old_data:
            result["old_data"] = self.old_data
        if self.new_data:
            result["new_data"] = self.new_data
        if self.changed_fields:
            result["changed_fields"] = self.changed_fields
        return result


@dataclass
class DiffResult:
    """Result of comparing two XML trees at the node level."""
    summary: str
    created_nodes: List[NodeDiff]
    deleted_nodes: List[NodeDiff]
    modified_nodes: List[NodeDiff]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "created_nodes": [n.to_dict() for n in self.created_nodes],
            "deleted_nodes": [n.to_dict() for n in self.deleted_nodes],
            "modified_nodes": [n.to_dict() for n in self.modified_nodes]
        }


@dataclass
class PipelineResult:
    """Complete result from the incontext pipeline."""
    operation: str
    success: bool
    version_used: int
    reasoning: str
    result_xml: str
    diff: Optional[DiffResult] = None
    token_usage: Optional[TokenUsage] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    new_version: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        output = {
            "operation": self.operation,
            "success": self.success,
            "version_used": self.version_used,
            "reasoning": self.reasoning,
            "result": self.result_xml,
            "execution_time_ms": round(self.execution_time_ms, 2)
        }
        if self.new_version:
            output["new_version"] = self.new_version
        if self.diff:
            output["diff"] = self.diff.to_dict()
        if self.token_usage:
            output["token_usage"] = self.token_usage.to_dict()
        if self.error:
            output["error"] = self.error
        return output


class IncontextPipeline:
    """
    Single-LLM CRUD Pipeline with full XML tree in context.
    
    Instead of multi-stage XPath query processing, this pipeline:
    1. Sends the entire XML tree to the LLM
    2. Lets the LLM identify CRUD intent and process accordingly
    3. Calculates diff locally for modification operations
    4. Persists changes as new versions in the XML tree
    
    Trade-offs vs. Semantic XPath Pipeline:
    - Simpler architecture (single LLM call)
    - Higher token usage for large trees
    - More direct LLM reasoning over full context
    """
    
    def __init__(self, tree_path: Path = None, config_override: Dict[str, Any] = None):
        """Initialize the pipeline."""
        self.config = load_config()
        self.client = get_default_client()
        
        # Load pipeline-specific LLM settings
        pipeline_config = self.config.get("incontext_pipeline", {})
        self.temperature = pipeline_config.get("temperature", 0.3)
        self.max_tokens = pipeline_config.get("max_tokens", 16384)
        
        # Override config if provided
        self.config_override = config_override or {}
        self.input_mode = self.config_override.get("input_mode", "full")
        
        # Load paths
        base_path = Path(__file__).parent.parent
        self.prompts_path = base_path / "storage" / "prompts"
        
        # Determine tree path and base directory for VersionManager
        if tree_path:
            self.tree_path = Path(tree_path)
            vm_base_dir = self.tree_path.parent
        else:
            self.memory_path = base_path / "storage" / "memory"
            self.tree_path = None  # Will be resolved via _get_tree_path()
            vm_base_dir = self.memory_path / "travel"
        
        # Initialize Version Manager
        # Lazy import to avoid circular dependencies if any
        from tree_modification.version_manager import VersionManager
        self.version_manager = VersionManager(base_directory=vm_base_dir)
        
        # Load the system prompt
        self.system_prompt = self._load_prompt()
        
        # Load tree based on config if not provided
        if self.tree_path is None:
            self.tree_path = self._get_tree_path()
        self.tree = None
        self.original_xml = None
        
        # Session statistics
        self.session_stats = {
            "operations": 0,
            "reads": 0,
            "creates": 0,
            "updates": 0,
            "deletes": 0,
            "versions_created": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0
        }
    
    def _load_prompt(self) -> str:
        """Load the system prompt from file."""
        prompt_path = self.prompts_path / "incontext_pipeline.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _get_tree_path(self) -> Path:
        """Get the path to the XML tree based on config."""
        active_schema = self.config.get("active_schema", "itinerary")
        active_data = self.config.get("active_data", "travel_memory_3day")
        
        # Map schema to subdirectory
        schema_dirs = {
            "itinerary": "travel",
            "todolist": "todo_list"
        }
        subdir = schema_dirs.get(active_schema, "travel")
        
        return self.memory_path / subdir / f"{active_data}.xml"
    
    def _load_tree(self) -> Tuple[ET.ElementTree, str]:
        """Load the XML tree and return both parsed tree and raw XML."""
        with open(self.tree_path, "r", encoding="utf-8") as f:
            raw_xml = f.read()
        tree = ET.parse(self.tree_path)
        return tree, raw_xml
    
    def _get_latest_version_xml(self) -> str:
        """Extract the latest version's itinerary content as XML string."""
        if self.tree is None:
            self.tree, self.original_xml = self._load_tree()
        
        root = self.tree.getroot()
        
        # Find all versions and get the latest
        versions = root.findall(".//Itinerary_Version")
        if not versions:
            # Check for legacy "Version" tag
            versions = root.findall(".//Version")

        if not versions:
            # No versions? Fallback to raw xml (likely wrong structure but best effort)
            return self.original_xml
        
        # Sort by version number
        latest = max(versions, key=lambda v: int(v.get("number", "0")))
        
        # Serialize the version for the prompt
        return ET.tostring(latest, encoding="unicode")
    
    def _parse_content_nodes(self, xml_string: str) -> List[ET.Element]:
        """
        Parse XML string into a list of Element nodes.
        Used for parsing the LLM's 'result' output which contains children of Itinerary.
        """
        nodes = []
        try:
            # Wrap in a root if needed
            if not xml_string.strip().startswith('<'):
                return nodes
            
            # Use 'Itinerary' wrapper to match structure
            root = ET.fromstring(f"<Itinerary>{xml_string}</Itinerary>")
            nodes = list(root)
        except ET.ParseError:
            pass
        return nodes

    def process_request(self, user_request: str) -> PipelineResult:
        """
        Process a user request as a CRUD operation.
        
        Args:
            user_request: Natural language request from the user
            
        Returns:
            PipelineResult with operation results, diff, and token usage
        """
        start_time = time.perf_counter()
        
        # Load/refresh the tree
        self.tree, self.original_xml = self._load_tree()
        
        # Get the latest version XML for diff calculation
        latest_version_xml = self._get_latest_version_xml()
        
        # Determine context based on input_mode
        if self.input_mode == "latest":
            xml_context = latest_version_xml
            # Add a wrapper if needed to make it look like a tree root, or just pass the Version element
            # The system expects "conversational history tree". Passing one version is a valid (short) history.
        else:
            # Default: Full tree (all versions)
            xml_context = self.original_xml
        
        # Build the user message
        user_message = f"""## XML Tree
{xml_context}

## User Request

{user_request}"""

        # Call LLM with token tracking (using pipeline-specific settings)
        try:
            result = self.client.complete_with_usage(
                prompt=user_message,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
        except Exception as e:
            return PipelineResult(
                operation="ERROR",
                success=False,
                version_used=0,
                reasoning="",
                result_xml="",
                error=f"LLM call failed: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        # Parse the response
        try:
            parsed = self._parse_response(result.content)
        except Exception as e:
            return PipelineResult(
                operation="ERROR",
                success=False,
                version_used=0,
                reasoning="",
                result_xml=result.content,
                error=f"Failed to parse LLM response: {str(e)}",
                token_usage=result.usage,
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        operation = parsed.get("operation", "UNKNOWN")
        version_used = parsed.get("version_used", 1)
        reasoning = parsed.get("reasoning", "")
        result_xml = parsed.get("result", "")
        
        # Calculate diff for CUD operations
        diff_result = None
        new_version_num = None
        
        if operation in ("CREATE", "UPDATE", "DELETE"):
            diff_result = self._calculate_diff(latest_version_xml, result_xml)
            
            # Persist changes: Create a new version
            try:
                # 1. Parse the result XML into elements
                new_content = self._parse_content_nodes(result_xml)
                
                if new_content:
                    # 2. Get the source version
                    source_version = self.version_manager.get_version_by_number(self.tree, version_used)
                    if not source_version:
                        # Fallback to latest if specified version not found
                        source_version = self.version_manager.get_latest_version(self.tree)
                    
                    if source_version:
                        # 3. Create the new version
                        new_version_elem = self.version_manager.create_new_version(
                            tree=self.tree,
                            source_version=source_version,
                            patch_info=reasoning,
                            conversation_history=user_request,
                            modified_content=new_content
                        )
                        new_version_num = int(new_version_elem.get("number"))
                        
                        # 4. Save the tree
                        self.version_manager.save_tree(
                            tree=self.tree, 
                            original_path=self.tree_path
                        )
            except Exception as e:
                # Log error but don't fail the pipeline result completely, just mark error
                parsed["error"] = f"Failed to persist version: {e}"
        
        # Update session stats
        self._update_stats(operation, result.usage, new_version_num)
        
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        return PipelineResult(
            operation=operation,
            success=True,
            version_used=version_used,
            reasoning=reasoning,
            result_xml=result_xml,
            diff=diff_result,
            token_usage=result.usage,
            execution_time_ms=execution_time_ms,
            new_version=new_version_num,
            error=parsed.get("error")
        )
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM's JSON response."""
        # Try to extract JSON from the response
        response = response.strip()
        
        # Handle markdown code blocks
        if response.startswith("```"):
            # Remove code block markers
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)
        
        # Parse JSON
        return json.loads(response)
    
    def _calculate_diff(self, original_xml: str, modified_xml: str) -> DiffResult:
        """
        Calculate the difference between original and modified XML at the node level.
        
        Compares POI and Restaurant nodes, not individual lines.
        """
        # Extract nodes from both trees
        original_nodes = self._extract_nodes(original_xml)
        modified_nodes = self._extract_nodes(modified_xml)
        
        created_nodes = []
        deleted_nodes = []
        modified_nodes_list = []
        
        # Build lookup by (day, node_type, name)
        original_lookup = {(n['day'], n['type'], n['name']): n for n in original_nodes}
        modified_lookup = {(n['day'], n['type'], n['name']): n for n in modified_nodes}
        
        # Find deleted nodes (in original but not in modified)
        for key, node in original_lookup.items():
            if key not in modified_lookup:
                deleted_nodes.append(NodeDiff(
                    change_type="deleted",
                    node_type=node['type'],
                    day=node['day'],
                    name=node['name'],
                    old_data=node['data']
                ))
        
        # Find created and modified nodes
        for key, node in modified_lookup.items():
            if key not in original_lookup:
                # New node
                created_nodes.append(NodeDiff(
                    change_type="created",
                    node_type=node['type'],
                    day=node['day'],
                    name=node['name'],
                    new_data=node['data']
                ))
            else:
                # Check for modifications
                old_node = original_lookup[key]
                changed_fields = {}
                
                for field in set(node['data'].keys()) | set(old_node['data'].keys()):
                    old_val = old_node['data'].get(field)
                    new_val = node['data'].get(field)
                    if old_val != new_val:
                        changed_fields[field] = {
                            "from": old_val,
                            "to": new_val
                        }
                
                if changed_fields:
                    modified_nodes_list.append(NodeDiff(
                        change_type="modified",
                        node_type=node['type'],
                        day=node['day'],
                        name=node['name'],
                        old_data=old_node['data'],
                        new_data=node['data'],
                        changed_fields=changed_fields
                    ))
        
        # Generate summary
        summary_parts = []
        if created_nodes:
            summary_parts.append(f"{len(created_nodes)} node(s) created")
        if deleted_nodes:
            summary_parts.append(f"{len(deleted_nodes)} node(s) deleted")
        if modified_nodes_list:
            summary_parts.append(f"{len(modified_nodes_list)} node(s) modified")
        summary = ", ".join(summary_parts) if summary_parts else "No changes detected"
        
        return DiffResult(
            summary=summary,
            created_nodes=created_nodes,
            deleted_nodes=deleted_nodes,
            modified_nodes=modified_nodes_list
        )
    
    def _extract_nodes(self, xml_string: str) -> List[Dict[str, Any]]:
        """Extract POI and Restaurant nodes from XML string."""
        nodes = []
        
        try:
            # Wrap in a root if needed
            if not xml_string.strip().startswith('<'):
                return nodes
            
            # Try to parse - handle both full tree and just Days
            try:
                root = ET.fromstring(f"<wrapper>{xml_string}</wrapper>")
            except ET.ParseError:
                return nodes
            
            # Find all Day elements
            for day_elem in root.iter('Day'):
                day_index = day_elem.get('index', '?')
                
                # Extract POIs
                for poi in day_elem.findall('POI'):
                    node_data = self._element_to_dict(poi)
                    nodes.append({
                        'type': 'POI',
                        'day': day_index,
                        'name': node_data.get('name', 'Unknown'),
                        'data': node_data
                    })
                
                # Extract Restaurants
                for restaurant in day_elem.findall('Restaurant'):
                    node_data = self._element_to_dict(restaurant)
                    nodes.append({
                        'type': 'Restaurant',
                        'day': day_index,
                        'name': node_data.get('name', 'Unknown'),
                        'data': node_data
                    })
        
        except Exception:
            pass
        
        return nodes
    
    def _element_to_dict(self, elem: ET.Element) -> Dict[str, Any]:
        """Convert an XML element to a dictionary."""
        result = {}
        
        for child in elem:
            if child.tag == 'highlights':
                result['highlights'] = [h.text.strip() for h in child if h.text]
            elif len(child) == 0:
                result[child.tag] = child.text.strip() if child.text else ''
            else:
                result[child.tag] = self._element_to_dict(child)
        
        return result
    
    def _update_stats(self, operation: str, usage: TokenUsage, new_version: int = None):
        """Update session statistics."""
        self.session_stats["operations"] += 1
        
        op_key = operation.lower() + "s"
        if op_key in self.session_stats:
            self.session_stats[op_key] += 1
        
        if new_version:
            self.session_stats["versions_created"] += 1
            
        self.session_stats["total_prompt_tokens"] += usage.prompt_tokens
        self.session_stats["total_completion_tokens"] += usage.completion_tokens
    
    def format_result(self, result: PipelineResult) -> str:
        """Format the result for display."""
        lines = []
        
        status_icon = "✅" if result.success else "❌"
        lines.append(f"\n{status_icon} {result.operation} Operation {'Succeeded' if result.success else 'Failed'}")
        lines.append("=" * 60)
        
        lines.append(f"📌 Version Used: {result.version_used}")
        if result.new_version:
            lines.append(f"🆕 New Version: {result.new_version}")
            
        lines.append(f"⏱️  Time: {result.execution_time_ms:.1f}ms")
        
        if result.token_usage:
            lines.append(f"🔢 Tokens: {result.token_usage.prompt_tokens} prompt + {result.token_usage.completion_tokens} completion = {result.token_usage.total_tokens} total")
        
        lines.append(f"\n💭 Reasoning: {result.reasoning}")
        
        # Show diff for CUD operations
        if result.diff:
            lines.append(f"\n📊 Changes: {result.diff.summary}")
            
            if result.diff.created_nodes:
                lines.append("\n➕ Created:")
                for node in result.diff.created_nodes[:5]:
                    lines.append(f"   {node.node_type}: {node.name} (Day {node.day})")
            
            if result.diff.deleted_nodes:
                lines.append("\n➖ Deleted:")
                for node in result.diff.deleted_nodes[:5]:
                    lines.append(f"   {node.node_type}: {node.name} (Day {node.day})")
            
            if result.diff.modified_nodes:
                lines.append("\n✏️  Modified:")
                for node in result.diff.modified_nodes[:5]:
                    lines.append(f"   {node.node_type}: {node.name} (Day {node.day})")
                    if node.changed_fields:
                        for field, change in node.changed_fields.items():
                            lines.append(f"     {field}: {change['from']} -> {change['to']}")
        
        # Show result preview
        if result.operation == "READ":
            lines.append("\n📋 Result:")
            lines.append("-" * 40)
            # Show first 500 chars of result
            preview = result.result_xml[:500]
            if len(result.result_xml) > 500:
                preview += "\n... (truncated)"
            lines.append(preview)
        
        if result.error:
            lines.append(f"\n⚠️  Error: {result.error}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def run_interactive(self):
        """Run an interactive loop for CRUD operations."""
        print("=" * 60)
        print("In-Context Pipeline - Single-LLM CRUD Operations")
        print("=" * 60)
        print("Full XML tree sent to LLM in each request.")
        print(f"Tree file: {self.tree_path}")
        print("-" * 60)
        print("Commands:")
        print("  - Natural language query for CRUD operations")
        print("  - 'stats' - Session statistics")
        print("  - 'exit' or 'quit' - Exit")
        print("=" * 60)
        print()
        
        while True:
            try:
                user_input = input("🔄 Query: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit", "q"):
                    self._print_session_summary()
                    print("Goodbye!")
                    break
                
                if user_input.lower() == "stats":
                    self._print_stats()
                    continue
                
                # Process the query
                result = self.process_request(user_input)
                print(self.format_result(result))
                print()
                
            except KeyboardInterrupt:
                self._print_session_summary()
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
    
    def _print_stats(self):
        """Print session statistics."""
        print("\n📊 Session Statistics:")
        print("-" * 40)
        print(f"  Total Operations: {self.session_stats['operations']}")
        print(f"  - Reads:   {self.session_stats['reads']}")
        print(f"  - Creates: {self.session_stats['creates']}")
        print(f"  - Updates: {self.session_stats['updates']}")
        print(f"  - Deletes: {self.session_stats['deletes']}")
        print(f"  Versions Created: {self.session_stats['versions_created']}")
        print(f"  Total Tokens: {self.session_stats['total_prompt_tokens'] + self.session_stats['total_completion_tokens']}")
        print(f"    - Prompt:     {self.session_stats['total_prompt_tokens']}")
        print(f"    - Completion: {self.session_stats['total_completion_tokens']}")
        print()
    
    def _print_session_summary(self):
        """Print session summary on exit."""
        print("\n" + "=" * 60)
        print("📊 Session Summary:")
        print("-" * 40)
        print(f"  Operations: {self.session_stats['operations']}")
        print(f"  Versions Created: {self.session_stats['versions_created']}")
        print(f"  Total Tokens: {self.session_stats['total_prompt_tokens'] + self.session_stats['total_completion_tokens']}")
        print("=" * 60)


def main():
    """Main entry point for running the pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="In-Context Pipeline - Single-LLM CRUD Operations")
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="Single query to execute (non-interactive)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output result as JSON")
    
    args = parser.parse_args()
    
    pipeline = IncontextPipeline()
    
    if args.query:
        # Single query mode
        result = pipeline.process_request(args.query)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(pipeline.format_result(result))
    else:
        # Interactive mode
        pipeline.run_interactive()


if __name__ == "__main__":
    main()
