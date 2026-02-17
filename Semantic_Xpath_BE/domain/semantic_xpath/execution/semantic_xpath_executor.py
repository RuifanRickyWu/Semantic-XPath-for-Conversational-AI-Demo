"""
Semantic XPath Executor - Main executor class that orchestrates query execution.

Current behavior:
- Parses semantic XPath path steps and executes structural matching.
- Supports semantic predicates in min/max/avg/1-p forms via predicate scorer.
- Produces `retrieved_nodes` and `step_scoring_trace`.
- Applies threshold + top_k only when the query includes semantic predicates.
- For structural-only queries, returns all matched nodes.
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict, Any, Union
from .predicate_scorer import PredicateScorer

from domain.semantic_xpath.parsing import QueryParser
from domain.semantic_xpath.parsing.parsing_models import (
    Axis,
    Index,
    NodeTestExpr,
    NodeTestAnd,
    NodeTestLeaf,
    NodeTestOr,
    Step,
)
from .execution_models import (
    TraversalStep,
    ExecutionResult,
    NodeItem,
    ParsedQueryAST,
    RetrievalDetail,
)
from domain.semantic_xpath.node_ops import NodeUtils
from .index_handler import IndexHandler
from .predicate_handler import PredicateHandler


# Small epsilon to avoid log(0)
EPSILON = 1e-9


class SemanticXPathExecutor:
    """
    Executes XPath-like queries against an XML tree with semantic matching.
    
    Supports:
    - Type matching: /Itinerary/Day/POI (κ - node type)
    - Positional indexing: Day[1], POI[2], POI[-1], POI[1:3] (ι - positional constraint)
    - Semantic predicates: field=~value, min(...), max(...), avg(...), 1-p
    - Global indexing: (/Itinerary/Day/POI)[5]
    - Injected XML and schema runtime inputs
    """
    
    def __init__(
        self,
        scorer: PredicateScorer,
        top_k: int = 5,
        score_threshold: float = 0.5,
    ):
        """
        Initialize the executor.
        
        Args:
            scorer: Ready semantic predicate scorer implementation.
            top_k: Number of top-scoring nodes to return.
            score_threshold: Minimum score threshold.
        """
        if scorer is None:
            raise ValueError("scorer is required for SemanticXPathExecutor.")

        self.top_k = top_k
        self.score_threshold = score_threshold

        self.scorer = scorer
        
        # Initialize components
        self.parser = QueryParser()
        self._schema: Dict[str, Any] = {}
        self._node_utils: Optional[NodeUtils] = None
        self.predicate_handler: Optional[PredicateHandler] = None
        self._root: Optional[ET.Element] = None

    @property
    def root(self) -> ET.Element:
        """Get the root element."""
        if self._root is None:
            raise ValueError("XML root is not loaded. Call execute(...) with xml_input first.")
        return self._root

    def _load_xml_root(self, xml_input: Union[str, ET.Element, ET.ElementTree]) -> ET.Element:
        if isinstance(xml_input, ET.Element):
            return xml_input
        if isinstance(xml_input, ET.ElementTree):
            return xml_input.getroot()
        if isinstance(xml_input, str):
            return ET.fromstring(xml_input)
        raise TypeError(
            "xml_input must be XML string, xml.etree.ElementTree.Element, "
            "or xml.etree.ElementTree.ElementTree."
        )

    def _prepare_runtime(
        self,
        xml_input: Union[str, ET.Element, ET.ElementTree],
        schema: Dict[str, Any],
    ) -> None:
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dict.")
        self._root = self._load_xml_root(xml_input)
        self._schema = schema
        self._node_utils = NodeUtils(self._schema)
        self.predicate_handler = PredicateHandler(
            scorer=self.scorer,
            top_k=self.top_k,
            score_threshold=self.score_threshold,
            schema=self._schema,
        )

    @property
    def _node_utils_ready(self) -> NodeUtils:
        if self._node_utils is None:
            raise ValueError("Executor runtime is not prepared. Call execute(...) first.")
        return self._node_utils

    @property
    def _predicate_handler_ready(self) -> PredicateHandler:
        if self.predicate_handler is None:
            raise ValueError("Executor runtime is not prepared. Call execute(...) first.")
        return self.predicate_handler

    @property
    def _root_ready(self) -> ET.Element:
        if self._root is None:
            raise ValueError("Executor runtime is not prepared. Call execute(...) first.")
        return self._root
    
    @property
    def root_type(self) -> str:
        """Get the root element's tag name."""
        return self._root_ready.tag
    
    def execute(
        self,
        query: str,
        xml_input: Union[str, ET.Element, ET.ElementTree],
        schema: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Execute an XPath-like query against the tree.
        
        Execution flow:
        1. Parse query into steps.
        2. Traverse and score each step.
        3. Accumulate scores multiplicatively across steps.
        4. Apply threshold + top_k only for semantic-predicate queries.
        5. Return final retrieved nodes and step-scoring traces.
        
        Args:
            query: XPath-like query string
            xml_input: Loaded XML content (XML string, Element, or ElementTree)
            schema: Loaded schema dictionary
            
        Returns:
            ExecutionResult with retrieved nodes and step-level scoring traces.
        """
        self._prepare_runtime(xml_input=xml_input, schema=schema)
        parsed_query = self.parser.parse(query)
        steps = parsed_query.path.steps
        global_index = parsed_query.global_index

        root_type = self.root_type
        current_items: List[NodeItem] = [NodeItem(self._root_ready, root_type, 1.0, 0)]

        # Runtime score progression:
        # final_step_score = previous_score * step_score
        accumulated_by_node_id: Dict[int, float] = {id(self._root_ready): 1.0}

        # Per-step trace records, filtered to final-result lineage at the end.
        step_records: List[Dict[str, Any]] = []
        has_semantic_predicate_query = any(
            self._step_has_predicates(step) for step in steps
        )
        parent_map = self._node_utils_ready.build_parent_map(self._root_ready)

        for step_idx, step in enumerate(steps):
            if self._is_root_step(step, root_type):
                current_items, _ = self._handle_root_step_new(current_items, step, step_idx)
                root_entries: List[Dict[str, Any]] = []
                for item in current_items:
                    node_id = id(item.node)
                    previous_score = accumulated_by_node_id.get(node_id, 1.0)
                    final_step_score = previous_score * 1.0
                    accumulated_by_node_id[node_id] = final_step_score
                    root_entries.append(
                        {
                            "node": item.node,
                            "node_id": node_id,
                            "tree_path": item.path,
                            "previous_score": previous_score,
                            "step_score": 1.0,
                            "final_step_score": final_step_score,
                            "accumulated_score": final_step_score,
                            "predicate_results": [],
                        }
                    )

                step_records.append(
                    {
                        "step_index": step_idx,
                        "step_query": str(step),
                        "axis": step.axis.value,
                        "node_test_expr": step.test.to_dict(),
                        "has_predicate": False,
                        "entries": root_entries,
                    }
                )
                continue

            next_items, step_scores, step_trace = self._apply_step_expr(
                current_items, step, step_idx
            )

            if not next_items:
                current_items = []
                break

            # Per-step result
            def _node_sum(n: ET.Element) -> str:
                tag = n.tag
                a = n.attrib
                if tag == "Task":
                    return f"Task[{a.get('task_id', '?')}]"
                if tag == "Version":
                    return f"Version[{a.get('version_id', '?')}]"
                if tag == "Day":
                    return f"Day[{a.get('number', a.get('index', '?'))}]"
                if a:
                    return f"{tag}{dict(a)}"
                txt = (n.text or "").strip()[:40]
                return f"{tag}: {txt!r}" if txt else tag
            step_summaries = [_node_sum(item.node) for item in next_items[:5]]
            if len(next_items) > 5:
                step_summaries.append(f"...+{len(next_items) - 5} more")

            has_predicates = self._step_has_predicates(step)

            scoring_traces = step_trace.details.get("scoring_trace", [])
            predicate_results_by_node = self._extract_predicate_results(scoring_traces)
            relative_index_by_node = self._extract_relative_index_info(scoring_traces)
            step_entries: List[Dict[str, Any]] = []

            for item in next_items:
                node_id = id(item.node)
                step_score = step_scores.get(node_id, 1.0)
                step_score = max(EPSILON, min(1 - EPSILON, step_score))

                previous_score = accumulated_by_node_id.get(node_id)
                if previous_score is None:
                    previous_score = self._get_ancestor_accumulated_score(
                        item.node, parent_map, accumulated_by_node_id
                    )
                final_step_score = previous_score * step_score
                accumulated_by_node_id[node_id] = final_step_score

                rel_info = relative_index_by_node.get(node_id)
                pred_results = predicate_results_by_node.get(node_id, [])
                if rel_info:
                    pred_results = rel_info.get("anchor_predicate_results", [])

                entry: Dict[str, Any] = {
                    "node": item.node,
                    "node_id": node_id,
                    "tree_path": item.path,
                    "previous_score": previous_score,
                    "step_score": step_score,
                    "final_step_score": final_step_score,
                    "accumulated_score": final_step_score,
                    "predicate_results": pred_results,
                }
                if rel_info:
                    entry["relative_index"] = {
                        "offset": rel_info.get("offset"),
                        "anchor_path": rel_info.get("anchor_path"),
                        "anchor_node": rel_info.get("anchor_node"),
                        "anchor_predicate_results": rel_info.get("anchor_predicate_results"),
                    }
                step_entries.append(entry)

            step_records.append(
                {
                    "step_index": step_idx,
                    "step_query": str(step),
                    "axis": step.axis.value,
                    "node_test_expr": step.test.to_dict(),
                    "has_predicate": has_predicates,
                    "entries": step_entries,
                }
            )

            current_items = next_items

        if not current_items:
            empty_result = ExecutionResult(
                query=query,
                retrieved_nodes=[],
                retrieval_detail=RetrievalDetail(per_node=[], step_scoring_trace=[]),
            )
            return empty_result

        # Use accumulated score as final score before filtering.
        for item in current_items:
            node_id = id(item.node)
            item.score = accumulated_by_node_id.get(node_id)
            if item.score is None:
                item.score = self._get_ancestor_accumulated_score(
                    item.node, parent_map, accumulated_by_node_id
                )

        if has_semantic_predicate_query:
            current_items = [item for item in current_items if item.score >= self.score_threshold]
            current_items.sort(key=lambda item: item.score, reverse=True)

        if global_index is not None and current_items:
            current_items, _ = self._apply_global_index(
                current_items, global_index, len(steps)
            )

        if has_semantic_predicate_query:
            current_items = current_items[:self.top_k]

        final_items = current_items
        final_nodes = [item.node for item in final_items]
        parent_map = self._node_utils_ready.build_parent_map(self._root_ready)

        def _is_relevant_entry(entry: Dict[str, Any]) -> bool:
            return any(
                self._is_ancestor_or_self(entry["node"], target, parent_map)
                for target in final_nodes
            )

        # Step-level trace, excluding nodes dropped from final lineage.
        step_scoring_trace: List[Dict[str, Any]] = []
        for record in step_records:
            relevant_entries = [entry for entry in record["entries"] if _is_relevant_entry(entry)]
            if not relevant_entries:
                continue
            nodes_list = []
            for entry in relevant_entries:
                node_dict: Dict[str, Any] = {
                    "tree_path": entry["tree_path"],
                    "previous_score": entry["previous_score"],
                    "step_score": entry["step_score"],
                    "final_step_score": entry["final_step_score"],
                    "accumulated_score": entry["accumulated_score"],
                    "predicate_results": entry["predicate_results"],
                    "node": self._node_utils_ready.node_to_dict_schema_aware(entry["node"]),
                    "children": self._node_utils_ready.get_full_subtree(entry["node"]),
                }
                if "relative_index" in entry:
                    ri = entry["relative_index"]
                    node_dict["relative_index"] = {
                        "offset": ri.get("offset"),
                        "anchor_path": ri.get("anchor_path"),
                        "anchor_node": self._node_utils_ready.node_to_dict_schema_aware(ri["anchor_node"])
                        if ri.get("anchor_node") is not None
                        else None,
                        "anchor_predicate_results": ri.get("anchor_predicate_results"),
                    }
                nodes_list.append(node_dict)
            step_scoring_trace.append(
                {
                    "step_index": record["step_index"],
                    "step_query": record["step_query"],
                    "axis": record["axis"],
                    "node_test_expr": record["node_test_expr"],
                    "nodes": nodes_list,
                }
            )

        # Build enriched path (root → node) with type + full attributes per segment (for LLM/display).
        def path_from_root_to_node(node: ET.Element, pm: Dict[ET.Element, ET.Element]) -> List[Dict[str, Any]]:
            segments: List[Dict[str, Any]] = []
            current: Optional[ET.Element] = node
            while current is not None:
                d = self._node_utils_ready.node_to_dict_schema_aware(current)
                segments.append({"type": d.get("type", current.tag), "attributes": d.get("attributes") or {}})
                current = pm.get(current)
            segments.reverse()
            return segments

        # Final result: retrieved_nodes (node-only) + retrieval_detail (per_node + step_scoring_trace).
        retrieved_nodes: List[Dict[str, Any]] = []
        per_node: List[Dict[str, Any]] = []
        for final_item in final_items:
            evidence: List[Dict[str, Any]] = []
            for record in step_records:
                if not record["has_predicate"]:
                    continue
                candidates = [
                    entry
                    for entry in record["entries"]
                    if self._is_ancestor_or_self(entry["node"], final_item.node, parent_map)
                ]
                if not candidates:
                    continue
                evidence_entry = max(candidates, key=lambda entry: entry["tree_path"].count(" > "))
                ev_dict: Dict[str, Any] = {
                    "step_index": record["step_index"],
                    "step_query": record["step_query"],
                    "tree_path": evidence_entry["tree_path"],
                    "previous_score": evidence_entry["previous_score"],
                    "step_score": evidence_entry["step_score"],
                    "final_step_score": evidence_entry["final_step_score"],
                    "accumulated_score": evidence_entry["accumulated_score"],
                    "predicate_results": evidence_entry["predicate_results"],
                    "node": self._node_utils_ready.node_to_dict_schema_aware(evidence_entry["node"]),
                    "children": self._node_utils_ready.get_full_subtree(evidence_entry["node"]),
                }
                if "relative_index" in evidence_entry:
                    ri = evidence_entry["relative_index"]
                    ev_dict["relative_index"] = {
                        "offset": ri.get("offset"),
                        "anchor_path": ri.get("anchor_path"),
                        "anchor_node": self._node_utils_ready.node_to_dict_schema_aware(ri["anchor_node"])
                        if ri.get("anchor_node") is not None
                        else None,
                        "anchor_predicate_results": ri.get("anchor_predicate_results"),
                    }
                evidence.append(ev_dict)

            node_dict = self._node_utils_ready.node_to_dict_schema_aware(final_item.node)
            children = self._node_utils_ready.get_full_subtree(final_item.node)
            path_segments = NodeUtils.node_to_path_segments(
                final_item.node, self._root_ready, parent_map
            )
            tree_path_display = path_from_root_to_node(final_item.node, parent_map)
            # Add display path to evidence for LLM context
            evidence_with_path = list(evidence)
            evidence_with_path.append({"type": "path_display", "segments": tree_path_display})

            retrieved_nodes.append(node_dict)
            per_node.append(
                {
                    "tree_path": path_segments,
                    "tree_path_display": tree_path_display,
                    "score": final_item.score,
                    "node": node_dict,
                    "children": children,
                    "evidence": evidence_with_path,
                }
            )

        result = ExecutionResult(
            query=query,
            retrieved_nodes=retrieved_nodes,
            retrieval_detail=RetrievalDetail(per_node=per_node, step_scoring_trace=step_scoring_trace),
        )
        return result

    def _extract_predicate_results(
        self,
        scoring_traces: List[Dict[str, Any]],
    ) -> Dict[int, List[Dict[str, Any]]]:
        by_node: Dict[int, List[Dict[str, Any]]] = {}
        for trace in scoring_traces:
            predicate = trace.get("predicate")
            predicate_ast = trace.get("predicate_ast")
            for node_trace in trace.get("node_scores", []):
                node_id = node_trace.get("node_id")
                if node_id is None:
                    continue
                by_node.setdefault(node_id, []).append(
                    {
                        "predicate": predicate,
                        "predicate_ast": predicate_ast,
                        "predicate_score": node_trace.get("final_score"),
                        "scoring_steps": node_trace.get("scoring_steps", []),
                    }
                )
        return by_node

    def _extract_relative_index_info(
        self, scoring_traces: List[Dict[str, Any]]
    ) -> Dict[int, Dict[str, Any]]:
        """Extract relative_index by_node from traces with type 'relative_index'."""
        for trace in scoring_traces:
            if trace.get("type") == "relative_index":
                return trace.get("by_node", {})
        return {}

    def _is_ancestor_or_self(
        self,
        ancestor: ET.Element,
        target: ET.Element,
        parent_map: Dict[ET.Element, ET.Element],
    ) -> bool:
        current = target
        while current is not None:
            if current is ancestor:
                return True
            current = parent_map.get(current)
        return False
    
    def _items_to_info(
        self, 
        items: List[NodeItem]
    ) -> List[dict]:
        """Convert items to info dictionaries for result trace assembly."""
        return [
            self._node_utils_ready.to_info_dict(item.node, item.path, item.score)
            for item in items
        ]
    
    def _is_root_step(self, step: Step, root_type: str) -> bool:
        if not isinstance(step.test, NodeTestLeaf):
            return False
        test = step.test.test
        if test.kind != "type" or test.name != root_type:
            return False
        if test.predicate or test.index or test.relative_index:
            return False
        return True

    def _handle_root_step_new(
        self,
        current_items: List[NodeItem],
        step: Step,
        step_idx: int,
    ) -> Tuple[List[NodeItem], Optional[TraversalStep]]:
        root_type = self.root_type
        if current_items and current_items[0].node.tag == root_type:
            traversal_step = TraversalStep(
                step_index=step_idx,
                step_query=str(step),
                nodes_before=[{"type": "root"}],
                nodes_after=[{"type": root_type, "path": root_type}],
                action="root_match",
                details={"matched": True}
            )
            return current_items, traversal_step
        return [], None

    def _step_has_predicates(self, step: Step) -> bool:
        return any(step.test.get_all_predicates())

    def _get_ancestor_accumulated_score(
        self,
        node: ET.Element,
        parent_map: Dict[ET.Element, ET.Element],
        accumulated_by_node_id: Dict[int, float],
    ) -> float:
        """
        Walk up the parent chain until finding an ancestor in accumulated_by_node_id.
        Works for child-axis and descendant-axis; root is always in the map.
        Returns 1.0 if no ancestor found (should not happen with a valid tree).
        """
        current: Optional[ET.Element] = node
        while current is not None:
            score = accumulated_by_node_id.get(id(current))
            if score is not None:
                return score
            current = parent_map.get(current)
        return 1.0

    def _apply_step_expr(
        self,
        current_items: List[NodeItem],
        step: Step,
        step_idx: int,
    ) -> Tuple[List[NodeItem], Dict[int, float], TraversalStep]:
        """
        Apply a full step: axis expansion + node test expression evaluation.
        """
        nodes_before = self._items_to_info(current_items)
        axis = step.axis
        parent_map = None
        if axis == Axis.DESC:
            parent_map = self._node_utils_ready.build_parent_map(self._root_ready)

        next_items: List[NodeItem] = []
        scores_map: Dict[int, float] = {}
        scoring_traces: List[Dict[str, Any]] = []

        for group_id, item in enumerate(current_items):
            items, local_scores, local_traces = self._eval_node_test_expr_context(
                item, group_id, axis, step.test, parent_map
            )
            next_items.extend(items)
            for node_id, score in local_scores.items():
                scores_map[node_id] = max(scores_map.get(node_id, 0.0), score)
            scoring_traces.extend(local_traces)

        nodes_after = self._items_to_info(next_items)

        traversal_step = TraversalStep(
            step_index=step_idx,
            step_query=str(step),
            nodes_before=nodes_before,
            nodes_after=nodes_after,
            action="node_test_expr",
            details={
                "axis": axis.value,
                "node_test_expr": step.test.to_dict(),
                "found_count": len(next_items),
                "scoring_trace": scoring_traces,
            }
        )
        return next_items, scores_map, traversal_step

    def _eval_node_test_expr_context(
        self,
        context_item: NodeItem,
        group_id: int,
        axis: Axis,
        expr: NodeTestExpr,
        parent_map: Optional[Dict] = None
    ) -> Tuple[List[NodeItem], Dict[int, float], List[Dict[str, Any]]]:
        if isinstance(expr, NodeTestLeaf):
            return self._eval_node_test_leaf_context(
                context_item, group_id, axis, expr, parent_map
            )

        if isinstance(expr, NodeTestOr):
            combined: Dict[Tuple[int, int], NodeItem] = {}
            traces: List[Dict[str, Any]] = []
            for child in expr.children:
                items, _, child_traces = self._eval_node_test_expr_context(
                    context_item, group_id, axis, child, parent_map
                )
                traces.extend(child_traces)
                for item in items:
                    key = (id(item.node), item.parent_group_id)
                    if key not in combined or item.score > combined[key].score:
                        combined[key] = item
            items_list = list(combined.values())
            scores_map = _items_score_map(items_list)
            return items_list, scores_map, traces

        if isinstance(expr, NodeTestAnd):
            traces: List[Dict[str, Any]] = []
            child_results = []
            for child in expr.children:
                items, _, child_traces = self._eval_node_test_expr_context(
                    context_item, group_id, axis, child, parent_map
                )
                traces.extend(child_traces)
                child_results.append({(id(item.node), item.parent_group_id): item for item in items})

            if not child_results:
                return [], {}, traces

            common_keys = set(child_results[0].keys())
            for mapping in child_results[1:]:
                common_keys &= set(mapping.keys())

            combined: Dict[Tuple[int, int], NodeItem] = {}
            for key in common_keys:
                first_item = child_results[0][key]
                min_score = min(mapping[key].score for mapping in child_results)
                combined[key] = NodeItem(
                    first_item.node,
                    first_item.path,
                    min_score,
                    first_item.parent_group_id
                )
            items_list = list(combined.values())
            scores_map = _items_score_map(items_list)
            return items_list, scores_map, traces

        return [], {}, []

    def _eval_node_test_leaf_context(
        self,
        context_item: NodeItem,
        group_id: int,
        axis: Axis,
        expr: NodeTestLeaf,
        parent_map: Optional[Dict] = None
    ) -> Tuple[List[NodeItem], Dict[int, float], List[Dict[str, Any]]]:
        test = expr.test
        axis_val = axis.value if axis != Axis.NONE else "child"
        matches: List[ET.Element] = []
        next_items: List[NodeItem] = []

        if test.kind == "wildcard":
            if axis_val == "desc":
                matches = [
                    n for n in context_item.node.iter()
                    if n is not context_item.node and NodeUtils._is_structured_node(n)
                ]
            else:
                matches = [
                    child for child in context_item.node
                    if NodeUtils._is_structured_node(child)
                ]
        else:
            if axis_val == "desc":
                matches = [
                    n for n in context_item.node.iter(test.name)
                    if n is not context_item.node
                ]
            else:
                matches = list(context_item.node.findall(test.name))

        # Build NodeItems with path tracking
        if axis_val == "desc":
            if parent_map is None:
                parent_map = self._node_utils_ready.build_parent_map(self._root_ready)
            for child in matches:
                child_path = self._node_utils_ready.get_path_from_ancestor_to_descendant(
                    context_item.node, child, context_item.path, parent_map
                )
                next_items.append(NodeItem(child, child_path, 1.0, group_id))
        else:
            for child in matches:
                child_name = self._node_utils_ready.get_name(child)
                child_path = f"{context_item.path} > {child_name}"
                next_items.append(NodeItem(child, child_path, 1.0, group_id))

        # Apply index within this context
        if test.index is not None:
            nodes_only = [item.node for item in next_items]
            indexed_nodes = IndexHandler.apply_index(nodes_only, test.index)
            indexed_ids = {id(n) for n in indexed_nodes}
            next_items = [item for item in next_items if id(item.node) in indexed_ids]

        scores_map: Dict[int, float] = _items_score_map(next_items)
        traces: List[Dict[str, Any]] = []

        if test.predicate and next_items:
            nodes_only = [item.node for item in next_items]
            _, pred_scores, trace = self._predicate_handler_ready.apply_semantic_predicate(
                nodes_only, test.predicate
            )
            traces.append(trace)
            for item in next_items:
                score = pred_scores.get(id(item.node), item.score)
                item.score = score
            scores_map = pred_scores

        # Apply relative index [@+k] / [@-k]: replace anchors with siblings
        if test.relative_index is not None and next_items:
            if parent_map is None:
                parent_map = self._node_utils_ready.build_parent_map(self._root_ready)
            anchor_items = next_items
            anchor_nodes = [item.node for item in anchor_items]
            anchor_by_id = {id(n): item for item in anchor_items for n in [item.node]}
            pairs = IndexHandler.apply_relative_index(
                anchor_nodes, test.relative_index.offset, parent_map
            )
            sibling_items: List[NodeItem] = []
            relative_index_by_node: Dict[int, Dict[str, Any]] = {}
            pred_results_by_anchor = self._extract_predicate_results(traces)
            for sibling_node, anchor_node in pairs:
                anchor_item = anchor_by_id.get(id(anchor_node))
                if anchor_item is None:
                    continue
                parent_path = (
                    anchor_item.path.rsplit(" > ", 1)[0]
                    if " > " in anchor_item.path
                    else ""
                )
                sibling_name = self._node_utils_ready.get_name(sibling_node)
                sibling_path = (
                    f"{parent_path} > {sibling_name}" if parent_path else sibling_name
                )
                sibling_item = NodeItem(
                    sibling_node,
                    sibling_path,
                    anchor_item.score,
                    anchor_item.parent_group_id,
                )
                sibling_items.append(sibling_item)
                anchor_pred_results = pred_results_by_anchor.get(id(anchor_node), [])
                relative_index_by_node[id(sibling_node)] = {
                    "offset": test.relative_index.offset,
                    "anchor_path": anchor_item.path,
                    "anchor_node": anchor_node,
                    "anchor_predicate_results": anchor_pred_results,
                    "anchor_score": anchor_item.score,
                }
            next_items = sibling_items
            scores_map = _items_score_map(next_items)
            traces.append({
                "type": "relative_index",
                "offset": test.relative_index.offset,
                "by_node": relative_index_by_node,
            })

        return next_items, scores_map, traces
    
    def _apply_global_index(
        self,
        items: List[NodeItem],
        global_index: Index,
        total_steps: int,
    ) -> Tuple[List[NodeItem], TraversalStep]:
        """
        Apply global index to final result set.
        
        Unlike local indexing, global indexing treats ALL nodes as a single
        flat list, regardless of parent_group_id.
        """
        nodes_before_global = self._items_to_info(items)
        nodes_only = [item.node for item in items]
        
        indexed_nodes = IndexHandler.apply_index(nodes_only, global_index)
        
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
    
    def _build_parsed_ast(
        self,
        steps: List[Step],
        global_index: Optional[Index]
    ) -> ParsedQueryAST:
        """
        Build a ParsedQueryAST object from parsed query steps.
        
        Converts Step objects and their node-test/predicate AST nodes into
        serializable dictionaries for debug/inspection.
        """
        ast_steps = []
        for step in steps:
            step_dict = {
                "axis": step.axis.value,
                "node_test_expr": step.test.to_dict(),
            }
            ast_steps.append(step_dict)

        global_idx_dict = global_index.to_dict() if global_index else None

        return ParsedQueryAST(steps=ast_steps, global_index=global_idx_dict)


def _items_score_map(items: List[NodeItem]) -> Dict[int, float]:
    scores: Dict[int, float] = {}
    for item in items:
        node_id = id(item.node)
        scores[node_id] = max(scores.get(node_id, 0.0), item.score)
    return scores
