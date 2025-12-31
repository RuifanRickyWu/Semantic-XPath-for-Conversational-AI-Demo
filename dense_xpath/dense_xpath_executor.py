"""
Dense XPath Executor - Executes XPath-like queries against a tree memory with semantic matching.

Implements BFS-like traversal with semantic predicate scoring for flexible node matching.
"""

import re
import logging
import json
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer, LLMPredicateScorer


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


logger = logging.getLogger(__name__)


@dataclass
class QueryStep:
    """Represents a single step in an XPath query."""
    node_type: str  # e.g., "Itinerary", "Day", "POI", "Restaurant"
    predicate: Optional[str] = None  # semantic predicate, e.g., "artistic"
    index: Optional[int] = None  # positional index (1-based, -1 for last)
    
    def __repr__(self):
        parts = [self.node_type]
        if self.predicate:
            parts.append(f'[description =~ "{self.predicate}"]')
        if self.index is not None:
            parts.append(f'[{self.index}]')
        return "".join(parts)


@dataclass
class MatchedNode:
    """A matched node with its tree context."""
    node_data: Dict[str, Any]  # The node's own data
    tree_path: str  # Path in tree, e.g., "Itinerary > Day 1 > POI 2"
    children: List[Dict[str, Any]] = field(default_factory=list)  # All child nodes
    score: float = 1.0  # Semantic matching score (1.0 if no semantic predicate)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tree_path": self.tree_path,
            "score": self.score,
            "node": self.node_data,
            "children": self.children
        }


@dataclass
class TraversalStep:
    """A single step in the tree traversal."""
    step_index: int
    step_query: str
    nodes_before: List[Dict[str, Any]]  # Nodes at start of step
    nodes_after: List[Dict[str, Any]]   # Nodes after filtering
    action: str  # "type_match", "semantic_predicate", "index"
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_query": self.step_query,
            "action": self.action,
            "nodes_before_count": len(self.nodes_before),
            "nodes_after_count": len(self.nodes_after),
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
            "details": self.details
        }


@dataclass
class ExecutionResult:
    """Result of executing an XPath query."""
    query: str
    matched_nodes: List[MatchedNode]
    execution_log: List[str] = field(default_factory=list)
    scoring_traces: List[Dict[str, Any]] = field(default_factory=list)
    traversal_steps: List[TraversalStep] = field(default_factory=list)


class DenseXPathExecutor:
    """
    Executes XPath-like queries against an XML tree with semantic matching.
    
    Supports:
    - Type matching: /Itinerary/Day/POI
    - Positional indexing: Day[1], POI[2], POI[-1]
    - Semantic predicates: Day[description =~ "artistic"]
    - Global indexing: (/Itinerary/Day/POI)[5]
    - Combined: Day[description =~ "artistic"][2]
    """
    
    MEMORY_PATH = Path(__file__).parent.parent / "storage" / "memory" / "tree_memory.xml"
    LOG_PATH = Path(__file__).parent.parent / "traces" / "log"
    TRACES_PATH = Path(__file__).parent.parent / "traces" / "reasoning_traces"
    
    def __init__(
        self, 
        scorer: PredicateScorer = None,
        top_k: int = None,
        score_threshold: float = None,
        config: dict = None
    ):
        """
        Initialize the executor.
        
        Args:
            scorer: Predicate scorer implementation. Defaults to LLMPredicateScorer.
            top_k: Number of top-scoring nodes to consider as "relevant". Defaults to config value.
            score_threshold: Minimum score to consider a node relevant. Defaults to config value.
            config: Optional config dict. If not provided, loads from config.yaml.
        """
        if config is None:
            config = load_config()
        
        executor_config = config.get("xpath_executor", {})
        
        self.scorer = scorer or LLMPredicateScorer()
        self.top_k = top_k if top_k is not None else executor_config.get("top_k", 5)
        self.score_threshold = score_threshold if score_threshold is not None else executor_config.get("score_threshold", 0.5)
        self._tree = None
        self._root = None
        
        # Ensure directories exist
        self.LOG_PATH.mkdir(parents=True, exist_ok=True)
        self.TRACES_PATH.mkdir(parents=True, exist_ok=True)
    
    @property
    def tree(self) -> ET.ElementTree:
        """Lazy load the XML tree."""
        if self._tree is None:
            self._tree = ET.parse(self.MEMORY_PATH)
            self._root = self._tree.getroot()
        return self._tree
    
    @property
    def root(self) -> ET.Element:
        """Get the root element."""
        if self._root is None:
            _ = self.tree  # Trigger lazy load
        return self._root
    
    def execute(self, query: str) -> ExecutionResult:
        """
        Execute an XPath-like query against the tree.
        
        Args:
            query: XPath-like query string
            
        Returns:
            ExecutionResult with matched nodes and execution log
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        execution_log = []
        scoring_traces = []
        traversal_steps = []
        
        execution_log.append(f"[{timestamp}] Executing query: {query}")
        
        # Check for global indexing: (/Itinerary/Day/POI)[n]
        global_index = None
        inner_query = query
        
        global_match = re.match(r'^\((.+)\)\[(-?\d+)\]$', query)
        if global_match:
            inner_query = global_match.group(1)
            global_index = int(global_match.group(2))
            execution_log.append(f"Global index detected: {global_index}")
        
        # Parse the query into steps
        steps = self._parse_query(inner_query)
        execution_log.append(f"Parsed steps: {steps}")
        
        # Execute BFS-like traversal with path and score tracking
        # Each item is (node, path_string, score)
        current_items: List[Tuple[ET.Element, str, float]] = [(self.root, "Itinerary", 1.0)]
        
        for step_idx, step in enumerate(steps):
            execution_log.append(f"\n--- Step {step_idx + 1}: {step} ---")
            
            if step.node_type == "Itinerary":
                # Root node, just verify
                if current_items and current_items[0][0].tag == "Itinerary":
                    execution_log.append("Matched Itinerary root")
                    traversal_steps.append(TraversalStep(
                        step_index=step_idx,
                        step_query=str(step),
                        nodes_before=[{"type": "root"}],
                        nodes_after=[{"type": "Itinerary", "path": "Itinerary"}],
                        action="root_match",
                        details={"matched": True}
                    ))
                else:
                    execution_log.append("ERROR: Root is not Itinerary")
                    current_items = []
                continue
            
            # Track nodes before this step
            nodes_before = [
                {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                for n, p, s in current_items
            ]
            
            # Get children of current nodes that match the type
            next_items = []
            for node, path, parent_score in current_items:
                children = list(node.findall(step.node_type))
                for idx, child in enumerate(children):
                    child_name = self._get_node_name(child)
                    # Track position within parent, inherit parent score
                    child_path = f"{path} > {child_name}"
                    next_items.append((child, child_path, parent_score))
            
            execution_log.append(f"Found {len(next_items)} {step.node_type} nodes")
            
            # Track type matching step
            type_match_nodes = [
                {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                for n, p, s in next_items
            ]
            traversal_steps.append(TraversalStep(
                step_index=step_idx,
                step_query=str(step),
                nodes_before=nodes_before,
                nodes_after=type_match_nodes,
                action="type_match",
                details={"target_type": step.node_type, "found_count": len(next_items)}
            ))
            
            if not next_items:
                execution_log.append(f"No matching nodes for {step.node_type}")
                current_items = []
                break
            
            # Apply semantic predicate if present
            if step.predicate:
                execution_log.append(f"Applying semantic predicate: {step.predicate}")
                nodes_only = [item[0] for item in next_items]
                nodes_before_pred = [
                    {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                    for n, p, s in next_items
                ]
                
                filtered_nodes, scores_map, trace = self._apply_semantic_predicate(
                    nodes_only, step.predicate, execution_log
                )
                # Filter items and update scores
                filtered_set = set(id(n) for n in filtered_nodes)
                next_items = [
                    (n, p, scores_map.get(id(n), s))  # Use new score from predicate
                    for n, p, s in next_items if id(n) in filtered_set
                ]
                scoring_traces.append(trace)
                
                # Track predicate step
                nodes_after_pred = [
                    {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                    for n, p, s in next_items
                ]
                traversal_steps.append(TraversalStep(
                    step_index=step_idx,
                    step_query=str(step),
                    nodes_before=nodes_before_pred,
                    nodes_after=nodes_after_pred,
                    action="semantic_predicate",
                    details={
                        "predicate": step.predicate,
                        "scoring_result": trace
                    }
                ))
            
            # Apply positional index if present
            if step.index is not None:
                execution_log.append(f"Applying positional index: {step.index}")
                nodes_before_idx = [
                    {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                    for n, p, s in next_items
                ]
                
                nodes_only = [item[0] for item in next_items]
                indexed_nodes = self._apply_index(nodes_only, step.index, execution_log)
                if indexed_nodes:
                    indexed_set = set(id(n) for n in indexed_nodes)
                    next_items = [(n, p, s) for n, p, s in next_items if id(n) in indexed_set]
                else:
                    next_items = []
                
                # Track index step
                nodes_after_idx = [
                    {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                    for n, p, s in next_items
                ]
                traversal_steps.append(TraversalStep(
                    step_index=step_idx,
                    step_query=str(step),
                    nodes_before=nodes_before_idx,
                    nodes_after=nodes_after_idx,
                    action="positional_index",
                    details={"index": step.index, "selected_count": len(next_items)}
                ))
            
            current_items = next_items
            execution_log.append(f"After step: {len(current_items)} nodes remaining")
        
        # Apply global index if present
        if global_index is not None and current_items:
            execution_log.append(f"\nApplying global index: {global_index}")
            nodes_before_global = [
                {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                for n, p, s in current_items
            ]
            
            nodes_only = [item[0] for item in current_items]
            indexed_nodes = self._apply_index(nodes_only, global_index, execution_log)
            if indexed_nodes:
                indexed_set = set(id(n) for n in indexed_nodes)
                current_items = [(n, p, s) for n, p, s in current_items if id(n) in indexed_set]
            else:
                current_items = []
            
            nodes_after_global = [
                {"path": p, "name": self._get_node_name(n), "type": n.tag, "score": s}
                for n, p, s in current_items
            ]
            traversal_steps.append(TraversalStep(
                step_index=len(steps),
                step_query=f"global[{global_index}]",
                nodes_before=nodes_before_global,
                nodes_after=nodes_after_global,
                action="global_index",
                details={"index": global_index}
            ))
        
        # Convert to result format with tree path, children, and score
        # Sort by score descending
        current_items.sort(key=lambda x: x[2], reverse=True)
        
        matched_nodes = [
            self._node_to_matched(node, path, score) 
            for node, path, score in current_items
        ]
        execution_log.append(f"\nFinal result: {len(matched_nodes)} nodes (sorted by score)")
        
        result = ExecutionResult(
            query=query,
            matched_nodes=matched_nodes,
            execution_log=execution_log,
            scoring_traces=scoring_traces,
            traversal_steps=traversal_steps
        )
        
        # Save traces
        self._save_traces(timestamp, result)
        
        return result
    
    def _parse_query(self, query: str) -> List[QueryStep]:
        """Parse an XPath query into steps."""
        steps = []
        
        # Remove leading slash
        if query.startswith("/"):
            query = query[1:]
        
        # Split by / but respect brackets
        parts = self._split_path(query)
        
        for part in parts:
            step = self._parse_step(part)
            if step:
                steps.append(step)
        
        return steps
    
    def _split_path(self, query: str) -> List[str]:
        """Split path by / while respecting brackets."""
        parts = []
        current = ""
        bracket_depth = 0
        
        for char in query:
            if char == "[":
                bracket_depth += 1
                current += char
            elif char == "]":
                bracket_depth -= 1
                current += char
            elif char == "/" and bracket_depth == 0:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts
    
    def _parse_step(self, step_str: str) -> Optional[QueryStep]:
        """Parse a single step like 'Day[description =~ "artistic"][2]'."""
        # Pattern: NodeType[description =~ "predicate"]?[index]?
        
        # Extract node type (everything before first [)
        match = re.match(r'^([A-Za-z]+)', step_str)
        if not match:
            return None
        
        node_type = match.group(1)
        remaining = step_str[len(node_type):]
        
        predicate = None
        index = None
        
        # Extract predicates and indexes from brackets
        bracket_pattern = r'\[([^\]]+)\]'
        brackets = re.findall(bracket_pattern, remaining)
        
        for bracket_content in brackets:
            # Check if it's a semantic predicate
            pred_match = re.match(r'description\s*=~\s*["\']([^"\']+)["\']', bracket_content)
            if pred_match:
                predicate = pred_match.group(1)
            else:
                # Try to parse as index
                try:
                    index = int(bracket_content)
                except ValueError:
                    pass
        
        return QueryStep(node_type=node_type, predicate=predicate, index=index)
    
    def _apply_semantic_predicate(
        self, 
        nodes: List[ET.Element], 
        predicate: str,
        execution_log: List[str]
    ) -> Tuple[List[ET.Element], Dict[int, float], Dict[str, Any]]:
        """
        Apply semantic predicate scoring to nodes.
        
        For each node, scores itself and its subtree, takes mean as final score.
        Returns:
            - filtered nodes (top-k above threshold)
            - scores_map: dict mapping node id() to mean score
            - trace: detailed scoring trace
        """
        # Prepare nodes for scoring (include subtree descriptions)
        scoring_input = []
        node_info_map = {}  # Track detailed info for each scoring input
        
        for idx, node in enumerate(nodes):
            # Get the node's own description
            node_desc = self._get_node_description(node)
            node_name = self._get_node_name(node)
            
            # Get subtree descriptions
            subtree_descs = self._get_subtree_descriptions(node)
            
            node_id = f"node_{idx}"
            
            # Add main node
            main_item = {
                "id": f"{node_id}_main",
                "type": node.tag,
                "name": node_name,
                "description": node_desc,
                "parent_idx": idx,
                "is_main": True
            }
            scoring_input.append(main_item)
            node_info_map[f"{node_id}_main"] = main_item
            
            # Add subtree nodes
            for sub_idx, (sub_type, sub_name, sub_desc) in enumerate(subtree_descs):
                sub_item = {
                    "id": f"{node_id}_sub_{sub_idx}",
                    "type": sub_type,
                    "name": sub_name,
                    "description": sub_desc,
                    "parent_idx": idx,
                    "is_main": False
                }
                scoring_input.append(sub_item)
                node_info_map[f"{node_id}_sub_{sub_idx}"] = sub_item
        
        execution_log.append(f"Scoring {len(scoring_input)} descriptions for predicate '{predicate}'")
        
        # Score all in one batch
        batch_result = self.scorer.score_batch(scoring_input, predicate)
        
        # Build detailed scoring results for trace
        individual_scores = []
        parent_scores = {}  # parent_idx -> list of (score, item_info)
        
        for item in scoring_input:
            parent_idx = item["parent_idx"]
            if parent_idx not in parent_scores:
                parent_scores[parent_idx] = []
        
        for result in batch_result.results:
            node_id = result.node_id
            item_info = node_info_map.get(node_id, {})
            
            score_detail = {
                "id": node_id,
                "type": item_info.get("type", ""),
                "name": item_info.get("name", ""),
                "description": item_info.get("description", "")[:100],
                "score": result.score,
                "reasoning": result.reasoning,
                "is_main_node": item_info.get("is_main", False)
            }
            individual_scores.append(score_detail)
            
            if "_main" in node_id or "_sub_" in node_id:
                parent_idx = int(node_id.split("_")[1])
                parent_scores[parent_idx].append(result.score)
        
        # Calculate mean scores for each parent node
        mean_scores = []
        node_aggregations = []
        
        for idx in range(len(nodes)):
            scores = parent_scores.get(idx, [0.0])
            mean_score = sum(scores) / len(scores) if scores else 0.0
            mean_scores.append((idx, mean_score))
            
            node_aggregations.append({
                "node_idx": idx,
                "node_name": self._get_node_name(nodes[idx]),
                "node_type": nodes[idx].tag,
                "individual_scores": scores,
                "mean_score": mean_score,
                "num_items_scored": len(scores)
            })
            
            execution_log.append(f"  Node {idx} ({self._get_node_name(nodes[idx])}): mean score = {mean_score:.3f} (from {len(scores)} items)")
        
        # Sort by score descending
        mean_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take top-k above threshold
        top_indices = []
        for idx, score in mean_scores:
            if score >= self.score_threshold and len(top_indices) < self.top_k:
                top_indices.append(idx)
        
        # Preserve original order for indexed selection
        top_indices.sort()
        
        execution_log.append(f"Top {len(top_indices)} nodes selected (threshold={self.score_threshold}, top_k={self.top_k})")
        
        # Build scores_map: node id() -> mean score
        scores_map = {}
        for idx, score in mean_scores:
            scores_map[id(nodes[idx])] = score
        
        # Create detailed trace
        trace = {
            "predicate": predicate,
            "config": {
                "top_k": self.top_k,
                "score_threshold": self.score_threshold
            },
            "batch_scoring": {
                "total_items_scored": len(scoring_input),
                "individual_scores": individual_scores
            },
            "node_aggregations": node_aggregations,
            "ranking": [
                {"idx": idx, "score": score, "name": self._get_node_name(nodes[idx])} 
                for idx, score in mean_scores
            ],
            "selected": {
                "indices": top_indices,
                "nodes": [
                    {"idx": idx, "name": self._get_node_name(nodes[idx])}
                    for idx in top_indices
                ]
            }
        }
        
        return [nodes[i] for i in top_indices], scores_map, trace
    
    def _apply_index(
        self, 
        nodes: List[ET.Element], 
        index: int,
        execution_log: List[str]
    ) -> List[ET.Element]:
        """Apply positional index to nodes."""
        if not nodes:
            return []
        
        # Convert to 0-based index
        if index > 0:
            idx = index - 1
        elif index == -1:
            idx = len(nodes) - 1
        else:
            idx = index  # Handle other negative indices if needed
        
        if 0 <= idx < len(nodes):
            execution_log.append(f"Selected node at index {index} (0-based: {idx})")
            return [nodes[idx]]
        else:
            execution_log.append(f"Index {index} out of range (have {len(nodes)} nodes)")
            return []
    
    def _get_node_description(self, node: ET.Element) -> str:
        """Get the description of a node."""
        desc_elem = node.find("description")
        if desc_elem is not None and desc_elem.text:
            return desc_elem.text
        
        # For Day nodes, create a summary from children
        if node.tag == "Day":
            children_descs = []
            for child in node:
                if child.tag in ("POI", "Restaurant"):
                    child_desc = child.find("description")
                    child_name = child.find("name")
                    if child_name is not None and child_name.text:
                        children_descs.append(child_name.text)
            if children_descs:
                return f"Day with: {', '.join(children_descs[:3])}"
        
        return ""
    
    def _get_node_name(self, node: ET.Element) -> str:
        """Get the name of a node."""
        name_elem = node.find("name")
        if name_elem is not None and name_elem.text:
            return name_elem.text
        
        # For Day nodes, use index
        if node.tag == "Day":
            index = node.get("index", "?")
            return f"Day {index}"
        
        return node.tag
    
    def _get_subtree_descriptions(self, node: ET.Element) -> List[Tuple[str, str, str]]:
        """Get descriptions from all descendants. Returns list of (type, name, description)."""
        results = []
        
        for child in node:
            if child.tag in ("POI", "Restaurant"):
                name = ""
                desc = ""
                name_elem = child.find("name")
                desc_elem = child.find("description")
                if name_elem is not None:
                    name = name_elem.text or ""
                if desc_elem is not None:
                    desc = desc_elem.text or ""
                results.append((child.tag, name, desc))
        
        return results
    
    def _node_to_matched(self, node: ET.Element, tree_path: str, score: float = 1.0) -> MatchedNode:
        """Convert an XML node to a MatchedNode with tree context, children, and score."""
        node_data = self._node_to_dict(node)
        children = self._get_all_children(node)
        
        return MatchedNode(
            node_data=node_data,
            tree_path=tree_path,
            children=children,
            score=score
        )
    
    def _node_to_dict(self, node: ET.Element) -> Dict[str, Any]:
        """Convert an XML node to a dictionary (node's own data only)."""
        result = {
            "type": node.tag,
            "attributes": dict(node.attrib)
        }
        
        # Add simple child elements as fields
        for child in node:
            if len(child) == 0:  # Leaf element
                result[child.tag] = child.text
            elif child.tag == "highlights":
                result["highlights"] = [h.text for h in child.findall("highlight")]
        
        return result
    
    def _get_all_children(self, node: ET.Element) -> List[Dict[str, Any]]:
        """Get all children of a node as dictionaries."""
        children = []
        for child in node:
            if child.tag in ("POI", "Restaurant"):
                child_dict = {
                    "type": child.tag,
                    "name": "",
                    "description": "",
                    "time_block": "",
                    "expected_cost": "",
                    "highlights": []
                }
                for elem in child:
                    if elem.tag == "highlights":
                        child_dict["highlights"] = [h.text for h in elem.findall("highlight")]
                    elif elem.text:
                        child_dict[elem.tag] = elem.text
                children.append(child_dict)
        return children
    
    def _save_traces(self, timestamp: str, result: ExecutionResult):
        """Save execution log and reasoning traces to files."""
        # Save text log
        log_file = self.LOG_PATH / f"execution_{timestamp}.log"
        
        with open(log_file, "w") as f:
            f.write(f"Query: {result.query}\n")
            f.write("=" * 60 + "\n\n")
            f.write("Execution Log:\n")
            f.write("-" * 40 + "\n")
            for line in result.execution_log:
                f.write(line + "\n")
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"Matched Nodes: {len(result.matched_nodes)}\n")
            f.write("-" * 40 + "\n")
            for matched in result.matched_nodes:
                f.write(json.dumps(matched.to_dict(), indent=2) + "\n")
        
        # Save detailed reasoning trace (always save, not just when scoring)
        trace_file = self.TRACES_PATH / f"execution_{timestamp}.json"
        
        trace_data = {
            "timestamp": timestamp,
            "query": result.query,
            "traversal_steps": [step.to_dict() for step in result.traversal_steps],
            "scoring_traces": result.scoring_traces,
            "matched_nodes": [m.to_dict() for m in result.matched_nodes],
            "summary": {
                "total_steps": len(result.traversal_steps),
                "total_scoring_calls": len(result.scoring_traces),
                "matched_count": len(result.matched_nodes)
            }
        }
        
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved execution log to {log_file}")
        logger.debug(f"Saved reasoning trace to {trace_file}")

