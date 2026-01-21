"""
Predicate Handler - Applies semantic predicate scoring to nodes.

Implements the Semantic XPath scoring framework:
- SEM: Score the node's OWN content only (no subtree aggregation)
- AND: Conjunction using product of scores
- OR: Disjunction using max of scores
- EXIST: Existential quantifier - max over specified children
- MASS: Prevalence quantifier - average over specified children

Key Semantic Distinction:
- sem() looks at the node's LOCAL content only
- exist()/mass() aggregate scores from CHILDREN of specified type

Batch Optimization:
- Collects all descriptions for the same semantic value across all nodes
- Makes one scorer call per unique semantic value
- Reduces N*M calls to just M calls (where M = unique semantic values)
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
from .models import CompoundPredicate, SemanticCondition


# Small epsilon to avoid log(0) and division by zero
EPSILON = 1e-9

# Type alias for scoring task: (node_id, desc_id, description_dict)
ScoringTask = Tuple[int, str, Dict[str, Any]]


class PredicateHandler:
    """
    Handles semantic predicate scoring with clear local vs subtree semantics.
    
    Scoring methods:
    - SEM: Score node's own content (local only)
    - OR: π(p) = max(π(cj))
    - AND: π(p) = ∏(π(cj))
    - EXIST: max over children of specified type
    - MASS: average over children of specified type
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
        child_type: Optional[str] = None
    ) -> List[ET.Element]:
        """
        Get hierarchical children of a node (filtering out XML sub-elements).
        
        Uses schema's 'children' field to distinguish structural children
        from the node's own fields (like name, description, etc.).
        
        Args:
            node: XML element
            child_type: Optional specific child type to filter for
            
        Returns:
            List of child elements that are recognized as structural children
        """
        if child_type:
            return list(node.findall(child_type))
        
        # Use schema's children definition for this node type
        allowed_children = self._get_allowed_children(node.tag)
        
        if allowed_children:
            return [child for child in node if child.tag in allowed_children]
        else:
            # Leaf node or no children defined - return empty
            return []
    
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
        
        # Collect all semantic values for logging
        semantic_values = predicate.get_all_semantic_values()
        execution_log.append(
            f"Scoring predicate: {predicate} (semantic values: {semantic_values})"
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
        
        # Phase 3: Compute final scores
        scores_map: Dict[int, float] = {}
        
        for idx, node in enumerate(nodes):
            node_name = NodeUtils.get_node_name(node)
            node_trace = {
                "node_idx": idx,
                "node_name": node_name,
                "node_type": node.tag,
                "scoring_steps": []
            }
            
            score = self._score_predicate(
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
            [(idx, scores_map[id(node)], NodeUtils.get_node_name(node)) 
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
        """Recursively collect scoring tasks for a node."""
        if predicate.operator == "SEM":
            # SEM: score node's own content
            if predicate.conditions:
                condition = predicate.conditions[0]
                if isinstance(condition, SemanticCondition):
                    self._add_node_content_to_tasks(node, condition.value, tasks)
        
        elif predicate.operator in ("AND", "OR"):
            for cond in predicate.conditions:
                if isinstance(cond, CompoundPredicate):
                    self._collect_tasks_for_node(node, cond, tasks)
        
        elif predicate.operator in ("EXIST", "MASS"):
            # Collect from children of specified type
            if predicate.child_predicate:
                children = self._get_hierarchical_children(node, predicate.child_type)
                for child in children:
                    self._collect_tasks_for_node(child, predicate.child_predicate, tasks)
    
    def _add_node_content_to_tasks(
        self,
        node: ET.Element,
        semantic_value: str,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """Add a node's content to scoring tasks."""
        node_id = id(node)
        
        # Skip if already added
        if any(t[0] == node_id for t in tasks.get(semantic_value, [])):
            return
        
        # Get node's own content (not subtree)
        node_desc = NodeUtils.get_node_description(node)
        node_name = NodeUtils.get_node_name(node)
        
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
        
        for semantic_value, tasks in scoring_tasks.items():
            if not tasks:
                continue
            
            start_time = time.perf_counter()
            
            desc_dicts = [task[2] for task in tasks]
            batch_result = self.scorer.score_batch(desc_dicts, semantic_value)
            
            call_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Store scores in cache
            for i, task in enumerate(tasks):
                node_id, desc_id, _ = task
                score = batch_result.results[i].score if i < len(batch_result.results) else 0.5
                score = max(EPSILON, min(1 - EPSILON, score))
                self._score_cache[(node_id, semantic_value)] = score
            
            batch_stats["per_value_stats"].append({
                "value": semantic_value,
                "num_descriptions": len(tasks),
                "call_time_ms": round(call_time_ms, 2)
            })
            batch_stats["total_scorer_calls"] += 1
            batch_stats["total_descriptions_scored"] += len(tasks)
        
        trace["batch_scoring"] = batch_stats
        return batch_stats
    
    # =========================================================================
    # Phase 3: Score Computation
    # =========================================================================
    
    def _score_predicate(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """Recursively score a predicate against a node."""
        if predicate.operator == "SEM":
            return self._score_sem(node, predicate, trace_steps)
        
        elif predicate.operator == "OR":
            return self._score_or(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AND":
            return self._score_and(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "EXIST":
            return self._score_exist(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "MASS":
            return self._score_mass(node, predicate, trace_steps, execution_log)
        
        return 0.5
    
    def _score_sem(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict]
    ) -> float:
        """
        Score SEM predicate - node's OWN content only.
        
        This is the key distinction: sem() NEVER looks at children.
        """
        if not predicate.conditions:
            return 0.5
        
        condition = predicate.conditions[0]
        if not isinstance(condition, SemanticCondition):
            return 0.5
        
        node_id = id(node)
        cache_key = (node_id, condition.value)
        score = self._score_cache.get(cache_key, 0.5)
        
        trace_steps.append({
            "type": "sem",
            "condition": condition.to_dict(),
            "score": score,
            "note": "Local node content only (no subtree)"
        })
        
        return score
    
    def _score_or(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """Score OR using max: π(p) = max(π(cj))"""
        child_scores = []
        
        for cond in predicate.conditions:
            if isinstance(cond, CompoundPredicate):
                score = self._score_predicate(node, cond, [], execution_log)
            else:
                score = 0.5
            child_scores.append(score)
        
        result = max(child_scores) if child_scores else 0.5
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "or",
            "formula": "max(π_j)",
            "child_scores": child_scores,
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
        """Score AND using product: π(p) = ∏(π(cj))"""
        child_scores = []
        
        for cond in predicate.conditions:
            if isinstance(cond, CompoundPredicate):
                score = self._score_predicate(node, cond, [], execution_log)
            else:
                score = 0.5
            child_scores.append(score)
        
        result = 1.0
        for s in child_scores:
            result *= s
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "and",
            "formula": "∏(π_j)",
            "child_scores": child_scores,
            "result": result
        })
        
        return result
    
    def _score_exist(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score EXIST using max over children.
        
        exist(ChildType[pred]) = max(π_ch(pred))
        
        "At least one child matches" semantics.
        """
        if not predicate.child_predicate:
            return 0.5
        
        children = self._get_hierarchical_children(node, predicate.child_type)
        
        if not children:
            # No children of specified type - return neutral
            trace_steps.append({
                "type": "exist",
                "child_type": predicate.child_type or "*",
                "num_children": 0,
                "note": "No children found",
                "result": 0.5
            })
            return 0.5
        
        child_scores = []
        for child in children:
            score = self._score_predicate(
                child, predicate.child_predicate, [], execution_log
            )
            child_scores.append(score)
        
        # Max over children
        result = max(child_scores)
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "exist",
            "formula": "max(π_ch)",
            "child_type": predicate.child_type or "*",
            "num_children": len(children),
            "child_scores": child_scores,
            "result": result
        })
        
        return result
    
    def _score_mass(
        self,
        node: ET.Element,
        predicate: CompoundPredicate,
        trace_steps: List[Dict],
        execution_log: List[str]
    ) -> float:
        """
        Score MASS using average over children.
        
        mass(ChildType[pred]) = Σπ_ch / n
        
        "General prevalence among children" semantics.
        """
        if not predicate.child_predicate:
            return 0.5
        
        children = self._get_hierarchical_children(node, predicate.child_type)
        
        if not children:
            # No children - return neutral
            trace_steps.append({
                "type": "mass",
                "child_type": predicate.child_type or "*",
                "num_children": 0,
                "note": "No children found",
                "result": 0.5
            })
            return 0.5
        
        child_scores = []
        for child in children:
            score = self._score_predicate(
                child, predicate.child_predicate, [], execution_log
            )
            child_scores.append(score)
        
        # Average over children
        sum_scores = sum(child_scores)
        n = len(children)
        result = sum_scores / n
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "mass",
            "formula": "Σπ_ch / n",
            "child_type": predicate.child_type or "*",
            "num_children": n,
            "child_scores": child_scores,
            "sum_scores": sum_scores,
            "result": result
        })
        
        return result
