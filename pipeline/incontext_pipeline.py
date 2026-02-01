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

from client.openai_client import OpenAIClient, TokenUsage, CompletionResult


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


@dataclass
class DiffResult:
    """Result of comparing two XML trees."""
    summary: str
    additions: List[str]
    deletions: List[str]
    modifications: List[str]
    unified_diff: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "additions": self.additions,
            "deletions": self.deletions,
            "modifications": self.modifications,
            "unified_diff": self.unified_diff
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
    
    def to_dict(self) -> Dict[str, Any]:
        output = {
            "operation": self.operation,
            "success": self.success,
            "version_used": self.version_used,
            "reasoning": self.reasoning,
            "result": self.result_xml,
            "execution_time_ms": round(self.execution_time_ms, 2)
        }
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
    
    Trade-offs vs. Semantic XPath Pipeline:
    - Simpler architecture (single LLM call)
    - Higher token usage for large trees
    - More direct LLM reasoning over full context
    """
    
    def __init__(self):
        """Initialize the pipeline."""
        self.config = load_config()
        self.client = OpenAIClient(self.config)
        
        # Load pipeline-specific LLM settings
        pipeline_config = self.config.get("incontext_pipeline", {})
        self.temperature = pipeline_config.get("temperature", 0.3)
        self.max_tokens = pipeline_config.get("max_tokens", 16384)
        
        # Load paths
        base_path = Path(__file__).parent.parent
        self.prompts_path = base_path / "storage" / "prompts"
        self.memory_path = base_path / "storage" / "memory"
        
        # Load the system prompt
        self.system_prompt = self._load_prompt()
        
        # Load tree based on config
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
            return self.original_xml
        
        # Sort by version number
        latest = max(versions, key=lambda v: int(v.get("number", "0")))
        
        # Serialize the version for the prompt
        return ET.tostring(latest, encoding="unicode")
    
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
        
        # Get the full tree XML to include in the prompt
        tree_xml = self._get_latest_version_xml()
        
        # Build the user message with tree context
        user_message = f"""## XML Tree

{tree_xml}

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
        if operation in ("CREATE", "UPDATE", "DELETE"):
            diff_result = self._calculate_diff(tree_xml, result_xml)
        
        # Update session stats
        self._update_stats(operation, result.usage)
        
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        return PipelineResult(
            operation=operation,
            success=True,
            version_used=version_used,
            reasoning=reasoning,
            result_xml=result_xml,
            diff=diff_result,
            token_usage=result.usage,
            execution_time_ms=execution_time_ms
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
        Calculate the difference between original and modified XML.
        
        Uses difflib for unified diff and simple heuristics for 
        categorizing changes as additions, deletions, or modifications.
        """
        # Normalize XML for comparison (format consistently)
        original_lines = self._normalize_xml(original_xml).splitlines(keepends=True)
        modified_lines = self._normalize_xml(modified_xml).splitlines(keepends=True)
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            original_lines, 
            modified_lines,
            fromfile='original',
            tofile='modified',
            lineterm=''
        ))
        unified_diff = "".join(diff)
        
        # Categorize changes
        additions = []
        deletions = []
        modifications = []
        
        i = 0
        while i < len(diff):
            line = diff[i]
            if line.startswith('-') and not line.startswith('---'):
                # Check if this is a modification (paired with +)
                if i + 1 < len(diff) and diff[i + 1].startswith('+') and not diff[i + 1].startswith('+++'):
                    # This is a modification
                    old_content = line[1:].strip()
                    new_content = diff[i + 1][1:].strip()
                    if old_content and new_content:
                        modifications.append(f"{old_content} → {new_content}")
                    i += 2
                    continue
                else:
                    # Pure deletion
                    content = line[1:].strip()
                    if content and not content.startswith('<?'):
                        deletions.append(content)
            elif line.startswith('+') and not line.startswith('+++'):
                # Pure addition
                content = line[1:].strip()
                if content and not content.startswith('<?'):
                    additions.append(content)
            i += 1
        
        # Generate summary
        summary_parts = []
        if additions:
            summary_parts.append(f"{len(additions)} addition(s)")
        if deletions:
            summary_parts.append(f"{len(deletions)} deletion(s)")
        if modifications:
            summary_parts.append(f"{len(modifications)} modification(s)")
        summary = ", ".join(summary_parts) if summary_parts else "No changes detected"
        
        return DiffResult(
            summary=summary,
            additions=additions[:10],  # Limit to avoid huge outputs
            deletions=deletions[:10],
            modifications=modifications[:10],
            unified_diff=unified_diff
        )
    
    def _normalize_xml(self, xml_string: str) -> str:
        """Normalize XML string for consistent comparison."""
        try:
            # Parse and re-serialize for consistent formatting
            root = ET.fromstring(f"<wrapper>{xml_string}</wrapper>")
            # Use a simple indent approach
            self._indent_element(root)
            result = ET.tostring(root, encoding="unicode")
            # Remove wrapper
            result = result.replace("<wrapper>", "").replace("</wrapper>", "")
            return result.strip()
        except ET.ParseError:
            # If parsing fails, just normalize whitespace
            return re.sub(r'\s+', ' ', xml_string).strip()
    
    def _indent_element(self, elem: ET.Element, level: int = 0):
        """Add indentation to XML element for pretty printing."""
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_element(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
    
    def _update_stats(self, operation: str, usage: TokenUsage):
        """Update session statistics."""
        self.session_stats["operations"] += 1
        
        op_key = operation.lower() + "s"
        if op_key in self.session_stats:
            self.session_stats[op_key] += 1
        
        self.session_stats["total_prompt_tokens"] += usage.prompt_tokens
        self.session_stats["total_completion_tokens"] += usage.completion_tokens
    
    def format_result(self, result: PipelineResult) -> str:
        """Format the result for display."""
        lines = []
        
        status_icon = "✅" if result.success else "❌"
        lines.append(f"\n{status_icon} {result.operation} Operation {'Succeeded' if result.success else 'Failed'}")
        lines.append("=" * 60)
        
        lines.append(f"📌 Version: {result.version_used}")
        lines.append(f"⏱️  Time: {result.execution_time_ms:.1f}ms")
        
        if result.token_usage:
            lines.append(f"🔢 Tokens: {result.token_usage.prompt_tokens} prompt + {result.token_usage.completion_tokens} completion = {result.token_usage.total_tokens} total")
        
        lines.append(f"\n💭 Reasoning: {result.reasoning}")
        
        # Show diff for CUD operations
        if result.diff:
            lines.append(f"\n📊 Changes: {result.diff.summary}")
            
            if result.diff.additions:
                lines.append("\n➕ Additions:")
                for add in result.diff.additions[:5]:
                    lines.append(f"   {add[:80]}{'...' if len(add) > 80 else ''}")
            
            if result.diff.deletions:
                lines.append("\n➖ Deletions:")
                for delete in result.diff.deletions[:5]:
                    lines.append(f"   {delete[:80]}{'...' if len(delete) > 80 else ''}")
            
            if result.diff.modifications:
                lines.append("\n✏️  Modifications:")
                for mod in result.diff.modifications[:5]:
                    lines.append(f"   {mod[:80]}{'...' if len(mod) > 80 else ''}")
        
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
