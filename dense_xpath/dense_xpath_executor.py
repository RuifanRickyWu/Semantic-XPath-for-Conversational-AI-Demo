"""
Dense XPath Executor - Main executor class that orchestrates query execution.

Uses modular components for parsing, node operations, indexing, and scoring.
"""

import logging
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer, get_scorer

from .models import (
    IndexRange, QueryStep, MatchedNode, TraversalStep, ExecutionResult
)
from .parser import QueryParser
from .node_utils import NodeUtils
from .index_handler import IndexHandler
from .predicate_handler import PredicateHandler
from .trace_writer import TraceWriter


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


logger = logging.getLogger(__name__)


class DenseXPathExecutor:
    """
    Executes XPath-like queries against an XML tree with semantic matching.
    
    Supports:
    - Type matching: /Itinerary/Day/POI
    - Positional indexing: Day[1], POI[2], POI[-1], POI[1:3]
    - Semantic predicates: Day[description =~ "artistic"]
    - Global indexing: (/Itinerary/Day/POI)[5], (/Itinerary/Day/POI)[1:3]
    - Combined: Day[description =~ "artistic"][2]
    """
    
    MEMORY_PATH = Path(__file__).parent.parent / "storage" / "memory" / "tree_memory.xml"
    
    def __init__(
        self, 
        scorer: PredicateScorer = None,
        scoring_method: str = None,
        top_k: int = None,
        score_threshold: float = None,
        config: dict = None
    ):
        """
        Initialize the executor.
        
        Args:
            scorer: Predicate scorer implementation. If not provided, uses get_scorer().
            scoring_method: Scoring method ("llm" or "entailment"). 
                           If None, uses value from config.yaml.
            top_k: Number of top-scoring nodes to consider. Defaults to config value.
            score_threshold: Minimum score threshold. Defaults to config value.
            config: Optional config dict. If not provided, loads from config.yaml.
        """
        if config is None:
            config = load_config()
        
        executor_config = config.get("xpath_executor", {})
        
        # Load configuration values
        self.scoring_method = scoring_method or executor_config.get("scoring_method", "llm")
        self.top_k = top_k if top_k is not None else executor_config.get("top_k", 5)
        self.score_threshold = score_threshold if score_threshold is not None else executor_config.get("score_threshold", 0.5)
        
        # Initialize scorer
        if scorer is not None:
            self.scorer = scorer
        else:
            self.scorer = get_scorer(method=self.scoring_method, config=config)
        
        # Initialize components
        self.parser = QueryParser()
        self.predicate_handler = PredicateHandler(
            scorer=self.scorer,
            top_k=self.top_k,
            score_threshold=self.score_threshold
        )
        self.trace_writer = TraceWriter()
        
        # Lazy-loaded tree
        self._tree = None
        self._root = None
    
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
        
        # Parse the query
        steps, global_index = self.parser.parse(query)
        
        if global_index is not None:
            if global_index.is_range:
                execution_log.append(f"Global index range detected: [{global_index.start}:{global_index.end}]")
            else:
                execution_log.append(f"Global index detected: {global_index.start}")
        
        execution_log.append(f"Parsed steps: {steps}")
        
        # Execute BFS-like traversal with path and score tracking
        # Each item is (node, path_string, score)
        current_items: List[Tuple[ET.Element, str, float]] = [(self.root, "Itinerary", 1.0)]
        
        for step_idx, step in enumerate(steps):
            execution_log.append(f"\n--- Step {step_idx + 1}: {step} ---")
            
            if step.node_type == "Itinerary":
                # Root node, just verify
                current_items, traversal_step = self._handle_root_step(
                    current_items, step, step_idx, execution_log
                )
                if traversal_step:
                    traversal_steps.append(traversal_step)
                continue
            
            # Track nodes before this step
            nodes_before = self._items_to_info(current_items)
            
            # Step 1: Type matching - get children matching the type
            next_items = self._apply_type_match(current_items, step, execution_log)
            
            # Track type matching
            type_match_nodes = self._items_to_info(next_items)
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
            
            # Step 2: Apply semantic predicate if present
            if step.predicate:
                next_items, pred_trace, pred_step = self._apply_predicate_step(
                    next_items, step, step_idx, execution_log
                )
                scoring_traces.append(pred_trace)
                traversal_steps.append(pred_step)
            
            # Step 3: Apply positional index if present
            if step.index is not None:
                next_items, idx_step = self._apply_index_step(
                    next_items, step, step_idx, execution_log
                )
                traversal_steps.append(idx_step)
            
            current_items = next_items
            execution_log.append(f"After step: {len(current_items)} nodes remaining")
        
        # Apply global index if present
        if global_index is not None and current_items:
            current_items, global_step = self._apply_global_index(
                current_items, global_index, len(steps), execution_log
            )
            traversal_steps.append(global_step)
        
        # Convert to result format, sorted by score descending
        current_items.sort(key=lambda x: x[2], reverse=True)
        
        matched_nodes = [
            NodeUtils.node_to_matched(node, path, score) 
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
        self.trace_writer.save_traces(timestamp, result)
        
        return result
    
    def _items_to_info(
        self, 
        items: List[Tuple[ET.Element, str, float]]
    ) -> List[dict]:
        """Convert items to info dictionaries for tracing."""
        return [
            NodeUtils.node_to_info_dict(n, p, s)
            for n, p, s in items
        ]
    
    def _handle_root_step(
        self,
        current_items: List[Tuple[ET.Element, str, float]],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[Tuple[ET.Element, str, float]], Optional[TraversalStep]]:
        """Handle the root Itinerary step."""
        if current_items and current_items[0][0].tag == "Itinerary":
            execution_log.append("Matched Itinerary root")
            traversal_step = TraversalStep(
                step_index=step_idx,
                step_query=str(step),
                nodes_before=[{"type": "root"}],
                nodes_after=[{"type": "Itinerary", "path": "Itinerary"}],
                action="root_match",
                details={"matched": True}
            )
            return current_items, traversal_step
        else:
            execution_log.append("ERROR: Root is not Itinerary")
            return [], None
    
    def _apply_type_match(
        self,
        current_items: List[Tuple[ET.Element, str, float]],
        step: QueryStep,
        execution_log: List[str]
    ) -> List[Tuple[ET.Element, str, float]]:
        """Apply type matching to get children of specified type."""
        next_items = []
        for node, path, parent_score in current_items:
            children = list(node.findall(step.node_type))
            for child in children:
                child_name = NodeUtils.get_node_name(child)
                child_path = f"{path} > {child_name}"
                next_items.append((child, child_path, parent_score))
        
        execution_log.append(f"Found {len(next_items)} {step.node_type} nodes")
        return next_items
    
    def _apply_predicate_step(
        self,
        items: List[Tuple[ET.Element, str, float]],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[Tuple[ET.Element, str, float]], dict, TraversalStep]:
        """Apply semantic predicate filtering."""
        execution_log.append(f"Applying semantic predicate: {step.predicate}")
        
        nodes_before_pred = self._items_to_info(items)
        nodes_only = [item[0] for item in items]
        
        filtered_nodes, scores_map, trace = self.predicate_handler.apply_semantic_predicate(
            nodes_only, step.predicate, execution_log
        )
        
        # Filter items and update scores
        filtered_set = set(id(n) for n in filtered_nodes)
        next_items = [
            (n, p, scores_map.get(id(n), s))
            for n, p, s in items if id(n) in filtered_set
        ]
        
        nodes_after_pred = self._items_to_info(next_items)
        
        traversal_step = TraversalStep(
            step_index=step_idx,
            step_query=str(step),
            nodes_before=nodes_before_pred,
            nodes_after=nodes_after_pred,
            action="semantic_predicate",
            details={
                "predicate": step.predicate,
                "scoring_result": trace
            }
        )
        
        return next_items, trace, traversal_step
    
    def _apply_index_step(
        self,
        items: List[Tuple[ET.Element, str, float]],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[Tuple[ET.Element, str, float]], TraversalStep]:
        """Apply positional index filtering."""
        execution_log.append(f"Applying positional index: {step.index}")
        
        nodes_before_idx = self._items_to_info(items)
        nodes_only = [item[0] for item in items]
        
        indexed_nodes = IndexHandler.apply_index(nodes_only, step.index, execution_log)
        
        if indexed_nodes:
            indexed_set = set(id(n) for n in indexed_nodes)
            next_items = [(n, p, s) for n, p, s in items if id(n) in indexed_set]
        else:
            next_items = []
        
        nodes_after_idx = self._items_to_info(next_items)
        
        traversal_step = TraversalStep(
            step_index=step_idx,
            step_query=str(step),
            nodes_before=nodes_before_idx,
            nodes_after=nodes_after_idx,
            action="positional_index",
            details={
                "index": step.index.to_dict(),
                "selected_count": len(next_items)
            }
        )
        
        return next_items, traversal_step
    
    def _apply_global_index(
        self,
        items: List[Tuple[ET.Element, str, float]],
        global_index: IndexRange,
        total_steps: int,
        execution_log: List[str]
    ) -> Tuple[List[Tuple[ET.Element, str, float]], TraversalStep]:
        """Apply global index to final result set."""
        execution_log.append(f"\nApplying global index: {global_index}")
        
        nodes_before_global = self._items_to_info(items)
        nodes_only = [item[0] for item in items]
        
        indexed_nodes = IndexHandler.apply_index(nodes_only, global_index, execution_log)
        
        if indexed_nodes:
            indexed_set = set(id(n) for n in indexed_nodes)
            next_items = [(n, p, s) for n, p, s in items if id(n) in indexed_set]
        else:
            next_items = []
        
        nodes_after_global = self._items_to_info(next_items)
        
        traversal_step = TraversalStep(
            step_index=total_steps,
            step_query=f"global{global_index}",
            nodes_before=nodes_before_global,
            nodes_after=nodes_after_global,
            action="global_index",
            details={"index": global_index.to_dict()}
        )
        
        return next_items, traversal_step

