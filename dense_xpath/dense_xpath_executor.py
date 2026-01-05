"""
Dense XPath Executor - Main executor class that orchestrates query execution.

Uses modular components for parsing, node operations, indexing, and scoring.
Supports multiple data files through schema configuration.
"""

import logging
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
import time
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer, get_scorer

from .models import (
    IndexRange, QueryStep, MatchedNode, TraversalStep, ExecutionResult, NodeItem
)
from .parser import QueryParser
from .node_utils import NodeUtils
from .index_handler import IndexHandler
from .predicate_handler import PredicateHandler
from .trace_writer import TraceWriter
from .schema_loader import load_config, get_data_path, load_schema


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
    - Multiple data files via schema configuration
    """
    
    def __init__(
        self, 
        scorer: PredicateScorer = None,
        scoring_method: str = None,
        top_k: int = None,
        score_threshold: float = None,
        config: dict = None,
        data_name: str = None,
        schema_name: str = None
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
            data_name: Name of the data file to use (e.g., "travel_memory_5day").
                      If None, uses active_data from config.yaml or schema's default.
            schema_name: Name of the schema to use. If None, uses active_schema from config.
        """
        if config is None:
            config = load_config()
        
        executor_config = config.get("xpath_executor", {})
        
        # Load configuration values
        self.scoring_method = scoring_method or executor_config.get("scoring_method", "llm")
        self.top_k = top_k if top_k is not None else executor_config.get("top_k", 5)
        self.score_threshold = score_threshold if score_threshold is not None else executor_config.get("score_threshold", 0.5)
        
        # Store schema and data configuration
        self.schema_name = schema_name
        self.data_name = data_name
        
        # Resolve data file path using schema loader
        self._memory_path = get_data_path(data_name=data_name, schema_name=schema_name)
        
        # Load schema for reference
        self._schema = load_schema(schema_name)
        
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
    def memory_path(self) -> Path:
        """Get the path to the data file."""
        return self._memory_path
    
    @property
    def tree(self) -> ET.ElementTree:
        """Lazy load the XML tree."""
        if self._tree is None:
            self._tree = ET.parse(self._memory_path)
            self._root = self._tree.getroot()
        return self._tree
    
    @property
    def root(self) -> ET.Element:
        """Get the root element."""
        if self._root is None:
            _ = self.tree  # Trigger lazy load
        return self._root
    
    @property
    def root_type(self) -> str:
        """Get the root element's tag name."""
        return self.root.tag
    
    def execute(self, query: str) -> ExecutionResult:
        """
        Execute an XPath-like query against the tree.
        
        Args:
            query: XPath-like query string
            
        Returns:
            ExecutionResult with matched nodes and execution log
        """
        start_time = time.perf_counter()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        execution_log = []
        scoring_traces = []
        traversal_steps = []
        
        execution_log.append(f"[{timestamp}] Executing query: {query}")
        execution_log.append(f"Data file: {self._memory_path.name}")
        
        # Parse the query
        steps, global_index = self.parser.parse(query)
        
        if global_index is not None:
            if global_index.is_range:
                execution_log.append(f"Global index range detected: [{global_index.start}:{global_index.end}]")
            else:
                execution_log.append(f"Global index detected: {global_index.start}")
        
        execution_log.append(f"Parsed steps: {steps}")
        
        # Execute BFS-like traversal with path and score tracking
        # Each item is a NodeItem with (node, path, score, parent_group_id)
        # Use dynamic root type instead of hardcoded "Itinerary"
        root_type = self.root_type
        current_items: List[NodeItem] = [NodeItem(self.root, root_type, 1.0, 0)]
        
        for step_idx, step in enumerate(steps):
            execution_log.append(f"\n--- Step {step_idx + 1}: {step} ---")
            
            # Dynamic root check - works with any root type
            if step.node_type == root_type:
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
        current_items.sort(key=lambda item: item.score, reverse=True)
        
        matched_nodes = [
            NodeUtils.node_to_matched(item.node, item.path, item.score) 
            for item in current_items
        ]
        
        # Calculate execution time
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000
        
        execution_log.append(f"\nFinal result: {len(matched_nodes)} nodes (sorted by score)")
        execution_log.append(f"⏱️  Query execution time: {execution_time_ms:.2f}ms")
        
        result = ExecutionResult(
            query=query,
            matched_nodes=matched_nodes,
            execution_log=execution_log,
            scoring_traces=scoring_traces,
            traversal_steps=traversal_steps,
            execution_time_ms=execution_time_ms,
            data_file=self._memory_path.name
        )
        
        # Save traces
        self.trace_writer.save_traces(timestamp, result)
        
        return result
    
    def _items_to_info(
        self, 
        items: List[NodeItem]
    ) -> List[dict]:
        """Convert items to info dictionaries for tracing."""
        return [
            NodeUtils.node_to_info_dict(item.node, item.path, item.score)
            for item in items
        ]
    
    def _handle_root_step(
        self,
        current_items: List[NodeItem],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[NodeItem], Optional[TraversalStep]]:
        """Handle the root step (works with any root type)."""
        root_type = self.root_type
        if current_items and current_items[0].node.tag == root_type:
            execution_log.append(f"Matched {root_type} root")
            traversal_step = TraversalStep(
                step_index=step_idx,
                step_query=str(step),
                nodes_before=[{"type": "root"}],
                nodes_after=[{"type": root_type, "path": root_type}],
                action="root_match",
                details={"matched": True}
            )
            return current_items, traversal_step
        else:
            execution_log.append(f"ERROR: Root is not {root_type}")
            return [], None
    
    def _apply_type_match(
        self,
        current_items: List[NodeItem],
        step: QueryStep,
        execution_log: List[str]
    ) -> List[NodeItem]:
        """
        Apply type matching to get children of specified type.
        
        Each parent node's children are assigned a unique parent_group_id,
        enabling local indexing like Day/POI[2] to select the 2nd POI
        within EACH Day rather than the global 2nd POI.
        """
        next_items = []
        for group_id, item in enumerate(current_items):
            children = list(item.node.findall(step.node_type))
            for child in children:
                child_name = NodeUtils.get_node_name(child)
                child_path = f"{item.path} > {child_name}"
                # Children inherit group_id from their parent's position
                next_items.append(NodeItem(child, child_path, item.score, group_id))
        
        execution_log.append(f"Found {len(next_items)} {step.node_type} nodes across {len(current_items)} parent(s)")
        return next_items
    
    def _apply_predicate_step(
        self,
        items: List[NodeItem],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[NodeItem], dict, TraversalStep]:
        """Apply semantic predicate filtering."""
        execution_log.append(f"Applying semantic predicate: {step.predicate}")
        
        nodes_before_pred = self._items_to_info(items)
        nodes_only = [item.node for item in items]
        
        filtered_nodes, scores_map, trace = self.predicate_handler.apply_semantic_predicate(
            nodes_only, step.predicate, execution_log
        )
        
        # Filter items and update scores, preserving parent_group_id
        filtered_set = set(id(n) for n in filtered_nodes)
        next_items = [
            NodeItem(item.node, item.path, scores_map.get(id(item.node), item.score), item.parent_group_id)
            for item in items if id(item.node) in filtered_set
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
        items: List[NodeItem],
        step: QueryStep,
        step_idx: int,
        execution_log: List[str]
    ) -> Tuple[List[NodeItem], TraversalStep]:
        """
        Apply positional index filtering with LOCAL semantics.
        
        Groups items by parent_group_id and applies the index to each group
        separately. This enables Day/POI[2] to return the 2nd POI in EACH Day.
        """
        execution_log.append(f"Applying positional index: {step.index}")
        
        nodes_before_idx = self._items_to_info(items)
        
        # Group items by parent_group_id for local indexing
        from collections import defaultdict
        groups = defaultdict(list)
        for item in items:
            groups[item.parent_group_id].append(item)
        
        # Apply index to each group separately
        next_items = []
        group_details = []
        
        for group_id in sorted(groups.keys()):
            group_items = groups[group_id]
            group_nodes = [item.node for item in group_items]
            
            # Apply index to this group's nodes
            indexed_nodes = IndexHandler.apply_index(group_nodes, step.index, execution_log)
            
            if indexed_nodes:
                indexed_set = set(id(n) for n in indexed_nodes)
                selected = [item for item in group_items if id(item.node) in indexed_set]
                next_items.extend(selected)
                group_details.append({
                    "group_id": group_id,
                    "group_size": len(group_items),
                    "selected_count": len(selected)
                })
        
        nodes_after_idx = self._items_to_info(next_items)
        
        traversal_step = TraversalStep(
            step_index=step_idx,
            step_query=str(step),
            nodes_before=nodes_before_idx,
            nodes_after=nodes_after_idx,
            action="positional_index",
            details={
                "index": step.index.to_dict(),
                "selected_count": len(next_items),
                "groups_processed": len(groups),
                "group_details": group_details
            }
        )
        
        return next_items, traversal_step
    
    def _apply_global_index(
        self,
        items: List[NodeItem],
        global_index: IndexRange,
        total_steps: int,
        execution_log: List[str]
    ) -> Tuple[List[NodeItem], TraversalStep]:
        """
        Apply global index to final result set.
        
        Unlike local indexing, global indexing treats ALL nodes as a single
        flat list, regardless of parent_group_id.
        """
        execution_log.append(f"\nApplying global index: {global_index}")
        
        nodes_before_global = self._items_to_info(items)
        nodes_only = [item.node for item in items]
        
        indexed_nodes = IndexHandler.apply_index(nodes_only, global_index, execution_log)
        
        if indexed_nodes:
            indexed_set = set(id(n) for n in indexed_nodes)
            next_items = [item for item in items if id(item.node) in indexed_set]
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
