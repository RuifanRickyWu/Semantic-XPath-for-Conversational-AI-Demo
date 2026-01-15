"""
Predicate Handler - Applies semantic predicate scoring to nodes.

Implements the Semantic XPath scoring framework with batch optimization:
- AND (Conjunction): Log-odds aggregation with sigmoid
- OR (Disjunction): Noisy-OR model
- EXISTS (Existential): Noisy-OR over children
- ALL (Universal): Beta-Bernoulli posterior mean

Batch Optimization:
- Collects all descriptions for the same predicate value across all nodes
- Makes one scorer call per unique predicate value
- Reduces N*M calls to just M calls (where M = unique predicate values)
"""

import math
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer
from .node_utils import NodeUtils
from .models import CompoundPredicate, AtomicCondition


# Small epsilon to avoid log(0) and division by zero
EPSILON = 1e-9


# Type alias for scoring task: (node_id, desc_id, description_dict)
ScoringTask = Tuple[int, str, Dict[str, Any]]


class PredicateHandler:
    """
    Handles semantic predicate matching using a scorer.
    
    Implements probabilistic scoring per the Semantic XPath framework:
    - Atomic: Direct model scoring (batched per predicate value)
    - OR (Noisy-OR): π(p) = 1 - ∏(1 - π(cj))
    - AND (Log-odds): π(p) = σ(Σ log(π/(1-π)))
    - EXISTS: π(p) = 1 - ∏_{ch}(1 - π_u(p))
    - ALL (Beta-Bernoulli): π(p) = (α + Σπ_u) / (α + β + n)
    
    Batch Optimization:
    - Phase 1: Collect all (predicate_value -> descriptions) across all nodes
    - Phase 2: Call scorer once per unique predicate value
    - Phase 3: Compose scores using cached atomic results
    """
    
    # Beta-Bernoulli prior parameters (uninformative prior)
    BETA_ALPHA = 1.0
    BETA_BETA = 1.0
    
    def __init__(
        self,
        scorer: PredicateScorer,
        top_k: int = 5,
        score_threshold: float = 0.5,
        schema_node_types: Optional[Set[str]] = None
    ):
        """
        Initialize the predicate handler.
        
        Args:
            scorer: PredicateScorer implementation (LLM, Entailment, or Cosine)
            top_k: Maximum number of nodes to return (used for step-level filtering)
            score_threshold: Minimum score threshold (used for step-level filtering)
            schema_node_types: Set of recognized node types from schema (e.g., {"Day", "POI", "Restaurant"})
                              Used to distinguish hierarchical children from XML sub-elements.
        """
        self.scorer = scorer
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.schema_node_types = schema_node_types or set()
        
        # Cache for atomic scores: (node_id, predicate_value) -> mean_score
        self._atomic_score_cache: Dict[Tuple[int, str], float] = {}
        
        # Detailed cache: (node_id, desc_id, predicate_value) -> individual_score
        self._detailed_score_cache: Dict[Tuple[int, str, str], float] = {}
        
        # Track which descriptions belong to which node
        self._node_descriptions: Dict[int, List[str]] = {}  # node_id -> list of desc_ids
    
    def _get_hierarchical_children(self, node: ET.Element, child_type: Optional[str] = None) -> List[ET.Element]:
        """
        Get hierarchical children of a node (filtering out XML sub-elements).
        
        For container nodes like Day, returns children like POI, Restaurant.
        For leaf nodes like POI, returns empty list (name, description are not hierarchical children).
        
        Args:
            node: XML element
            child_type: Optional specific child type to filter for
            
        Returns:
            List of child elements that are recognized node types
        """
        if child_type:
            return list(node.findall(child_type))
        
        # Filter to only include recognized node types from schema
        if self.schema_node_types:
            return [child for child in node if child.tag in self.schema_node_types]
        else:
            # Fallback: return all children (old behavior)
            return list(node)
    
    # =========================================================================
    # Phase 1: Collect Scoring Tasks
    # =========================================================================
    
    def _collect_scoring_tasks(
        self,
        nodes: List[ET.Element],
        predicate: CompoundPredicate
    ) -> Dict[str, List[ScoringTask]]:
        """
        Recursively collect all scoring tasks grouped by predicate value.
        
        This method traverses the predicate AST and collects all (node, description)
        pairs that need to be scored for each unique predicate value.
        
        For EXISTS/ALL, also collects children's descriptions.
        
        Args:
            nodes: List of XML elements to score
            predicate: CompoundPredicate AST
            
        Returns:
            Dict mapping predicate_value to list of (node_id, desc_id, desc_dict)
        """
        tasks: Dict[str, List[ScoringTask]] = defaultdict(list)
        
        # Clear node descriptions tracking
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
        Recursively collect scoring tasks for a single node.
        
        Args:
            node: XML element to collect tasks for
            predicate: CompoundPredicate AST
            tasks: Dict to accumulate tasks into
        """
        if predicate.operator == "ATOMIC":
            # Collect descriptions for this atomic condition
            condition = predicate.conditions[0]
            self._add_node_descriptions_to_tasks(node, condition.value, tasks)
        
        elif predicate.operator in ("AND", "OR"):
            # Recursively collect for all child conditions
            for cond in predicate.conditions:
                if isinstance(cond, CompoundPredicate):
                    self._collect_tasks_for_node(node, cond, tasks)
                elif isinstance(cond, AtomicCondition):
                    self._add_node_descriptions_to_tasks(node, cond.value, tasks)
        
        elif predicate.operator in ("EXISTS", "ALL"):
            # Collect for children - use hierarchical children (not XML sub-elements)
            if predicate.child_predicate:
                children = self._get_hierarchical_children(node, predicate.child_type)
                
                if children:
                    # Container node - collect from children
                    for child in children:
                        self._collect_tasks_for_node(child, predicate.child_predicate, tasks)
                else:
                    # Leaf node - collect from node itself using inner predicate
                    self._collect_tasks_for_node(node, predicate.child_predicate, tasks)
    
    def _add_node_descriptions_to_tasks(
        self,
        node: ET.Element,
        predicate_value: str,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """
        Add a node's descriptions to the scoring tasks.
        
        Args:
            node: XML element
            predicate_value: The predicate value to score against
            tasks: Dict to add tasks to
        """
        node_id = id(node)
        
        # Skip if we've already added this node's descriptions for this predicate
        cache_key = (node_id, predicate_value)
        if any(t[0] == node_id for t in tasks.get(predicate_value, [])):
            return
        
        # Get node descriptions
        node_desc = NodeUtils.get_node_description(node)
        node_name = NodeUtils.get_node_name(node)
        subtree_descs = NodeUtils.get_subtree_descriptions(node)
        
        # Track descriptions for this node
        desc_ids = []
        
        # Add main node description
        if node_desc:
            desc_id = "main"
            desc_ids.append(desc_id)
            tasks[predicate_value].append((
                node_id,
                desc_id,
                {
                    "id": f"{node_id}_{desc_id}",
                    "type": node.tag,
                    "name": node_name,
                    "description": node_desc
                }
            ))
        
        # Add subtree descriptions
        for sub_idx, (sub_type, sub_name, sub_desc) in enumerate(subtree_descs):
            if sub_desc:
                desc_id = f"sub_{sub_idx}"
                desc_ids.append(desc_id)
                tasks[predicate_value].append((
                    node_id,
                    desc_id,
                    {
                        "id": f"{node_id}_{desc_id}",
                        "type": sub_type,
                        "name": sub_name,
                        "description": sub_desc
                    }
                ))
        
        # Track which descriptions belong to this node
        if node_id not in self._node_descriptions:
            self._node_descriptions[node_id] = desc_ids
    
    # =========================================================================
    # Phase 2: Batch Score Atomics
    # =========================================================================
    
    def _batch_score_atomics(
        self,
        scoring_tasks: Dict[str, List[ScoringTask]],
        trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call scorer once per unique predicate value and build cache.
        
        Args:
            scoring_tasks: Dict mapping predicate_value to list of tasks
            trace: Dict to add batch scoring stats to
            
        Returns:
            Batch scoring statistics
        """
        batch_stats = {
            "predicate_values": list(scoring_tasks.keys()),
            "per_predicate_stats": [],
            "total_scorer_calls": 0,
            "total_descriptions_scored": 0
        }
        
        for predicate_value, tasks in scoring_tasks.items():
            if not tasks:
                continue
            
            start_time = time.perf_counter()
            
            # Extract just the description dicts for scoring
            desc_dicts = [task[2] for task in tasks]
            
            # Call scorer once for this predicate value
            batch_result = self.scorer.score_batch(desc_dicts, predicate_value)
            
            end_time = time.perf_counter()
            call_time_ms = (end_time - start_time) * 1000
            
            # Store individual scores in detailed cache
            for i, task in enumerate(tasks):
                node_id, desc_id, _ = task
                score = batch_result.results[i].score if i < len(batch_result.results) else 0.5
                self._detailed_score_cache[(node_id, desc_id, predicate_value)] = score
            
            # Compute mean scores per node and store in atomic cache
            node_scores: Dict[int, List[float]] = defaultdict(list)
            for i, task in enumerate(tasks):
                node_id, desc_id, _ = task
                score = batch_result.results[i].score if i < len(batch_result.results) else 0.5
                node_scores[node_id].append(score)
            
            for node_id, scores in node_scores.items():
                mean_score = sum(scores) / len(scores) if scores else 0.5
                mean_score = max(EPSILON, min(1 - EPSILON, mean_score))
                self._atomic_score_cache[(node_id, predicate_value)] = mean_score
            
            # Track stats
            batch_stats["per_predicate_stats"].append({
                "value": predicate_value,
                "num_descriptions": len(tasks),
                "num_nodes": len(node_scores),
                "call_time_ms": round(call_time_ms, 2)
            })
            batch_stats["total_scorer_calls"] += 1
            batch_stats["total_descriptions_scored"] += len(tasks)
        
        trace["batch_scoring"] = batch_stats
        return batch_stats
    
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
        Apply compound semantic predicate scoring to nodes.
        
        Uses two-phase batch optimization:
        1. Collect all descriptions for each unique predicate value
        2. Call scorer once per predicate value
        3. Compose final scores using cached atomic results
        
        Args:
            nodes: List of XML elements to score
            predicate: CompoundPredicate AST defining the predicate structure
            execution_log: Optional list to append log messages
            
        Returns:
            - all nodes (no filtering at this level - deferred to executor)
            - scores_map: dict mapping node id() to predicate score
            - trace: detailed scoring trace
        """
        if execution_log is None:
            execution_log = []
        
        # Clear caches for fresh scoring
        self._atomic_score_cache.clear()
        self._detailed_score_cache.clear()
        self._node_descriptions.clear()
        
        # Collect all atomic values for logging
        atomic_values = predicate.get_all_atomic_values()
        execution_log.append(
            f"Scoring predicate: {predicate} (atomic conditions: {atomic_values})"
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
        
        # =====================================================================
        # Phase 1: Collect all scoring tasks
        # =====================================================================
        scoring_tasks = self._collect_scoring_tasks(nodes, predicate)
        
        execution_log.append(
            f"  Collected {sum(len(t) for t in scoring_tasks.values())} descriptions "
            f"for {len(scoring_tasks)} unique predicate value(s)"
        )
        
        # =====================================================================
        # Phase 2: Batch score all atomics (one call per predicate value)
        # =====================================================================
        batch_stats = self._batch_score_atomics(scoring_tasks, trace)
        
        execution_log.append(
            f"  Made {batch_stats['total_scorer_calls']} scorer call(s) "
            f"for {batch_stats['total_descriptions_scored']} total descriptions"
        )
        
        # =====================================================================
        # Phase 3: Compute final scores using cached atomics
        # =====================================================================
        scores_map: Dict[int, float] = {}
        
        for idx, node in enumerate(nodes):
            node_name = NodeUtils.get_node_name(node)
            node_trace = {
                "node_idx": idx,
                "node_name": node_name,
                "node_type": node.tag,
                "scoring_steps": []
            }
            
            # Score this node against the compound predicate
            score = self._score_compound_predicate(
                node, predicate, node_trace["scoring_steps"], execution_log
            )
            
            scores_map[id(node)] = score
            node_trace["final_score"] = score
            trace["node_scores"].append(node_trace)
            
            execution_log.append(
                f"  Node {idx} ({node_name}): score = {score:.4f}"
            )
        
        # Sort nodes by score for ranking info
        sorted_nodes = sorted(
            [(idx, scores_map[id(node)], NodeUtils.get_node_name(node)) 
             for idx, node in enumerate(nodes)],
            key=lambda x: x[1],
            reverse=True
        )
        
        trace["ranking"] = [
            {"idx": idx, "score": score, "name": name}
            for idx, score, name in sorted_nodes
        ]
        
        # Return ALL nodes - filtering is deferred to executor
        return nodes, scores_map, trace
    
    # =========================================================================
    # Phase 3: Score Computation (uses cached atomics)
    # =========================================================================
    
    def _score_compound_predicate(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Recursively score a compound predicate against a node.
        
        Uses pre-computed atomic scores from cache.
        
        Args:
            node: The XML element to score
            predicate: The compound predicate AST
            trace_steps: List to append scoring trace steps
            execution_log: Log for human-readable output
            
        Returns:
            Probability score in [0, 1]
        """
        if predicate.operator == "ATOMIC":
            return self._score_atomic(node, predicate.conditions[0], trace_steps)
        
        elif predicate.operator == "OR":
            return self._score_or(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AND":
            return self._score_and(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "EXISTS":
            return self._score_exists(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "ALL":
            return self._score_all(node, predicate, trace_steps, execution_log)
        
        else:
            # Unknown operator - return neutral score
            return 0.5
    
    def _score_atomic(
        self,
        node: ET.Element,
        condition: AtomicCondition,
        trace_steps: List[Dict]
    ) -> float:
        """
        Score a single atomic condition against a node.
        
        Looks up the pre-computed score from cache (populated in Phase 2).
        """
        node_id = id(node)
        cache_key = (node_id, condition.value)
        
        # Get score from cache (should always be present after Phase 2)
        score = self._atomic_score_cache.get(cache_key, 0.5)
        
        # Get individual description scores for trace
        desc_ids = self._node_descriptions.get(node_id, [])
        individual_scores = []
        for desc_id in desc_ids:
            detail_key = (node_id, desc_id, condition.value)
            if detail_key in self._detailed_score_cache:
                individual_scores.append(self._detailed_score_cache[detail_key])
        
        trace_steps.append({
            "type": "atomic",
            "condition": condition.to_dict(),
            "num_descriptions_scored": len(individual_scores),
            "individual_scores": individual_scores,
            "score": score,
            "cached": True  # Always cached after Phase 2
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
        Score OR (disjunction) using Noisy-OR model.
        
        Formula: π(p) = 1 - ∏(1 - π(cj))
        """
        child_scores = []
        child_traces = []
        
        for cond in predicate.conditions:
            child_trace = []
            if isinstance(cond, CompoundPredicate):
                score = self._score_compound_predicate(node, cond, child_trace, execution_log)
            elif isinstance(cond, AtomicCondition):
                atomic_pred = CompoundPredicate(operator="ATOMIC", conditions=[cond])
                score = self._score_compound_predicate(node, atomic_pred, child_trace, execution_log)
            else:
                score = 0.5
            child_scores.append(score)
            child_traces.append(child_trace)
        
        # Noisy-OR: 1 - ∏(1 - π_j)
        product = 1.0
        for s in child_scores:
            product *= (1 - s)
        result = 1 - product
        
        # Clamp result
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "or_composition",
            "operator": "OR",
            "formula": "1 - ∏(1 - π_j)",
            "child_scores": child_scores,
            "product_of_complements": product,
            "result": result,
            "child_traces": child_traces
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
        Score AND (conjunction) using log-odds aggregation.
        
        Formula: π(p) = σ(Σ log(π/(1-π)))
        """
        child_scores = []
        child_traces = []
        
        for cond in predicate.conditions:
            child_trace = []
            if isinstance(cond, CompoundPredicate):
                score = self._score_compound_predicate(node, cond, child_trace, execution_log)
            elif isinstance(cond, AtomicCondition):
                atomic_pred = CompoundPredicate(operator="ATOMIC", conditions=[cond])
                score = self._score_compound_predicate(node, atomic_pred, child_trace, execution_log)
            else:
                score = 0.5
            child_scores.append(score)
            child_traces.append(child_trace)
        
        # Log-odds aggregation: σ(Σ log(π/(1-π)))
        log_odds_sum = 0.0
        individual_log_odds = []
        for s in child_scores:
            s_clamped = max(EPSILON, min(1 - EPSILON, s))
            lo = math.log(s_clamped / (1 - s_clamped))
            log_odds_sum += lo
            individual_log_odds.append(lo)
        
        # Sigmoid
        result = 1 / (1 + math.exp(-log_odds_sum))
        
        # Clamp result
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "and_composition",
            "operator": "AND",
            "formula": "σ(Σ log(π/(1-π)))",
            "child_scores": child_scores,
            "individual_log_odds": individual_log_odds,
            "accumulated_log_odds": log_odds_sum,
            "result": result,
            "child_traces": child_traces
        })
        
        return result
    
    def _score_exists(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score EXISTS (existential quantifier) over children.
        
        Formula: π(p) = 1 - ∏_{u∈ch(v)}(1 - π_u(p))
        
        For leaf nodes (no hierarchical children): scores the node itself directly.
        For container nodes: Noisy-OR over all children.
        """
        if not predicate.child_predicate:
            return 0.5
        
        # Find hierarchical children (not XML sub-elements like name, description)
        children = self._get_hierarchical_children(node, predicate.child_type)
        child_type_desc = predicate.child_type or "*"
        
        if not children:
            # Leaf node - score the node itself using the inner predicate
            inner_trace = []
            result = self._score_compound_predicate(
                node, predicate.child_predicate, inner_trace, execution_log
            )
            
            trace_steps.append({
                "type": "exists_quantifier",
                "operator": "EXISTS",
                "child_type": child_type_desc,
                "num_children": 0,
                "is_leaf_node": True,
                "note": "Leaf node - scoring node itself",
                "inner_predicate_trace": inner_trace,
                "result": result
            })
            return result
        
        # Score each child against the child predicate (uses cached scores)
        child_scores = []
        child_traces = []
        
        for child in children:
            child_trace = []
            score = self._score_compound_predicate(
                child, predicate.child_predicate, child_trace, execution_log
            )
            child_scores.append(score)
            child_traces.append({
                "child_name": NodeUtils.get_node_name(child),
                "child_type": child.tag,
                "score": score,
                "trace": child_trace
            })
        
        # Noisy-OR over children
        product = 1.0
        for s in child_scores:
            product *= (1 - s)
        result = 1 - product
        
        # Clamp result
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "exists_quantifier",
            "operator": "EXISTS",
            "formula": "1 - ∏_{ch}(1 - π_u)",
            "child_type": child_type_desc,
            "num_children": len(children),
            "child_scores": child_scores,
            "product_of_complements": product,
            "result": result,
            "child_details": child_traces
        })
        
        return result
    
    def _score_all(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score ALL (universal quantifier / prevalence) over children.
        
        Formula: π(p) = (α + Σπ_u) / (α + β + n)
        
        For leaf nodes (no hierarchical children): scores the node itself directly.
        For container nodes: Beta-Bernoulli over all children.
        """
        if not predicate.child_predicate:
            return 0.5
        
        # Find hierarchical children (not XML sub-elements like name, description)
        children = self._get_hierarchical_children(node, predicate.child_type)
        child_type_desc = predicate.child_type or "*"
        
        if not children:
            # Leaf node - score the node itself using the inner predicate
            inner_trace = []
            result = self._score_compound_predicate(
                node, predicate.child_predicate, inner_trace, execution_log
            )
            
            trace_steps.append({
                "type": "all_quantifier",
                "operator": "ALL",
                "child_type": child_type_desc,
                "num_children": 0,
                "is_leaf_node": True,
                "note": "Leaf node - scoring node itself",
                "inner_predicate_trace": inner_trace,
                "result": result
            })
            return result
        
        # Score each child against the child predicate (uses cached scores)
        child_scores = []
        child_traces = []
        
        for child in children:
            child_trace = []
            score = self._score_compound_predicate(
                child, predicate.child_predicate, child_trace, execution_log
            )
            child_scores.append(score)
            child_traces.append({
                "child_name": NodeUtils.get_node_name(child),
                "child_type": child.tag,
                "score": score,
                "trace": child_trace
            })
        
        # Beta-Bernoulli posterior mean
        sum_scores = sum(child_scores)
        n = len(children)
        result = (self.BETA_ALPHA + sum_scores) / (self.BETA_ALPHA + self.BETA_BETA + n)
        
        # Clamp result
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "all_quantifier",
            "operator": "ALL",
            "formula": "(α + Σπ_u) / (α + β + n)",
            "child_type": child_type_desc,
            "num_children": n,
            "child_scores": child_scores,
            "sum_child_scores": sum_scores,
            "alpha": self.BETA_ALPHA,
            "beta": self.BETA_BETA,
            "result": result,
            "child_details": child_traces
        })
        
        return result
    
    # =========================================================================
    # Legacy API for backward compatibility
    # =========================================================================
    
    def apply_semantic_predicate_legacy(
        self, 
        nodes: List[ET.Element], 
        predicate: str,
        execution_log: List[str] = None
    ) -> Tuple[List[ET.Element], Dict[int, float], Dict[str, Any]]:
        """
        Legacy API: Apply simple string predicate scoring to nodes.
        
        Converts string predicate to CompoundPredicate and delegates.
        """
        compound = CompoundPredicate(
            operator="ATOMIC",
            conditions=[AtomicCondition(field="description", value=predicate)]
        )
        return self.apply_semantic_predicate(nodes, compound, execution_log)
