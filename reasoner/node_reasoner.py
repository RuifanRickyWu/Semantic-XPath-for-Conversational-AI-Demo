"""
Node Reasoner - LLM-based reasoning for selecting relevant nodes.

Uses an LLM to analyze candidate nodes from semantic XPath and determine
which ones are truly relevant to the user's query.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import get_client
from .base import (
    ReasonerBase, 
    NodeReasoningResult, 
    BatchReasoningResult, 
    ReasonerDecision
)


logger = logging.getLogger(__name__)


class NodeReasoner(ReasonerBase):
    """
    LLM-based reasoner for selecting relevant nodes from candidates.
    
    Takes the topK nodes from semantic XPath and uses LLM reasoning
    to determine which ones truly match the user's intent.
    
    Supports batched processing for efficiency.
    """
    
    PROMPT_PATH = Path(__file__).parent.parent / "storage" / "prompts" / "node_reasoner.txt"
    TRACES_PATH = Path(__file__).parent.parent / "traces" / "reasoning_traces"
    
    DEFAULT_BATCH_SIZE = 10
    
    def __init__(
        self, 
        client=None, 
        batch_size: int = None,
        save_traces: bool = True
    ):
        """
        Initialize the node reasoner.
        
        Args:
            client: Optional OpenAI client
            batch_size: Number of nodes to process per LLM call
            save_traces: Whether to save reasoning traces
        """
        self._client = client
        self._system_prompt = None
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
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
    
    def reason(
        self, 
        nodes: List[Dict[str, Any]], 
        user_query: str,
        operation: str = "READ"
    ) -> BatchReasoningResult:
        """
        Apply reasoning to select relevant nodes.
        
        Args:
            nodes: List of candidate nodes from semantic XPath
            user_query: The original user query
            operation: The CRUD operation type
            
        Returns:
            BatchReasoningResult with decisions for each node
        """
        if not nodes:
            return BatchReasoningResult(user_query=user_query)
        
        all_results = []
        
        # Process in batches
        for i in range(0, len(nodes), self.batch_size):
            batch = nodes[i:i + self.batch_size]
            batch_results = self._process_batch(batch, user_query, operation)
            all_results.extend(batch_results)
        
        # Select nodes that were deemed relevant
        selected = [r for r in all_results if r.decision == ReasonerDecision.RELEVANT]
        
        result = BatchReasoningResult(
            user_query=user_query,
            results=all_results,
            selected_nodes=selected,
            metadata={
                "operation": operation,
                "total_candidates": len(nodes),
                "batch_size": self.batch_size,
                "num_batches": (len(nodes) + self.batch_size - 1) // self.batch_size
            }
        )
        
        # Save trace
        if self.save_traces:
            self._save_trace(result)
        
        return result
    
    def _process_batch(
        self, 
        nodes: List[Dict[str, Any]], 
        user_query: str,
        operation: str
    ) -> List[NodeReasoningResult]:
        """Process a single batch of nodes."""
        nodes_text = self._format_nodes(nodes)
        
        prompt = f"""User Query: {user_query}
Operation: {operation}

Candidate Nodes:
{nodes_text}

Analyze each node and determine if it's relevant to the user's query.
"""
        
        try:
            response = self.client.complete(
                prompt,
                system_prompt=self.system_prompt,
                temperature=0.1,
                max_tokens=2048
            )
            
            return self._parse_response(response, nodes)
            
        except Exception as e:
            logger.error(f"Error in batch reasoning: {e}")
            # Return uncertain results on error
            return [
                NodeReasoningResult(
                    node_id=str(i),
                    node_path=n.get("tree_path", f"node_{i}"),
                    node_data=n,
                    decision=ReasonerDecision.UNCERTAIN,
                    confidence=0.0,
                    reasoning=f"Error: {e}"
                )
                for i, n in enumerate(nodes)
            ]
    
    def _format_nodes(self, nodes: List[Dict[str, Any]]) -> str:
        """Format nodes for the prompt."""
        lines = []
        for i, node in enumerate(nodes):
            node_id = str(i + 1)
            tree_path = node.get("tree_path", f"node_{i}")
            node_type = node.get("node", {}).get("type", "Unknown")
            name = node.get("node", {}).get("name", "")
            description = node.get("node", {}).get("description", "")
            score = node.get("score", 0.0)
            
            lines.append(f"[{node_id}] Path: {tree_path}")
            lines.append(f"    Type: {node_type}")
            if name:
                lines.append(f"    Name: {name}")
            if description:
                lines.append(f"    Description: {description[:200]}...")
            lines.append(f"    Semantic Score: {score:.3f}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _parse_response(
        self, 
        response: str, 
        nodes: List[Dict[str, Any]]
    ) -> List[NodeReasoningResult]:
        """Parse LLM response into NodeReasoningResult objects."""
        results = []
        
        try:
            # Find JSON array in response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                for item in parsed:
                    node_id = str(item.get("id", ""))
                    # Handle both "id" as string and as 1-based index
                    try:
                        idx = int(node_id) - 1  # Convert to 0-based
                        if 0 <= idx < len(nodes):
                            node = nodes[idx]
                        else:
                            continue
                    except ValueError:
                        continue
                    
                    # Parse decision
                    decision_str = item.get("decision", "UNCERTAIN").upper()
                    if decision_str in ("RELEVANT", "YES", "TRUE"):
                        decision = ReasonerDecision.RELEVANT
                    elif decision_str in ("NOT_RELEVANT", "NO", "FALSE"):
                        decision = ReasonerDecision.NOT_RELEVANT
                    else:
                        decision = ReasonerDecision.UNCERTAIN
                    
                    results.append(NodeReasoningResult(
                        node_id=node_id,
                        node_path=node.get("tree_path", f"node_{idx}"),
                        node_data=node.get("node", {}),
                        decision=decision,
                        confidence=float(item.get("confidence", 0.5)),
                        reasoning=item.get("reasoning", "")
                    ))
                
                return results
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse reasoning response: {e}")
        
        # Fallback: assume all nodes are relevant (preserve semantic XPath results)
        for i, node in enumerate(nodes):
            results.append(NodeReasoningResult(
                node_id=str(i + 1),
                node_path=node.get("tree_path", f"node_{i}"),
                node_data=node.get("node", {}),
                decision=ReasonerDecision.RELEVANT,
                confidence=0.5,
                reasoning="Fallback: preserved from semantic XPath"
            ))
        
        return results
    
    def _save_trace(self, result: BatchReasoningResult):
        """Save reasoning trace to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trace_file = self.TRACES_PATH / f"node_reasoning_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            **result.to_dict()
        }
        
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved reasoning trace to {trace_file}")
