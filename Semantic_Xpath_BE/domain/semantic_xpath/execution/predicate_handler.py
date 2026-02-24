"""Predicate scoring for supported semantic operators (field=~value/min/max/avg/1-p)."""

import json
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from .predicate_scorer import PredicateScorer
from domain.semantic_xpath.node_ops import NodeUtils
from domain.semantic_xpath.parsing.predicate_ast import (
    PredicateNode,
    AtomPredicate,
    IdEqPredicate,
    AggPredicate,
    AggExistsPredicate,
    AggPrevPredicate,
    AndPredicate,
    OrPredicate,
    AvgPredicate,
    NotPredicate,
)
from domain.semantic_xpath.parsing.parsing_models import (
    Axis,
    Index,
    NodeTest,
    NodeTestExpr,
    NodeTestLeaf,
    NodeTestAnd,
    NodeTestOr,
)


# Small epsilon to avoid log(0) and division by zero
EPSILON = 1e-9

# Type alias for scoring task: (node_id, desc_id, description_dict)
ScoringTask = Tuple[int, str, Dict[str, Any]]


class PredicateHandler:
    """
    Predicate scorer for supported operators.

    Supported:
    - field =~ "value": local semantic scoring
    - min(...): predicate-level conjunction
    - max(...): predicate-level disjunction
    - avg(...): predicate-level arithmetic mean
    - 1-p: negation via 1 - score
    - agg_min(...), agg_max(...), agg_avg(...): evidence-based aggregation

    Unsupported:
    - Keyword forms AND / OR / NOT
    - agg_exists, agg_prev (legacy)
    """
    
    def __init__(
        self,
        scorer: PredicateScorer,
        top_k: int = 5,
        score_threshold: float = 0.1,
        schema: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the predicate handler.
        
        Args:
            scorer: PredicateScorer implementation (LLM, Entailment, or Cosine)
            top_k: Compatibility config (final top_k is applied by executor).
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
        
        # Track which (node_id, field, value) were resolved via exact match
        self._exact_match_set: set = set()
        
        # Track node descriptions
        self._node_descriptions: Dict[int, List[str]] = {}
    
    def _get_allowed_children(self, node_type: str) -> Optional[List[str]]:
        """Get the allowed child types for a node type from schema.

        Returns None if the node type is not defined in the schema.
        """
        node_config = self._node_configs.get(node_type)
        if node_config is None:
            return None
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

            if allowed_children is None:
                # Unknown node type: allow all direct children
                return list(node)
            if allowed_children:
                return [child for child in node if child.tag in allowed_children]
            # If this is a version node with no declared children, allow all
            node_cfg = self._node_configs.get(node.tag, {})
            if node_cfg.get("type") == "version":
                return list(node)
            # Leaf node or no children defined - return empty
            return []

    def _apply_index_to_nodes(self, nodes: List[ET.Element], index: Optional[Index]) -> List[ET.Element]:
        if not index:
            return nodes
        from domain.semantic_xpath.execution.index_handler import IndexHandler
        return IndexHandler.apply_index(nodes, index)  # type: ignore[arg-type]

    def _evaluate_node_test_expr(
        self,
        node: ET.Element,
        expr: NodeTestExpr,
        axis: Axis,
        execution_log: List[str]
    ) -> List[ET.Element]:
        """
        Evaluate a NodeTestExpr against a node to select evidence nodes.

        Predicates inside node tests are treated as filters using score_threshold.
        """
        if isinstance(expr, NodeTestLeaf):
            return self._evaluate_node_test_leaf(node, expr.test, axis, execution_log)

        if isinstance(expr, NodeTestOr):
            seen = set()
            result: List[ET.Element] = []
            for child in expr.children:
                for n in self._evaluate_node_test_expr(node, child, axis, execution_log):
                    nid = id(n)
                    if nid not in seen:
                        seen.add(nid)
                        result.append(n)
            return result

        if isinstance(expr, NodeTestAnd):
            child_lists = [
                self._evaluate_node_test_expr(node, child, axis, execution_log)
                for child in expr.children
            ]
            if not child_lists:
                return []
            # Intersection by node id, preserve order of first list
            common_ids = {id(n) for n in child_lists[0]}
            for lst in child_lists[1:]:
                common_ids &= {id(n) for n in lst}
            return [n for n in child_lists[0] if id(n) in common_ids]

        return []

    def _evaluate_node_test_leaf(
        self,
        node: ET.Element,
        test: NodeTest,
        axis: Axis,
        execution_log: List[str]
    ) -> List[ET.Element]:
        axis_str = axis.value if axis != Axis.NONE else "child"
        if test.kind == "wildcard":
            candidates = self._get_hierarchical_children(node, child_type=None, axis=axis_str)
        else:
            candidates = self._get_hierarchical_children(node, child_type=test.name, axis=axis_str)

        candidates = self._apply_index_to_nodes(candidates, test.index)

        if test.predicate:
            _, scores_map, _ = self.apply_semantic_predicate(candidates, test.predicate, execution_log)
            threshold = self.score_threshold
            return [n for n in candidates if scores_map.get(id(n), 0.0) >= threshold]
        return candidates
    
    def _get_all_structural_types(self) -> set:
        """Get all node types defined in the schema."""
        return set(self._node_configs.keys())
    
    # =========================================================================
    # Main Entry Point
    # =========================================================================
    
    def apply_semantic_predicate(
        self, 
        nodes: List[ET.Element], 
        predicate: PredicateNode,
        execution_log: List[str] = None
    ) -> Tuple[List[ET.Element], Dict[int, float], Dict[str, Any]]:
        """
        Apply semantic predicate scoring to nodes.
        
        Uses batch optimization for efficient scoring.
        
        Args:
            nodes: List of XML elements to score
            predicate: CompoundPredicate AST
            execution_log: Deprecated and ignored.
            
        Returns:
            - all nodes (no filtering - deferred to executor)
            - scores_map: dict mapping node id() to score
            - trace: detailed scoring trace
        """
        # Clear caches
        self._score_cache.clear()
        self._exact_match_set.clear()
        self._node_descriptions.clear()
        
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
        
        # Phase 2: Batch score all semantics
        batch_stats = self._batch_score_semantics(scoring_tasks, trace)
        
        # Phase 3: Compute final scores using recursive Score(u, ψ)
        scores_map: Dict[int, float] = {}
        
        for idx, node in enumerate(nodes):
            node_name = self._node_utils.get_name(node)
            node_trace = {
                "node_idx": idx,
                "node_id": id(node),
                "node_name": node_name,
                "node_type": node.tag,
                "scoring_steps": []
            }
            
            # Paper: Score(u, ψ) - recursive predicate evaluation
            score = self.score(
                node, predicate, node_trace["scoring_steps"]
            )
            
            scores_map[id(node)] = score
            node_trace["final_score"] = score
            trace["node_scores"].append(node_trace)
            
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
        predicate: PredicateNode
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
        predicate: PredicateNode,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """
        Recursively collect scoring tasks for a node.
        
        Traverses supported predicate structure to find all Atom(u, φ) evaluations.
        """
        if isinstance(predicate, AtomPredicate):
            exact = self._try_exact_match(node, predicate)
            if exact is not None:
                # Exact match resolved — cache score and skip entailment
                self._score_cache[(id(node), predicate.value)] = exact
                self._exact_match_set.add((id(node), predicate.field, predicate.value))
                return
            self._add_node_content_to_tasks(node, predicate.value, tasks)
        
        elif isinstance(predicate, (AndPredicate, OrPredicate, AvgPredicate)):
            for child in predicate.children:
                self._collect_tasks_for_node(node, child, tasks)
        
        elif isinstance(predicate, NotPredicate):
            if predicate.child:
                self._collect_tasks_for_node(node, predicate.child, tasks)
        
        elif isinstance(predicate, AggPredicate):
            if predicate.agg_type in ("min", "max", "avg"):
                evidence_nodes = self._evaluate_node_test_expr(
                    node, predicate.selector.test, predicate.selector.axis, []
                )
                for ev_node in evidence_nodes:
                    self._collect_tasks_for_node(ev_node, predicate.inner, tasks)
            else:
                raise ValueError(
                    "Unsupported predicate in task collection: aggregation is disabled."
                )
        elif isinstance(predicate, (AggExistsPredicate, AggPrevPredicate)):
            raise ValueError(
                "Unsupported predicate in task collection: aggregation is disabled."
            )
    
    def _try_exact_match(
        self,
        node: ET.Element,
        predicate: AtomPredicate,
    ) -> Optional[float]:
        """Check for exact attribute/field match, returning 1.0 or 0.0.

        Returns None if the field doesn't exist on the node (fall through to entailment).
        """
        field = predicate.field
        if not field or field == "content":
            return None  # Generic content match -> use entailment

        # Check XML attribute
        val = node.attrib.get(field)
        if val is None:
            # Check child element text
            child_elem = node.find(field)
            if child_elem is not None and child_elem.text:
                val = child_elem.text.strip()

        if val is None:
            return None  # Field not present -> fall through to entailment

        # Case-insensitive exact match
        if val.strip().lower() == predicate.value.strip().lower():
            return 1.0
        return 0.0

    def _add_node_content_to_tasks(
        self,
        node: ET.Element,
        semantic_value: str,
        tasks: Dict[str, List[ScoringTask]]
    ):
        """Add a node's content to scoring tasks.
        
        For all nodes (internal or leaf), builds content by concatenating
        all schema-defined descriptive fields (not child summaries).
        """
        node_id = id(node)
        
        # Skip if already added
        if any(t[0] == node_id for t in tasks.get(semantic_value, [])):
            return
        
        node_name = self._node_utils.get_name(node)

        # Build content from ALL schema-defined fields for any node type
        node_desc = self._build_node_content(node)
        
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
    
    def _build_node_content(self, node: ET.Element) -> str:
        """
        Build comprehensive content string for any node using schema-defined fields.
        
        Uses the schema's 'fields' list for the node type to include ALL relevant
        fields (name, time_block, description, expected_cost, etc.) in the content
        string. This enables semantic matching that considers temporal and cost context.
        
        Args:
            node: XML element (any structured node)
            
        Returns:
            Content string with all field values, formatted as "field: value" pairs
        """
        node_type = node.tag
        node_config = self._node_configs.get(node_type, {})
        schema_fields = node_config.get("fields", [])

        parts: List[str] = []

        if schema_fields:
            # Use schema-defined fields (child elements or attributes)
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
                elif field_name in node.attrib:
                    # Attribute (e.g. task_id, task_name, version_id, summary in registry)
                    parts.append(f"{field_name}: {node.attrib[field_name]}")
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
            # Elements with direct text (e.g. <Item>text</Item>) - no children, text in node.text
            if not parts and node.text and node.text.strip():
                parts.append(node.text.strip())

        # Always include full textual evidence from the entire node subtree.
        # This avoids schema-field-only blind spots (e.g. Task nodes with only @id field).
        text_pairs: List[str] = []
        for el in node.iter():
            txt = (el.text or "").strip()
            if txt:
                text_pairs.append(f"{el.tag}: {txt}")
        if text_pairs:
            parts.append("all_text: " + " | ".join(text_pairs))

        # Also include the full node payload so scorer always sees complete node context.
        full_node = {
            "type": node.tag,
            "attributes": dict(node.attrib),
            "xml": ET.tostring(node, encoding="unicode"),
        }
        parts.append("full_node: " + json.dumps(full_node, ensure_ascii=False))

        if parts:
            # De-duplicate while preserving order.
            deduped_parts = list(dict.fromkeys(parts))
            return " | ".join(deduped_parts)
        return self._node_utils.get_description(node)
    
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
        predicate: PredicateNode,
        trace_steps: List[Dict],
        execution_log: Optional[List[str]] = None
    ) -> float:
        """
        Recursively score a predicate against a node.
        
        Supported operators:
        - field =~ "value"
        - min(...)
        - max(...)
        - avg(...)
        - 1-p
        """
        if isinstance(predicate, AtomPredicate):
            return self._score_atom(node, predicate, trace_steps)
        if isinstance(predicate, IdEqPredicate):
            return self._score_id_eq(node, predicate, trace_steps)
        if isinstance(predicate, OrPredicate):
            return self._score_or(node, predicate, trace_steps)
        if isinstance(predicate, AndPredicate):
            return self._score_and(node, predicate, trace_steps)
        if isinstance(predicate, AvgPredicate):
            return self._score_avg(node, predicate, trace_steps)
        if isinstance(predicate, NotPredicate):
            return self._score_not(node, predicate, trace_steps)
        if isinstance(predicate, AggPredicate):
            if predicate.agg_type in ("min", "max", "avg"):
                return self._score_evidence_agg(node, predicate, trace_steps)
            raise ValueError(
                "Aggregation predicates are not supported. "
                "Use min/max/avg and 1-p forms."
            )
        if isinstance(predicate, AggExistsPredicate):
            raise ValueError(
                "Aggregation predicates are not supported. "
                "Use min/max/avg and 1-p forms."
            )
        if isinstance(predicate, AggPrevPredicate):
            raise ValueError(
                "Aggregation predicates are not supported. "
                "Use min/max/avg and 1-p forms."
            )
        raise ValueError(f"Unsupported predicate type: {type(predicate).__name__}")
    
    def _score_id_eq(
        self,
        node: ET.Element,
        predicate: IdEqPredicate,
        trace_steps: List[Dict]
    ) -> float:
        """Score @field = \"value\" - exact match on attribute or child element."""
        val = node.attrib.get(predicate.field)
        if val is None:
            child = node.find(predicate.field)
            val = child.text if child is not None and child.text else None
        score = 1.0 if val == predicate.value else 0.0
        trace_steps.append({
            "type": "id_eq",
            "field": predicate.field,
            "value": predicate.value,
            "actual": val,
            "score": score,
        })
        return score

    def _score_atom(
        self,
        node: ET.Element,
        predicate: AtomPredicate,
        trace_steps: List[Dict]
    ) -> float:
        """Score atomic predicate - Atom(u, φ) from attr(u)."""
        node_id = id(node)
        cache_key = (node_id, predicate.value)
        score = self._score_cache.get(cache_key, 0)
        
        # Detect if this was resolved via exact match
        was_exact = (node_id, predicate.field, predicate.value) in self._exact_match_set
        
        trace_steps.append({
            "type": "atom",
            "condition": predicate.to_dict(),
            "score": score,
            "note": "Exact field match" if was_exact else "Atom(u, φ) - entailment",
        })
        
        return score

    def _score_or(
        self,
        node: ET.Element,
        predicate: OrPredicate,
        trace_steps: List[Dict],
    ) -> float:
        """Score disjunction: max{Score(u, ψ_j)}."""
        trace_steps_list = []
        child_scores = []

        for child in predicate.children:
            inner_trace: List[Dict] = []
            s = self.score(node, child, inner_trace)
            child_scores.append(s)
            trace_steps_list.append(inner_trace)

        result = max(child_scores) if child_scores else 0
        result = max(EPSILON, min(1 - EPSILON, result))

        trace_steps.append({
            "type": "or",
            "operator": "max",
            "formula": "max{Score(u, ψ_j)}",
            "child_scores": child_scores,
            "inner_traces": trace_steps_list,
            "result": result
        })

        return result
    
    def _score_and(
        self,
        node: ET.Element,
        predicate: AndPredicate,
        trace_steps: List[Dict],
    ) -> float:
        """Score conjunction: min{Score(u, ψ_j)}"""
        trace_steps_list = []
        child_scores = []
        
        for child in predicate.children:
            inner_trace: List[Dict] = []
            s = self.score(node, child, inner_trace)
            child_scores.append(s)
            trace_steps_list.append(inner_trace)
        
        result = min(child_scores) if child_scores else 0
        result = max(EPSILON, min(1 - EPSILON, result))
        
        trace_steps.append({
            "type": "and",
            "operator": "min",
            "formula": "min{Score(u, ψ_j)}",
            "child_scores": child_scores,
            "inner_traces": trace_steps_list,
            "result": result
        })
        
        return result

    def _score_avg(
        self,
        node: ET.Element,
        predicate: AvgPredicate,
        trace_steps: List[Dict],
    ) -> float:
        """Score average: mean{Score(u, ψ_j)}."""
        trace_steps_list = []
        child_scores = []

        for child in predicate.children:
            inner_trace: List[Dict] = []
            s = self.score(node, child, inner_trace)
            child_scores.append(s)
            trace_steps_list.append(inner_trace)

        result = (sum(child_scores) / len(child_scores)) if child_scores else 0
        result = max(EPSILON, min(1 - EPSILON, result))

        trace_steps.append({
            "type": "avg",
            "operator": "avg",
            "formula": "mean{Score(u, ψ_j)}",
            "child_scores": child_scores,
            "inner_traces": trace_steps_list,
            "result": result
        })

        return result
    
    def _score_not(
        self,
        node: ET.Element,
        predicate: NotPredicate,
        trace_steps: List[Dict],
    ) -> float:
        """Score negation: 1 - Score(u, ψ)"""
        inner_trace: List[Dict] = []
        inner_score = self.score(node, predicate.child, inner_trace) if predicate.child else 0
        
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

    def _score_evidence_agg(
        self,
        node: ET.Element,
        predicate: "AggPredicate",
        trace_steps: List[Dict],
    ) -> float:
        """
        Score evidence-based aggregation: agg_min/agg_max/agg_avg over evidence nodes.
        Navigates evidence nodes via selector, scores each with inner predicate, then aggregates.
        """
        evidence_nodes = self._evaluate_node_test_expr(
            node, predicate.selector.test, predicate.selector.axis, []
        )
        if not evidence_nodes:
            trace_steps.append({
                "type": "evidence_agg",
                "agg_type": predicate.agg_type,
                "selector": str(predicate.selector),
                "evidence_count": 0,
                "result": 0.0,
            })
            return 0.0

        inner_traces: List[Dict] = []
        scores: List[float] = []
        for ev_node in evidence_nodes:
            inner_trace: List[Dict] = []
            s = self.score(ev_node, predicate.inner, inner_trace)
            scores.append(s)
            inner_traces.append(inner_trace)

        if predicate.agg_type == "min":
            result = min(scores)
        elif predicate.agg_type == "max":
            result = max(scores)
        else:
            result = sum(scores) / len(scores)
        result = max(EPSILON, min(1 - EPSILON, result))

        trace_steps.append({
            "type": "evidence_agg",
            "agg_type": predicate.agg_type,
            "selector": str(predicate.selector),
            "evidence_count": len(evidence_nodes),
            "scores": scores,
            "inner_traces": inner_traces,
            "result": result,
        })

        return result
