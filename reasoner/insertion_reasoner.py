"""
Insertion Reasoner - Determines optimal insertion points for Create operations.

Uses an LLM to analyze the tree context and determine where a new node
should be inserted based on the user's request.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from .base import InsertionPoint


logger = logging.getLogger(__name__)


class InsertionReasoner:
    """
    LLM-based reasoner for finding optimal insertion points.
    
    Analyzes the user's create request and the current tree structure
    to determine where a new node should be inserted.
    """
    
    PROMPT_PATH = Path(__file__).parent.parent / "storage" / "prompts" / "insertion_reasoner.txt"
    TRACES_PATH = Path(__file__).parent.parent / "traces" / "reasoning_traces"
    
    def __init__(self, client=None, save_traces: bool = True):
        """
        Initialize the insertion reasoner.
        
        Args:
            client: Optional OpenAI client
            save_traces: Whether to save reasoning traces
        """
        self._client = client
        self._system_prompt = None
        self.save_traces = save_traces
        
        # Ensure traces directory exists
        self.TRACES_PATH.mkdir(parents=True, exist_ok=True)
    
    @property
    def client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = get_client()
        return self._client
    
    @property
    def system_prompt(self) -> str:
        """Lazy load the system prompt from file."""
        if self._system_prompt is None:
            with open(self.PROMPT_PATH, "r") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    def find_insertion_point(
        self,
        user_query: str,
        parent_candidates: List[Dict[str, Any]],
        operation_details: Dict[str, Any],
        schema: Dict[str, Any] = None
    ) -> InsertionPoint:
        """
        Find the best insertion point for a new node.
        
        Args:
            user_query: The original user query
            parent_candidates: Potential parent nodes from semantic XPath
            operation_details: Details about what to create and where
            schema: Optional schema information for valid node types
            
        Returns:
            InsertionPoint with the chosen location and reasoning
        """
        if not parent_candidates:
            # Default to root if no candidates
            return InsertionPoint(
                parent_path="root",
                position=-1,
                reasoning="No parent candidates found, defaulting to root"
            )
        
        context_text = self._format_context(parent_candidates, operation_details)
        
        prompt = f"""User Query: {user_query}

Context:
{context_text}

Determine the best insertion point for the new content.
"""
        
        try:
            response = self.client.complete(
                prompt,
                system_prompt=self.system_prompt,
                temperature=0.1,
                max_tokens=1024
            )
            
            result = self._parse_response(response, parent_candidates, operation_details)
            
            # Save trace
            if self.save_traces:
                self._save_trace(user_query, parent_candidates, operation_details, result, response)
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding insertion point: {e}")
            # Default to first candidate, append at end
            first_candidate = parent_candidates[0]
            return InsertionPoint(
                parent_path=first_candidate.get("tree_path", "root"),
                position=-1,
                sibling_context={"children_count": len(first_candidate.get("children", []))},
                reasoning=f"Error occurred: {e}. Defaulting to first candidate."
            )
    
    def _format_context(
        self, 
        candidates: List[Dict[str, Any]], 
        operation_details: Dict[str, Any]
    ) -> str:
        """Format the context for the prompt."""
        lines = []
        
        # Operation details
        lines.append("=== Operation Details ===")
        new_content = operation_details.get("new_content", "unknown")
        insertion_context = operation_details.get("insertion_context", "")
        lines.append(f"New Content: {new_content}")
        if insertion_context:
            lines.append(f"Insertion Hint: {insertion_context}")
        lines.append("")
        
        # Parent candidates
        lines.append("=== Potential Parent Nodes ===")
        for i, candidate in enumerate(candidates):
            lines.append(f"\n[{i + 1}] {candidate.get('tree_path', 'unknown')}")
            node_data = candidate.get("node", {})
            node_type = node_data.get("type", "Unknown")
            lines.append(f"    Type: {node_type}")
            
            # List existing children
            children = candidate.get("children", [])
            if children:
                lines.append(f"    Children ({len(children)}):")
                for j, child in enumerate(children):
                    child_type = child.get("type", "?")
                    child_name = child.get("name", "")
                    child_time = child.get("time_block", "")
                    lines.append(f"      [{j}] {child_type}: {child_name} {child_time}")
            else:
                lines.append("    Children: none")
        
        return "\n".join(lines)
    
    def _parse_response(
        self, 
        response: str, 
        candidates: List[Dict[str, Any]],
        operation_details: Dict[str, Any]
    ) -> InsertionPoint:
        """Parse LLM response into InsertionPoint."""
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                # Get parent index (1-based in response)
                parent_idx = int(parsed.get("parent_index", 1)) - 1
                if 0 <= parent_idx < len(candidates):
                    parent = candidates[parent_idx]
                else:
                    parent = candidates[0]
                
                position = int(parsed.get("position", -1))
                reasoning = parsed.get("reasoning", "")
                
                return InsertionPoint(
                    parent_path=parent.get("tree_path", "root"),
                    position=position,
                    sibling_context={
                        "children": parent.get("children", []),
                        "parent_type": parent.get("node", {}).get("type", "Unknown")
                    },
                    reasoning=reasoning
                )
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse insertion response: {e}")
        
        # Fallback: use first candidate, append at end
        first = candidates[0]
        return InsertionPoint(
            parent_path=first.get("tree_path", "root"),
            position=-1,
            sibling_context={"children_count": len(first.get("children", []))},
            reasoning="Fallback: appending to first candidate"
        )
    
    def _save_trace(
        self,
        user_query: str,
        candidates: List[Dict[str, Any]],
        operation_details: Dict[str, Any],
        result: InsertionPoint,
        raw_response: str
    ):
        """Save reasoning trace to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trace_file = self.TRACES_PATH / f"insertion_reasoning_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            "user_query": user_query,
            "operation_details": operation_details,
            "candidates_count": len(candidates),
            "candidates": [
                {
                    "tree_path": c.get("tree_path"),
                    "node_type": c.get("node", {}).get("type"),
                    "children_count": len(c.get("children", []))
                }
                for c in candidates
            ],
            "result": result.to_dict(),
            "raw_response": raw_response
        }
        
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved insertion reasoning trace to {trace_file}")
