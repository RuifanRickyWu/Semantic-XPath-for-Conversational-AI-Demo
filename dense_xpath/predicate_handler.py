"""
Predicate Handler - Applies semantic predicate scoring to nodes.

Paper Formalization - Score(u, ψ):
The Score function is defined recursively over predicate structure:

  Score(u, ψ) = {
    Atom(u, φ)                           if ψ = φ (atomic predicate)
    Score(u, ψ₁) · Score(u, ψ₂)          if ψ = ψ₁ ∧ ψ₂ (conjunction)
    max{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∨ ψ₂ (disjunction)
  }

Atomic Predicate Evaluation - Atom(u, φ):
- Local: Atom(u, φ) evaluated from attr(u) - the node's own content
- Hierarchical: Atom(u, φ) = Agg({Atom(x, φ) | x ∈ Sφ(u)}) where Sφ(u) ⊆ Desc(u)

Aggregation Operators:
- Agg∃(A) = max A              (AGG_EXISTS - existential "at least one")
- Aggprev(A) = (1/|A|) ∑ A     (AGG_PREV - prevalence "on average")

Operator Mapping:
- ATOM: Local atomic predicate - Atom(u, φ) from attr(u)
- AND: Conjunction ψ₁ ∧ ψ₂ - product of scores
- OR: Disjunction ψ₁ ∨ ψ₂ - max of scores
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
    - AND: Score(u, ψ₁) · Score(u, ψ₂) - conjunction
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
            node_name = NodeUtils.get_node_name(node)
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
        
        elif predicate.operator in ("AGG_EXISTS", "AGG_PREV"):
            # Hierarchical: collect from children of specified type (Sφ(u) ⊆ Desc(u))
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
        """Add a node's content to scoring tasks.
        
        For container nodes (like Day), aggregates full content from all children
        to provide comprehensive information for semantic scoring.
        """
        node_id = id(node)
        
        # Skip if already added
        if any(t[0] == node_id for t in tasks.get(semantic_value, [])):
            return
        
        node_name = NodeUtils.get_node_name(node)
        
        # For container nodes, build comprehensive description from all children
        if NodeUtils._is_container_node(node):
            # Aggregate full content from all structured children
            parts = []
            for child in node:
                if NodeUtils._is_structured_node(child):
                    child_name = NodeUtils._get_field_value(child, NodeUtils.NAME_FIELDS)
                    child_desc = NodeUtils._get_field_value(child, NodeUtils.DESC_FIELDS)
                    if child_name and child_desc:
                        parts.append(f"{child.tag}: {child_name} - {child_desc}")
                    elif child_name:
                        parts.append(f"{child.tag}: {child_name}")
                    elif child_desc:
                        parts.append(f"{child.tag}: {child_desc}")
            
            # Use aggregated description if available, otherwise fallback
            node_desc = "; ".join(parts) if parts else NodeUtils.get_node_description(node)
        else:
            # For leaf nodes, use standard description
            node_desc = NodeUtils.get_node_description(node)
        
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
            Score(u, ψ₁) · Score(u, ψ₂)          if ψ = ψ₁ ∧ ψ₂ (AND)
            max{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∨ ψ₂ (OR)
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
        
        elif predicate.operator == "AGG_EXISTS":
            return self._score_agg_exists(node, predicate, trace_steps, execution_log)
        
        elif predicate.operator == "AGG_PREV":
            return self._score_agg_prev(node, predicate, trace_steps, execution_log)
        
        return 0.5
    
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
            return 0.5
        
        condition = predicate.conditions[0]
        if not isinstance(condition, AtomicPredicate):
            return 0.5
        
        node_id = id(node)
        cache_key = (node_id, condition.value)
        score = self._score_cache.get(cache_key, 0.5)
        
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
        child_scores = []
        
        for cond in predicate.conditions:
            if isinstance(cond, CompoundPredicate):
                s = self.score(node, cond, [], execution_log)
            else:
                s = 0.5
            child_scores.append(s)
        
        result = max(child_scores) if child_scores else 0.5
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "or",
            "formula": "max{Score(u, ψ_j)}",
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
        """
        Score conjunction: ψ₁ ∧ ψ₂
        
        Paper: Score(u, ψ₁ ∧ ψ₂) = Score(u, ψ₁) · Score(u, ψ₂)
        """
        child_scores = []
        
        for cond in predicate.conditions:
            if isinstance(cond, CompoundPredicate):
                s = self.score(node, cond, [], execution_log)
            else:
                s = 0.5
            child_scores.append(s)
        
        result = 1.0
        for s in child_scores:
            result *= s
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "and",
            "formula": "Score(u, ψ₁) · Score(u, ψ₂)",
            "child_scores": child_scores,
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
        Hierarchical predicate with existential aggregation.
        
        Paper Formalization:
        - Atom(u, φ) = Agg∃({Atom(x, φ) | x ∈ Sφ(u)})
        - Agg∃(A) = max A
        - Sφ(u) ⊆ Desc(u) is the set of evidence nodes (children of specified type)
        
        Semantics: "At least one child matches" - returns max score among children.
        """
        if not predicate.child_predicate:
            return 0.5
        
        # Sφ(u) - evidence nodes (children of specified type)
        children = self._get_hierarchical_children(node, predicate.child_type)
        
        if not children:
            # Empty evidence set - return neutral
            trace_steps.append({
                "type": "agg_exists",
                "child_type": predicate.child_type or "*",
                "num_children": 0,
                "note": "Sφ(u) is empty - no children found",
                "result": 0.5
            })
            return 0.5
        
        # Collect Atom(x, φ) for all x ∈ Sφ(u)
        child_scores = []
        for child in children:
            s = self.score(
                child, predicate.child_predicate, [], execution_log
            )
            child_scores.append(s)
        
        # Agg∃(A) = max A
        result = max(child_scores)
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "agg_exists",
            "formula": "Agg∃(A) = max A",
            "child_type": predicate.child_type or "*",
            "num_children": len(children),
            "child_scores": child_scores,
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
        Hierarchical predicate with prevalence aggregation.
        
        Paper Formalization:
        - Atom(u, φ) = Aggprev({Atom(x, φ) | x ∈ Sφ(u)})
        - Aggprev(A) = (1/|A|) ∑ A
        - Sφ(u) ⊆ Desc(u) is the set of evidence nodes (children of specified type)
        
        Semantics: "General prevalence among children" - returns average score.
        """
        if not predicate.child_predicate:
            return 0.5
        
        # Sφ(u) - evidence nodes (children of specified type)
        children = self._get_hierarchical_children(node, predicate.child_type)
        
        if not children:
            # Empty evidence set - return neutral
            trace_steps.append({
                "type": "agg_prev",
                "child_type": predicate.child_type or "*",
                "num_children": 0,
                "note": "Sφ(u) is empty - no children found",
                "result": 0.5
            })
            return 0.5
        
        # Collect Atom(x, φ) for all x ∈ Sφ(u)
        child_scores = []
        for child in children:
            s = self.score(
                child, predicate.child_predicate, [], execution_log
            )
            child_scores.append(s)
        
        # Aggprev(A) = (1/|A|) ∑ A
        sum_scores = sum(child_scores)
        n = len(children)
        result = sum_scores / n
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "agg_prev",
            "formula": "Aggprev(A) = (1/|A|) ∑ A",
            "child_type": predicate.child_type or "*",
            "num_children": n,
            "child_scores": child_scores,
            "sum_scores": sum_scores,
            "result": result
        })
        
        return result
