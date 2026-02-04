"""
Predicate Handler - Applies semantic predicate scoring to nodes.

Paper Formalization - Score(u, ψ):
The Score function is defined recursively over predicate structure:

  Score(u, ψ) = {
    Atom(u, φ)                           if ψ = φ (atomic predicate)
    min{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∧ ψ₂ (conjunction)
    max{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∨ ψ₂ (disjunction)
    1 - Score(u, ψ)                      if ψ = ¬ψ (negation)
  }

Atomic Predicate Evaluation - Atom(u, φ):
- Local: Atom(u, φ) evaluated from attr(u) - the node's own content
- Hierarchical: Atom(u, φ) = Agg({Atom(x, φ) | x ∈ Sφ(u)}) where Sφ(u) ⊆ Desc(u)

Aggregation Operators:
- Agg∃(A) = max A              (AGG_EXISTS - existential "at least one")
- Aggprev(A) = (1/|A|) ∑ A     (AGG_PREV - prevalence "on average")

Operator Mapping:
- ATOM: Local atomic predicate - Atom(u, φ) from attr(u)
- AND: Conjunction ψ₁ ∧ ψ₂ - min of scores
- OR: Disjunction ψ₁ ∨ ψ₂ - max of scores
- NOT: Negation ¬ψ - 1 minus score
- AGG_EXISTS: Hierarchical with Agg∃ - max over children
- AGG_PREV: Hierarchical with Aggprev - average over children

Batch Optimization:
- Collects all descriptions for the same atomic value across all nodes
- Makes one scorer call per unique atomic value
- Reduces N*M calls to just M calls (where M = unique atomic values)
"""

import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer
from .node_utils import NodeUtils
from .models import CompoundPredicate, AtomicPredicate


# Small epsilon to avoid log(0) and division by zero
EPSILON = 1e-9

# Type alias for scoring task: (node_id, desc_id, description_dict)
ScoringTask = Tuple[int, str, Dict[str, Any]]


class PredicateHandler:
    """
    Implements the recursive Score(u, ψ) function from paper formalization.
    
    Paper Formalization:
    - Score(u, ψ) recursively evaluates predicates over node u
    - Atom(u, φ) evaluates atomic predicates (local or hierarchical)
    
    Operator Scoring:
    - ATOM: Atom(u, φ) - local node content scoring
    - OR: max{Score(u, ψ₁), Score(u, ψ₂)} - disjunction
    - AND: min{Score(u, ψ₁), Score(u, ψ₂)} - conjunction
    - NOT: 1 - Score(u, ψ) - negation
    - AGG_EXISTS: Agg∃({Atom(x, φ) | x ∈ Sφ(u)}) = max - existential
    - AGG_PREV: Aggprev({Atom(x, φ) | x ∈ Sφ(u)}) = avg - prevalence
    """
    
    def __init__(
        self,
        scorer: PredicateScorer,
        top_k: int = 5,
        score_threshold: float = 0.5,
        schema: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the predicate handler.
        
        Args:
            scorer: PredicateScorer implementation (LLM, Entailment, or Cosine)
            top_k: Maximum number of nodes to return
            score_threshold: Minimum score threshold
            schema: Full schema dict with node definitions including 'children' field
        """
        self.scorer = scorer
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.schema = schema or {}
        
        # Extract node configs for quick lookup
        self._node_configs: Dict[str, Dict[str, Any]] = self.schema.get("nodes", {})
        
        # Create schema-aware NodeUtils instance for dynamic field lookup
        self._node_utils = NodeUtils(self.schema)
        
        # Cache for scores: (node_id, semantic_value) -> score
        self._score_cache: Dict[Tuple[int, str], float] = {}
        
        # Track node descriptions
        self._node_descriptions: Dict[int, List[str]] = {}
    
    def _get_allowed_children(self, node_type: str) -> List[str]:
        """Get the allowed child types for a node type from schema."""
        node_config = self._node_configs.get(node_type, {})
        return node_config.get("children", [])
    
    def _get_hierarchical_children(
        self, 
        node: ET.Element, 
        child_type: Optional[str] = None,
        axis: str = "child"
    ) -> List[ET.Element]:
        """
        Get hierarchical children or descendants of a node.
        
        Uses schema's 'children' field to distinguish structural children
        from the node's own fields (like name, description, etc.).
        
        Args:
            node: XML element
            child_type: Optional specific child type to filter for
            axis: "child" for direct children, "desc" for all descendants
            
        Returns:
            List of child/descendant elements that are recognized as structural
        """
        if axis == "desc":
            # Descendant axis: find all descendants of the specified type
            if child_type:
                # Get all descendants of the specified type (excluding self)
                return [n for n in node.iter(child_type) if n is not node]
            else:
                # Get all descendants (excluding self)
                # Filter to only include allowed children types recursively
                allowed_children = self._get_allowed_children(node.tag)
                if allowed_children:
                    result = []
                    for n in node.iter():
                        if n is not node and n.tag in self._get_all_structural_types():
                            result.append(n)
                    return result
                return list(node.iter())[1:]  # All descendants except self
        else:
            # Child axis (default): direct children only
            if child_type:
                return list(node.findall(child_type))
            
            # Use schema's children definition for this node type
            allowed_children = self._get_allowed_children(node.tag)
            
            if allowed_children:
                return [child for child in node if child.tag in allowed_children]
            else:
                # Leaf node or no children defined - return empty
                return []
    
    def _get_all_structural_types(self) -> set:
        """Get all node types defined in the schema."""
        return set(self._node_configs.keys())
    
    def _recursive_subtree_score(
        self,
        node: ET.Element,
        child_predicate: CompoundPredicate,
        agg_operator: str,  # "EXISTS" or "PREV"
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> Tuple[float, int, Optional[Dict]]:
        """
        Recursively aggregate scores from node and its entire subtree.
        
        Bottom-up aggregation: scores leaf nodes first, then propagates up
        combining each node's own score with its descendants' scores.
        
        Args:
            node: XML element to score
            child_predicate: Predicate to evaluate at each node
            agg_operator: "EXISTS" (max, no weighting) or "PREV" (weighted avg)
            trace_steps: List to record scoring trace
            execution_log: Execution log for debugging
            
        Returns:
            Tuple of (aggregated_score, subtree_size, best_match_details) where:
            - aggregated_score: Combined score for this node and all descendants
            - subtree_size: Number of nodes in subtree (1 + sum of children sizes)
            - best_match_details: Scoring details of the node that contributed max score (for EXISTS)
        """
        # 1. Score this node's own content against the predicate
        # Capture detailed trace for this node's match
        node_match_trace = []
        own_score = self.score(node, child_predicate, node_match_trace, execution_log)
        
        # Structure the match details
        current_node_details = {
             "type": "node_match",
             "node_name": self._node_utils.get_name(node),
             "score": own_score,
             "trace": node_match_trace
        }
        
        # 2. Get ALL hierarchical children (not filtered by type)
        children = self._get_hierarchical_children(node, child_type=None)
        
        if not children:
            # Leaf node - return own score and size=1
            return (own_score, 1, current_node_details)
        
        # 3. Recursively get (score, size) from all children
        child_results: List[Tuple[float, int, Optional[Dict]]] = []
        for child in children:
            child_score, child_size, child_details = self._recursive_subtree_score(
                child, child_predicate, agg_operator, trace_steps, execution_log
            )
            child_results.append((child_score, child_size, child_details))
        
        # 4. Calculate subtree size: 1 (self) + sum of children sizes
        total_children_size = sum(size for _, size, _ in child_results)
        subtree_size = 1 + total_children_size
        
        # 5. Aggregate based on operator
        best_match = current_node_details
        
        if agg_operator == "EXISTS":
            # Max - no weighting (max is max)
            # Find max score and keeping track of which node/branch produced it
            max_score = own_score
            
            for c_score, c_size, c_details in child_results:
                if c_score > max_score:
                    max_score = c_score
                    best_match = c_details
            
            result = max_score
        else:  # PREV - weighted average by subtree size
            # own_score has weight 1 (just this node)
            # each child has weight = its subtree size
            weighted_sum = own_score * 1
            total_weight = 1
            for child_score, child_size, _ in child_results:
                weighted_sum += child_score * child_size
                total_weight += child_size
            result = weighted_sum / total_weight
            best_match = None # Concept applies less to avg
        
        return (result, subtree_size, best_match)
    
    # =========================================================================
    # Main Entry Point
    # =========================================================================
    
    def apply_semantic_predicate(
        self, 
        nodes: List[ET.Element], 
        predicate: CompoundPredicate,
        execution_log: List[str] = None
    ) -> Tuple[List[ET.Element], Dict[int, float], Dict[str, Any]]:
        """
        Apply semantic predicate scoring to nodes.
        
        Uses batch optimization for efficient scoring.
        
        Args:
            nodes: List of XML elements to score
            predicate: CompoundPredicate AST
            execution_log: Optional list to append log messages
            
        Returns:
            - all nodes (no filtering - deferred to executor)
            - scores_map: dict mapping node id() to score
            - trace: detailed scoring trace
        """
        if execution_log is None:
            execution_log = []
        
        # Clear caches
        self._score_cache.clear()
        self._node_descriptions.clear()
        
        # Collect all atomic predicate values for logging
        atomic_values = predicate.get_all_atomic_values()
        execution_log.append(
            f"Scoring predicate: {predicate} (atomic values: {atomic_values})"
        )
        
        # Build trace structure
        trace = {
            "predicate": str(predicate),
            "predicate_ast": predicate.to_dict(),
            "config": {
                "top_k": self.top_k,
                "score_threshold": self.score_threshold
            },
            "node_scores": [],
            "batch_scoring": {}
        }
        
        # Phase 1: Collect all scoring tasks
        scoring_tasks = self._collect_scoring_tasks(nodes, predicate)
        
        execution_log.append(
            f"  Collected {sum(len(t) for t in scoring_tasks.values())} descriptions "
            f"for {len(scoring_tasks)} unique semantic value(s)"
        )
        
        # Phase 2: Batch score all semantics
        batch_stats = self._batch_score_semantics(scoring_tasks, trace)
        
        execution_log.append(
            f"  Made {batch_stats['total_scorer_calls']} scorer call(s) "
            f"for {batch_stats['total_descriptions_scored']} total descriptions"
        )
        
        # Phase 3: Compute final scores using recursive Score(u, ψ)
        scores_map: Dict[int, float] = {}
        
        for idx, node in enumerate(nodes):
            node_name = self._node_utils.get_name(node)
            node_trace = {
                "node_idx": idx,
                "node_name": node_name,
                "node_type": node.tag,
                "scoring_steps": []
            }
            
            # Paper: Score(u, ψ) - recursive predicate evaluation
            score = self.score(
                node, predicate, node_trace["scoring_steps"], execution_log
            )
            
            scores_map[id(node)] = score
            node_trace["final_score"] = score
            trace["node_scores"].append(node_trace)
            
            execution_log.append(
                f"  Node {idx} ({node_name}): score = {score:.4f}"
            )
        
        # Add ranking info
        sorted_nodes = sorted(
            [(idx, scores_map[id(node)], self._node_utils.get_name(node)) 
             for idx, node in enumerate(nodes)],
            key=lambda x: x[1],
            reverse=True
        )
        
        trace["ranking"] = [
            {"idx": idx, "score": score, "name": name}
            for idx, score, name in sorted_nodes
        ]
        
        return nodes, scores_map, trace
    
    # =========================================================================
    # Phase 1: Collect Scoring Tasks
    # =========================================================================
    
    def _collect_scoring_tasks(
        self,
        nodes: List[ET.Element],
        predicate: CompoundPredicate
    ) -> Dict[str, List[ScoringTask]]:
        """Collect all scoring tasks grouped by semantic value."""
        tasks: Dict[str, List[ScoringTask]] = defaultdict(list)
        self._node_descriptions.clear()
        
        for node in nodes:
            self._collect_tasks_for_node(node, predicate, tasks)
        
        return tasks
    
    def _collect_tasks_for_node(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """
        Recursively collect scoring tasks for a node.
        
        Paper: Traverses predicate structure to find all Atom(u, φ) evaluations needed.
        """
        if predicate.operator == "ATOM":
            # ATOM: score node's own content (local atomic predicate)
            if predicate.conditions:
                condition = predicate.conditions[0]
                if isinstance(condition, AtomicPredicate):
                    self._add_node_content_to_tasks(node, condition.value, tasks)
        
        elif predicate.operator in ("AND", "OR"):
            # Conjunction/Disjunction: collect from all sub-predicates
            for cond in predicate.conditions:
                if isinstance(cond, CompoundPredicate):
                    self._collect_tasks_for_node(node, cond, tasks)
        
        elif predicate.operator == "NOT":
            # Negation: collect from inner predicate
            if predicate.conditions:
                for cond in predicate.conditions:
                    if isinstance(cond, CompoundPredicate):
                        self._collect_tasks_for_node(node, cond, tasks)
        
        elif predicate.operator in ("AGG_EXISTS", "AGG_PREV"):
            # Hierarchical: collect from children/descendants AND their entire subtrees
            # for recursive bottom-up aggregation
            if predicate.child_predicate:
                child_axis = getattr(predicate, 'child_axis', 'child')
                children = self._get_hierarchical_children(
                    node, predicate.child_type, axis=child_axis
                )
                for child in children:
                    # Collect for child AND all its descendants (recursive subtree)
                    self._collect_subtree_tasks(child, predicate.child_predicate, tasks)
    
    def _collect_subtree_tasks(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """
        Recursively collect scoring tasks for node and ALL descendants.
        
        Used by AGG_EXISTS/AGG_PREV to collect tasks for the entire subtree
        so that recursive bottom-up aggregation can score all nodes.
        """
        # Collect for this node
        self._collect_tasks_for_node(node, predicate, tasks)
        
        # Recurse into all hierarchical children (any type)
        children = self._get_hierarchical_children(node, child_type=None)
        for child in children:
            self._collect_subtree_tasks(child, predicate, tasks)
    
    def _add_node_content_to_tasks(
        self,
        node: ET.Element,
        semantic_value: str,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """Add a node's content to scoring tasks.
        
        For container nodes (like Day), aggregates full content from all children.
        For leaf nodes, builds comprehensive content from ALL schema-defined fields
        (not just description) to enable temporal/cost-aware semantic matching.
        """
        node_id = id(node)
        
        # Skip if already added
        if any(t[0] == node_id for t in tasks.get(semantic_value, [])):
            return
        
        node_name = self._node_utils.get_name(node)
        
        # For container nodes, build comprehensive description from all children
        if NodeUtils._is_container_node(node):
            # Aggregate full content from all structured children
            parts = []
            for child in node:
                if NodeUtils._is_structured_node(child):
                    # Use schema-aware field lookup for child name/desc
                    child_name = self._node_utils.get_field_value(child, "name")
                    child_desc = self._node_utils.get_field_value(child, "desc")
                    if child_name and child_desc:
                        parts.append(f"{child.tag}: {child_name} - {child_desc}")
                    elif child_name:
                        parts.append(f"{child.tag}: {child_name}")
                    elif child_desc:
                        parts.append(f"{child.tag}: {child_desc}")
            
            # Use aggregated description if available, otherwise fallback
            node_desc = "; ".join(parts) if parts else self._node_utils.get_description(node)
        else:
            # For leaf nodes, build content from ALL schema-defined fields
            node_desc = self._build_leaf_node_content(node)
        
        desc_ids = []
        
        if node_desc:
            desc_id = "main"
            desc_ids.append(desc_id)
            tasks[semantic_value].append((
                node_id,
                desc_id,
                {
                    "id": f"{node_id}_{desc_id}",
                    "type": node.tag,
                    "name": node_name,
                    "description": node_desc
                }
            ))
        
        self._node_descriptions[node_id] = desc_ids
    
    def _build_leaf_node_content(self, node: ET.Element) -> str:
        """
        Build comprehensive content string for a leaf node using schema-defined fields.
        
        Uses the schema's 'fields' list for the node type to include ALL relevant
        fields (name, time_block, description, expected_cost, etc.) in the content
        string. This enables semantic matching that considers temporal and cost context.
        
        Args:
            node: XML element (leaf node like POI, Restaurant)
            
        Returns:
            Content string with all field values, formatted as "field: value" pairs
        """
        node_type = node.tag
        node_config = self._node_configs.get(node_type, {})
        schema_fields = node_config.get("fields", [])
        
        parts = []
        
        if schema_fields:
            # Use schema-defined fields
            for field_name in schema_fields:
                elem = node.find(field_name)
                if elem is not None:
                    if len(elem) == 0 and elem.text:
                        # Simple text field
                        parts.append(f"{field_name}: {elem.text}")
                    elif len(elem) > 0:
                        # List field (like highlights)
                        items = [child.text for child in elem if child.text]
                        if items:
                            parts.append(f"{field_name}: {', '.join(items)}")
        else:
            # Fallback: extract all text child elements
            for child in node:
                if len(child) == 0 and child.text:
                    parts.append(f"{child.tag}: {child.text}")
                elif len(child) > 0 and all(len(gc) == 0 for gc in child):
                    # Simple list
                    items = [gc.text for gc in child if gc.text]
                    if items:
                        parts.append(f"{child.tag}: {', '.join(items)}")
        
        return " | ".join(parts) if parts else self._node_utils.get_description(node)
    
    # =========================================================================
    # Phase 2: Batch Score Semantics
    # =========================================================================
    
    def _batch_score_semantics(
        self,
        scoring_tasks: Dict[str, List[ScoringTask]],
        trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call scorer once per unique semantic value."""
        batch_stats = {
            "semantic_values": list(scoring_tasks.keys()),
            "per_value_stats": [],
            "total_scorer_calls": 0,
            "total_descriptions_scored": 0
        }
        
        # Track total token usage
        total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for semantic_value, tasks in scoring_tasks.items():
            if not tasks:
                continue
            
            start_time = time.perf_counter()
            
            desc_dicts = [task[2] for task in tasks]
            batch_result = self.scorer.score_batch(desc_dicts, semantic_value)
            
            # Accumulate token usage if present
            if hasattr(batch_result, "token_usage") and batch_result.token_usage:
                for k in total_token_usage:
                    total_token_usage[k] += batch_result.token_usage.get(k, 0)
            
            call_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Store scores in cache
            for i, task in enumerate(tasks):
                node_id, desc_id, _ = task
                score = batch_result.results[i].score if i < len(batch_result.results) else 0
                score = max(EPSILON, min(1 - EPSILON, score))
                self._score_cache[(node_id, semantic_value)] = score
            
            batch_stats["per_value_stats"].append({
                "value": semantic_value,
                "num_descriptions": len(tasks),
                "call_time_ms": round(call_time_ms, 2)
            })
            batch_stats["total_scorer_calls"] += 1
            batch_stats["total_descriptions_scored"] += len(tasks)
        
        # Store accumulated token usage in trace
        trace["batch_scoring"] = batch_stats
        trace["token_usage"] = total_token_usage if total_token_usage["total_tokens"] > 0 else None
        
        return batch_stats
    
    # =========================================================================
    # Phase 3: Recursive Score Computation - Score(u, ψ)
    # =========================================================================
    
    def score(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Recursively score a predicate against a node.
        
        Paper Formalization - Score(u, ψ):
          Score(u, ψ) = {
            Atom(u, φ)                           if ψ = φ (atomic)
            min{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∧ ψ₂ (AND)
            max{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∨ ψ₂ (OR)
            1 - Score(u, ψ)                      if ψ = ¬ψ (NOT)
          }
        
        Args:
            node: XML element u to evaluate
            predicate: Predicate expression ψ
            trace_steps: List to record scoring trace
            execution_log: Execution log for debugging
            
        Returns:
            Score in [0, 1]
        """
        if predicate.operator == "ATOM":
            return self._score_atom(node, predicate, trace_steps)
        
        elif predicate.operator == "OR":
            return self._score_or(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AND":
            return self._score_and(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "NOT":
            return self._score_not(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AGG_EXISTS":
            return self._score_agg_exists(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AGG_PREV":
            return self._score_agg_prev(node, predicate, trace_steps, execution_log)
        
        return 0
    
    def _score_atom(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict]
    ) -> float:
        """
        Score atomic predicate - Atom(u, φ) from attr(u).
        
        Paper Formalization:
        - Local atomic predicates evaluate the node's OWN content
        - Atom(u, φ) = Pr(Zᵤ(φ) = 1 | attr(u))
        - This is distinct from hierarchical predicates that aggregate over Desc(u)
        """
        if not predicate.conditions:
            return 0
        
        condition = predicate.conditions[0]
        if not isinstance(condition, AtomicPredicate):
            return 0
        
        node_id = id(node)
        cache_key = (node_id, condition.value)
        score = self._score_cache.get(cache_key, 0)
        
        trace_steps.append({
            "type": "atom",
            "condition": condition.to_dict(),
            "score": score,
            "note": "Atom(u, φ) - local node content from attr(u)"
        })
        
        return score
    
    def _score_or(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score disjunction: ψ₁ ∨ ψ₂
        
        Paper: Score(u, ψ₁ ∨ ψ₂) = max{Score(u, ψ₁), Score(u, ψ₂)}
        """
        trace_steps_list = []
        child_scores = []
        
        for cond in predicate.conditions:
            inner_trace = []
            if isinstance(cond, CompoundPredicate):
                s = self.score(node, cond, inner_trace, execution_log)
            else:
                s = 0
            child_scores.append(s)
            trace_steps_list.append(inner_trace)
        
        result = max(child_scores) if child_scores else 0
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "or",
            "formula": "max{Score(u, ψ_j)}",
            "child_scores": child_scores,
            "inner_traces": trace_steps_list,
            "result": result
        })
        
        return result
    
    def _score_and(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score conjunction: ψ₁ ∧ ψ₂
        
        Paper: Score(u, ψ₁ ∧ ψ₂) = min{Score(u, ψ₁), Score(u, ψ₂)}
        """
        trace_steps_list = []
        child_scores = []
        
        for cond in predicate.conditions:
            inner_trace = []
            if isinstance(cond, CompoundPredicate):
                s = self.score(node, cond, inner_trace, execution_log)
            else:
                s = 0
            child_scores.append(s)
            trace_steps_list.append(inner_trace)
        
        result = min(child_scores) if child_scores else 0
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "and",
            "formula": "min{Score(u, ψ_j)}",
            "child_scores": child_scores,
            "inner_traces": trace_steps_list,
            "result": result
        })
        
        return result
    
    def _score_not(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score negation: ¬ψ
        
        Paper: Score(u, ¬ψ) = 1 - Score(u, ψ)
        """
        if not predicate.conditions:
            return 0
        
        inner_cond = predicate.conditions[0]
        inner_trace = []
        if isinstance(inner_cond, CompoundPredicate):
            inner_score = self.score(node, inner_cond, inner_trace, execution_log)
        else:
            inner_score = 0
        
        result = 1 - inner_score
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "not",
            "formula": "1 - Score(u, ψ)",
            "inner_score": inner_score,
            "inner_trace": inner_trace,
            "result": result
        })
        
        return result
    
    def _score_agg_exists(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Hierarchical predicate with existential aggregation and recursive subtree scoring.
        
        Paper Formalization (extended for recursive aggregation):
        - For each child x ∈ Sφ(u), recursively aggregate its subtree with max
        - Agg∃(A) = max A (no weighting - max is max)
        - Sφ(u) ⊆ Desc(u) is the set of evidence nodes (children of specified type)
        
        Semantics: "At least one node in the subtree matches" - returns max score
        across all nodes in all child subtrees.
        """
        if not predicate.child_predicate:
            return 0
        
        # Sφ(u) - evidence nodes (children/descendants of specified type)
        child_axis = getattr(predicate, 'child_axis', 'child')
        children = self._get_hierarchical_children(
            node, predicate.child_type, axis=child_axis
        )
        
        if not children:
            # Empty evidence set - return neutral
            trace_steps.append({
                "type": "agg_exists",
                "child_type": predicate.child_type or "*",
                "child_axis": child_axis,
                "num_children": 0,
                "note": "Sφ(u) is empty - no children/descendants found",
                "result": 0
            })
            return 0
        
        # Recursively score each child's entire subtree
        # Each child returns (score, subtree_size, best_match)
        child_results: List[Tuple[float, int, Optional[Dict]]] = []
        for child in children:
            score, size, details = self._recursive_subtree_score(
                child, predicate.child_predicate, "EXISTS", trace_steps, execution_log
            )
            child_results.append((score, size, details))
        
        # Agg∃(A) = max A (no weighting for EXISTS)
        # Find which child/subtree provided the max score
        max_score = -1.0
        best_details = None
        
        for s, _, d in child_results:
            if s > max_score:
                max_score = s
                best_details = d
                
        result = max(EPSILON, min(1 - EPSILON, max_score)) if child_results else 0
        
        trace_steps.append({
            "type": "agg_exists_recursive",
            "formula": "Agg∃(A) = max(recursive_subtree_scores)",
            "child_type": predicate.child_type or "*",
            "child_axis": child_axis,
            "num_children": len(children),
            "child_results": [{"score": s, "subtree_size": sz} for s, sz, _ in child_results],
            "best_match_details": best_details,
            "result": result
        })
        
        return result
    
    def _score_agg_prev(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Hierarchical predicate with prevalence aggregation and weighted recursive scoring.
        
        Paper Formalization (extended for weighted recursive aggregation):
        - For each child x ∈ Sφ(u), recursively aggregate its subtree with weighted avg
        - Aggprev uses WEIGHTED average where weight = subtree size
        - More subnodes = more weight (fair representation for unbalanced trees)
        
        Semantics: "General prevalence across subtree" - returns weighted average
        where branches with more content contribute proportionally more.
        """
        if not predicate.child_predicate:
            return 0
        
        # Sφ(u) - evidence nodes (children/descendants of specified type)
        child_axis = getattr(predicate, 'child_axis', 'child')
        children = self._get_hierarchical_children(
            node, predicate.child_type, axis=child_axis
        )
        
        if not children:
            # Empty evidence set - return neutral
            trace_steps.append({
                "type": "agg_prev",
                "child_type": predicate.child_type or "*",
                "child_axis": child_axis,
                "num_children": 0,
                "note": "Sφ(u) is empty - no children/descendants found",
                "result": 0
            })
            return 0
        
        # Recursively score each child's entire subtree with weighted aggregation
        # Each child returns (score, subtree_size) for weighting
        child_results: List[Tuple[float, int]] = []
        for child in children:
            score, size = self._recursive_subtree_score(
                child, predicate.child_predicate, "PREV", trace_steps, execution_log
            )
            child_results.append((score, size))
        
        # Weighted average: weight = subtree size
        # More subnodes = more weight
        weighted_sum = sum(score * size for score, size in child_results)
        total_weight = sum(size for _, size in child_results)
        result = weighted_sum / total_weight if total_weight > 0 else 0
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "agg_prev_weighted",
            "formula": "Aggprev(A) = Σ(score_i × size_i) / Σ(size_i)",
            "child_type": predicate.child_type or "*",
            "child_axis": child_axis,
            "num_children": len(children),
            "child_results": [{"score": s, "subtree_size": sz} for s, sz in child_results],
            "weighted_sum": weighted_sum,
            "total_weight": total_weight,
            "result": result
        })
        
        return result
