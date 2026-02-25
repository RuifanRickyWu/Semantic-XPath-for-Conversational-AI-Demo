"""
Plan Edit Service - Handles PLAN_ADD, PLAN_UPDATE, PLAN_DELETE intents.

PLAN_DELETE: retrieve nodes -> verify -> delete -> commit
PLAN_UPDATE: retrieve nodes -> verify -> LLM interpret -> ReplaceXmlNode -> commit
PLAN_ADD: retrieve container -> verify -> LLM interpret (add) -> ReplaceXmlNode -> commit
"""

from __future__ import annotations

from collections import Counter
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from common.types import (
    DeleteXmlNode,
    HandlerResult,
    IntentResult,
    ReplaceXmlNode,
    SessionUpdate,
)
from stores.xml_utils import find_by_path_segments
from services.intent_handling.intent_handling_service import IntentContext, BaseIntentHandler
from services.query_generation.models import QueryGenerationRequest, QueryGenerationResult

logger = logging.getLogger(__name__)


def _plan_schema_from_xml(xml_manager: Any, plan_xml: str) -> dict:
    """Build plan schema in nodes format from XML (mirrors registry schema)."""
    raw = xml_manager.sync_schema(plan_xml, "plan")
    nodes: Dict[str, Dict[str, Any]] = {}
    attrs = raw.get("attributes", {})
    children_map = raw.get("children", {})
    for tag in raw.get("node_types", []):
        nodes[tag] = {
            "fields": list(attrs.get(tag, [])),
            "children": list(children_map.get(tag, [])),
        }
    return {"nodes": nodes, "root": raw.get("root", "Plan")}


def _path_to_display_str(path_data: List[Any]) -> str:
    """Convert tree_path_display or path_segments to readable path string."""
    from services.intent_handling.node_format import path_to_display_str
    return path_to_display_str(path_data)


def _format_deleted_summary(per_node: List[Dict[str, Any]]) -> str:
    """Format a short summary of what was deleted (generic, no hardcoded fields)."""
    from services.intent_handling.node_format import extract_node_content, path_to_display_str

    if not per_node:
        return "Nothing was removed."
    node = per_node[0].get("node") or {}
    node_type = node.get("type", "item")
    path_data = per_node[0].get("tree_path_display") or per_node[0].get("tree_path") or []
    context = path_to_display_str(path_data) if path_data else node_type
    text = extract_node_content(node)
    if text:
        snippet = (text[:80] + "…") if len(text) > 80 else text
        return f"Removed from {context}: {snippet}"
    count = len(per_node)
    if count == 1:
        return f"Removed {context}."
    return f"Removed {count} items from {context}."


class PlanEditService(BaseIntentHandler):
    """Handler for PLAN_ADD, PLAN_UPDATE, PLAN_DELETE intents."""

    intent: str = "PLAN_ADD"

    def __init__(
        self,
        state_store: Optional[Any] = None,
        plan_query_service: Optional[Any] = None,
        executor: Optional[Any] = None,
        result_verifier: Optional[Any] = None,
        plan_update_interpreter: Optional[Any] = None,
        plan_add_interpreter: Optional[Any] = None,
    ) -> None:
        self._state_store = state_store
        self._plan_query_service = plan_query_service
        self._executor = executor
        self._result_verifier = result_verifier
        self._plan_update_interpreter = plan_update_interpreter
        self._plan_add_interpreter = plan_add_interpreter

    def _handle_impl(self, ctx: IntentContext) -> HandlerResult:
        intent = ctx.routing.intent
        if intent == "PLAN_DELETE":
            return self._handle_delete(ctx)
        if intent == "PLAN_UPDATE":
            return self._handle_update(ctx)
        if intent == "PLAN_ADD":
            return self._handle_add(ctx)
        return HandlerResult(session_updates=SessionUpdate())

    def _handle_delete(self, ctx: IntentContext) -> HandlerResult:
        state_store = self._state_store
        query_service = self._plan_query_service
        executor = self._executor

        if state_store is None:
            return _result("Plan state store is not available.")

        if query_service is None:
            return _result("Plan query service is not configured.")

        if executor is None:
            return _result("Semantic XPath executor is not configured.")

        task_id = ctx.session.active_task_id
        version_id = ctx.session.active_version_id

        if not task_id or not version_id:
            return _result(
                "No plan is currently loaded. Create a plan or open a task first."
            )

        try:
            core = state_store.load_core(task_id, version_id)
            plan_xml = core.xml_str
        except FileNotFoundError:
            return _result(
                "The plan for this task could not be found."
            )

        xml_manager = getattr(state_store, "xml_manager", None)
        if xml_manager is None:
            return _result("XML manager is not available.")

        schema = _plan_schema_from_xml(xml_manager, plan_xml)

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="PLAN_DELETE",
            context_messages=ctx.context_messages,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            return _result(
                "I couldn't understand what to remove. "
                "Try specifying the item, e.g. 'remove the museum' or 'delete day 1 lunch'."
            )
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=plan_xml,
                schema=schema,
            )
        except Exception:
            logger.exception(
                "PLAN_DELETE execute failed (task_id=%s, version_id=%s, xpath=%s)",
                task_id,
                version_id,
                gen_result.xpath_query,
            )
            return _result("Something went wrong while querying the plan.")

        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        step_scoring_trace = getattr(exec_result.retrieval_detail, "step_scoring_trace", []) or []
        if not per_node:
            return _result(
                "No matching content found to remove.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        if self._result_verifier and per_node:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="PLAN_DELETE",
                context={"active_task_id": task_id},
            )
            per_node = v_res.verified_nodes
        if not per_node:
            return _result(
                "No matching content found to remove.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        path_segments_list = []
        for item in per_node:
            ps = item.get("tree_path")
            if ps:
                path_segments_list.append(ps)

        if not path_segments_list:
            return _result("Could not determine which nodes to remove.")

        delete_ops = [DeleteXmlNode(path_segments=ps) for ps in path_segments_list]
        delete_ops.sort(key=lambda op: len(op.path_segments or []), reverse=True)

        try:
            commit_result = state_store.commit(
                task_id=task_id,
                base_version_id=version_id,
                ops=delete_ops,
                commit_message=request or "plan_delete",
            )
        except Exception as e:
            return _result(f"Failed to apply changes: {e}")

        if commit_result.status != "OK":
            err = commit_result.errors or ["Unknown error"]
            return _result(f"Failed to remove: {'; '.join(err)}")

        new_version_id = commit_result.new_version_id or version_id
        hint = _format_deleted_summary(per_node)

        # For delete, highlight parent containers only. Deleted node paths no
        # longer exist after commit and can reindex-match to wrong siblings.
        parent_paths: List[List[tuple]] = []
        seen_parent_keys = set()
        for item in per_node:
            ps = item.get("tree_path") or []
            if not ps:
                continue
            parent = list(ps[:-1]) if len(ps) > 0 else []
            if not parent:
                continue
            key = tuple(parent)
            if key in seen_parent_keys:
                continue
            seen_parent_keys.add(key)
            parent_paths.append(parent)

        affected_paths = parent_paths

        session_updates = SessionUpdate(active_version_id=new_version_id)

        return HandlerResult(
            session_updates=session_updates,
            generation_hint=hint,
            intent_result=IntentResult(
                intent="PLAN_DELETE",
                generation_hint=hint,
                xpath_query=gen_result.xpath_query,
                original_query=request,
                affected_node_paths=affected_paths,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            ),
        )

    def _handle_update(self, ctx: IntentContext) -> HandlerResult:
        state_store = self._state_store
        query_service = self._plan_query_service
        executor = self._executor
        interpreter = self._plan_update_interpreter

        if state_store is None:
            return _result_update("Plan state store is not available.")

        if query_service is None:
            return _result_update("Plan query service is not configured.")

        if executor is None:
            return _result_update("Semantic XPath executor is not configured.")

        if interpreter is None:
            return _result_update("Plan update interpreter is not configured.")

        task_id = ctx.session.active_task_id
        version_id = ctx.session.active_version_id

        if not task_id or not version_id:
            return _result_update(
                "No plan is currently loaded. Create a plan or open a task first."
            )

        try:
            core = state_store.load_core(task_id, version_id)
            plan_xml = core.xml_str
        except FileNotFoundError:
            return _result_update(
                "The plan for this task could not be found."
            )

        xml_manager = getattr(state_store, "xml_manager", None)
        if xml_manager is None:
            return _result_update("XML manager is not available.")

        schema = _plan_schema_from_xml(xml_manager, plan_xml)

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="PLAN_UPDATE",
            context_messages=ctx.context_messages,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            return _result_update(
                "I couldn't understand what to update. "
                "Try specifying the item, e.g. 'swap the museum and restaurant on day 1' or 'change dinner to 8pm'."
            )
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=plan_xml,
                schema=schema,
            )
        except Exception:
            logger.exception(
                "PLAN_UPDATE execute failed (task_id=%s, version_id=%s, xpath=%s)",
                task_id,
                version_id,
                gen_result.xpath_query,
            )
            return _result_update("Something went wrong while querying the plan.")

        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        step_scoring_trace = getattr(exec_result.retrieval_detail, "step_scoring_trace", []) or []
        if not per_node:
            return _result_update(
                "No matching content found to update.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        if self._result_verifier and per_node:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="PLAN_UPDATE",
                context={"active_task_id": task_id},
            )
            per_node = v_res.verified_nodes
        if not per_node:
            return _result_update(
                "No matching content found to update.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        item = per_node[0]
        path_segments = item.get("tree_path")
        if path_segments is None:
            return _result_update("Could not determine which node to update.")
        path_segments = path_segments if path_segments else []

        xml_fragment = _extract_xml_fragment_by_path_segments(plan_xml, path_segments)
        if not xml_fragment:
            return _result_update("Could not extract the content to update.")

        try:
            updated_xml = interpreter.interpret(
                xml_fragment=xml_fragment,
                user_request=request,
                context_messages=ctx.context_messages,
            )
        except ValueError as e:
            return _result_update(str(e))
        except Exception:
            return _result_update("Failed to apply the requested changes.")

        # Diff old vs new fragment to find precisely which child nodes changed
        affected_paths = _diff_xml_changed_paths(xml_fragment, updated_xml, path_segments)

        replace_op = ReplaceXmlNode(path_segments=path_segments, xml_fragment=updated_xml)

        try:
            commit_result = state_store.commit(
                task_id=task_id,
                base_version_id=version_id,
                ops=[replace_op],
                commit_message=request or "plan_update",
            )
        except Exception as e:
            return _result_update(f"Failed to apply changes: {e}")

        if commit_result.status != "OK":
            err = commit_result.errors or ["Unknown error"]
            return _result_update(f"Failed to update: {'; '.join(err)}")

        new_version_id = commit_result.new_version_id or version_id
        hint = _format_updated_summary(item, request)

        session_updates = SessionUpdate(active_version_id=new_version_id)

        return HandlerResult(
            session_updates=session_updates,
            generation_hint=hint,
            intent_result=IntentResult(
                intent="PLAN_UPDATE",
                generation_hint=hint,
                xpath_query=gen_result.xpath_query,
                original_query=request,
                affected_node_paths=affected_paths,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            ),
        )

    def _handle_add(self, ctx: IntentContext) -> HandlerResult:
        state_store = self._state_store
        query_service = self._plan_query_service
        executor = self._executor
        interpreter = self._plan_add_interpreter

        if state_store is None:
            return _result_add("Plan state store is not available.")

        if query_service is None:
            return _result_add("Plan query service is not configured.")

        if executor is None:
            return _result_add("Semantic XPath executor is not configured.")

        if interpreter is None:
            return _result_add("Plan add interpreter is not configured.")

        task_id = ctx.session.active_task_id
        version_id = ctx.session.active_version_id

        if not task_id or not version_id:
            return _result_add(
                "No plan is currently loaded. Create a plan or open a task first."
            )

        try:
            core = state_store.load_core(task_id, version_id)
            plan_xml = core.xml_str
        except FileNotFoundError:
            return _result_add(
                "The plan for this task could not be found."
            )

        xml_manager = getattr(state_store, "xml_manager", None)
        if xml_manager is None:
            return _result_add("XML manager is not available.")

        schema = _plan_schema_from_xml(xml_manager, plan_xml)

        request = ctx.routing.get_request(0, ctx.req.user_utterance) or ""
        gen_req = QueryGenerationRequest(
            utterance=request,
            loaded_schema=schema,
            intent="PLAN_ADD",
            context_messages=ctx.context_messages,
        )
        gen_result: QueryGenerationResult = query_service.generate(gen_req)

        if not gen_result.parsed_ok or not gen_result.xpath_query:
            return _result_add(
                "I couldn't understand where to add. "
                "Try specifying the container, e.g. 'add a lunch on day 1' or 'insert a coffee break between breakfast and lunch'."
            )
        try:
            exec_result = executor.execute(
                query=gen_result.xpath_query,
                xml_input=plan_xml,
                schema=schema,
            )
        except Exception:
            logger.exception(
                "PLAN_ADD execute failed (task_id=%s, version_id=%s, xpath=%s)",
                task_id,
                version_id,
                gen_result.xpath_query,
            )
            return _result_add("Something went wrong while querying the plan.")

        per_node = getattr(exec_result.retrieval_detail, "per_node", []) or []
        step_scoring_trace = getattr(exec_result.retrieval_detail, "step_scoring_trace", []) or []
        if not per_node:
            return _result_add(
                "No matching container found to add to.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        if self._result_verifier and per_node:
            v_res = self._result_verifier.verify(
                exec_result,
                request=request,
                intent="PLAN_ADD",
                context={"active_task_id": task_id},
            )
            per_node = v_res.verified_nodes
        if not per_node:
            return _result_add(
                "No matching container found to add to.",
                xpath_query=gen_result.xpath_query,
                original_query=request,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            )

        item = per_node[0]
        path_segments = item.get("tree_path")
        if path_segments is None:
            return _result_add("Could not determine which container to add to.")
        path_segments = path_segments if path_segments else []

        xml_fragment = _extract_xml_fragment_by_path_segments(plan_xml, path_segments)
        if not xml_fragment:
            return _result_add("Could not extract the container content.")

        try:
            updated_xml = interpreter.interpret(
                xml_fragment=xml_fragment,
                user_request=request,
                context_messages=ctx.context_messages,
            )
        except ValueError as e:
            return _result_add(str(e))
        except Exception:
            return _result_add("Failed to add the requested content.")

        # For create, only highlight truly newly-added content (ignore sibling reindex shifts).
        affected_paths = _diff_xml_added_paths(xml_fragment, updated_xml, path_segments)

        replace_op = ReplaceXmlNode(path_segments=path_segments, xml_fragment=updated_xml)

        try:
            commit_result = state_store.commit(
                task_id=task_id,
                base_version_id=version_id,
                ops=[replace_op],
                commit_message=request or "plan_add",
            )
        except Exception as e:
            return _result_add(f"Failed to apply changes: {e}")

        if commit_result.status != "OK":
            err = commit_result.errors or ["Unknown error"]
            return _result_add(f"Failed to add: {'; '.join(err)}")

        new_version_id = commit_result.new_version_id or version_id
        hint = _format_added_summary(item, request)

        session_updates = SessionUpdate(active_version_id=new_version_id)

        return HandlerResult(
            session_updates=session_updates,
            generation_hint=hint,
            intent_result=IntentResult(
                intent="PLAN_ADD",
                generation_hint=hint,
                xpath_query=gen_result.xpath_query,
                original_query=request,
                affected_node_paths=affected_paths,
                scoring_trace=step_scoring_trace,
                per_node_detail=per_node,
            ),
        )


def _format_added_summary(per_node_item: Dict[str, Any], request: str) -> str:
    """Format a short summary of what was added."""
    node = per_node_item.get("node") or {}
    path_data = per_node_item.get("tree_path_display") or per_node_item.get("tree_path") or []
    context = _path_to_display_str(path_data) if path_data else node.get("type", "container")
    return f"Added to {context}: {request}"


def _result_add(
    hint: str,
    xpath_query: Optional[str] = None,
    original_query: Optional[str] = None,
    scoring_trace: Optional[List[Dict[str, Any]]] = None,
    per_node_detail: Optional[List[Dict[str, Any]]] = None,
) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="PLAN_ADD",
            generation_hint=hint,
            xpath_query=xpath_query,
            original_query=original_query,
            scoring_trace=scoring_trace,
            per_node_detail=per_node_detail,
        ),
    )


def _extract_xml_fragment_by_path_segments(
    plan_xml: str, path_segments: List[tuple]
) -> Optional[str]:
    """Extract the XML fragment for the node at path_segments using tree walk."""
    try:
        root = ET.fromstring(plan_xml)
        node = find_by_path_segments(root, path_segments)
        if node is None:
            return None
        return ET.tostring(node, encoding="unicode")
    except Exception:
        return None


def _diff_xml_changed_paths(
    old_xml_str: str, new_xml_str: str, base_path: List[tuple]
) -> List[List[tuple]]:
    """Compare old/new XML fragments and return tree_paths of actually changed nodes.

    Walks both trees in parallel. Only paths that exist in the *new* tree are
    returned so the frontend can highlight them on the current plan.
    Falls back to ``[base_path]`` on parse errors or when no diff is detected.
    """
    try:
        old_root = ET.fromstring(old_xml_str)
        new_root = ET.fromstring(new_xml_str)
    except ET.ParseError:
        return [list(base_path)]

    changed: List[List[tuple]] = []
    _diff_walk(old_root, new_root, list(base_path), changed)
    return changed if changed else [list(base_path)]


def _diff_xml_added_paths(
    old_xml_str: str, new_xml_str: str, base_path: List[tuple]
) -> List[List[tuple]]:
    """Return paths of leaf nodes that are newly added in the new fragment.

    This matcher is order-insensitive: it compares old/new leaf signatures as a
    multiset, so inserting siblings at the front does not make existing nodes
    look "changed". It is intended for PLAN_ADD highlighting.
    """
    try:
        old_root = ET.fromstring(old_xml_str)
        new_root = ET.fromstring(new_xml_str)
    except ET.ParseError:
        return [list(base_path)]

    old_signatures: Counter[str] = Counter()
    _collect_leaf_signatures(old_root, old_signatures)

    added_paths: List[List[tuple]] = []
    _collect_added_leaf_paths(new_root, list(base_path), old_signatures, added_paths)
    return added_paths if added_paths else [list(base_path)]


def _leaf_signature(el: ET.Element) -> str:
    """Build a stable content signature for a leaf node."""
    attrs = "|".join(f"{k}={v}" for k, v in sorted(el.attrib.items()))
    text = (el.text or "").strip()
    return f"{el.tag}||{attrs}||{text}"


def _collect_leaf_signatures(el: ET.Element, bag: Counter[str]) -> None:
    """Collect leaf signatures from a subtree into a multiset."""
    children = list(el)
    if not children:
        bag[_leaf_signature(el)] += 1
        return
    for child in children:
        _collect_leaf_signatures(child, bag)


def _collect_added_leaf_paths(
    el: ET.Element,
    path: List[tuple],
    old_bag: Counter[str],
    result: List[List[tuple]],
) -> None:
    """Traverse new subtree and keep only leaves not consumed by old_bag."""
    children = list(el)
    if not children:
        sig = _leaf_signature(el)
        if old_bag[sig] > 0:
            old_bag[sig] -= 1
        else:
            result.append(list(path))
        return

    groups: Dict[str, list] = {}
    for c in children:
        groups.setdefault(c.tag, []).append(c)

    for tag, group in groups.items():
        for i, child in enumerate(group):
            _collect_added_leaf_paths(child, path + [(tag, i + 1)], old_bag, result)


def _diff_walk(
    old_el: ET.Element,
    new_el: ET.Element,
    path: List[tuple],
    changed: List[List[tuple]],
) -> None:
    """Recursively compare two XML elements, collecting paths of changed nodes."""
    old_children = list(old_el)
    new_children = list(new_el)

    # Leaf node: compare text and attributes
    if not old_children and not new_children:
        old_text = (old_el.text or "").strip()
        new_text = (new_el.text or "").strip()
        if old_text != new_text or old_el.attrib != new_el.attrib:
            changed.append(list(path))
        return

    # Group children by tag name
    def _group_by_tag(children: list) -> Dict[str, list]:
        groups: Dict[str, list] = {}
        for c in children:
            groups.setdefault(c.tag, []).append(c)
        return groups

    old_groups = _group_by_tag(old_children)
    new_groups = _group_by_tag(new_children)
    all_tags = sorted(set(list(old_groups.keys()) + list(new_groups.keys())))

    for tag in all_tags:
        old_list = old_groups.get(tag, [])
        new_list = new_groups.get(tag, [])

        for i in range(len(new_list)):
            child_path = path + [(tag, i + 1)]
            if i < len(old_list):
                _diff_walk(old_list[i], new_list[i], child_path, changed)
            else:
                # Newly added node — mark all its leaves as changed
                _collect_leaves(new_list[i], child_path, changed)

    # Check direct text / attribute changes on this (non-leaf) node
    old_text = (old_el.text or "").strip()
    new_text = (new_el.text or "").strip()
    if old_text != new_text or old_el.attrib != new_el.attrib:
        changed.append(list(path))


def _collect_leaves(
    el: ET.Element, path: List[tuple], result: List[List[tuple]]
) -> None:
    """Collect paths for all leaf nodes in a subtree (for newly added nodes)."""
    children = list(el)
    if not children:
        result.append(list(path))
        return
    groups: Dict[str, list] = {}
    for c in children:
        groups.setdefault(c.tag, []).append(c)
    for tag, group in groups.items():
        for i, child in enumerate(group):
            _collect_leaves(child, path + [(tag, i + 1)], result)


def _format_updated_summary(per_node_item: Dict[str, Any], request: str) -> str:
    """Format a short summary of what was updated."""
    node = per_node_item.get("node") or {}
    path_data = per_node_item.get("tree_path_display") or per_node_item.get("tree_path") or []
    context = _path_to_display_str(path_data) if path_data else node.get("type", "item")
    return f"Updated {context}: {request}"


def _result_update(
    hint: str,
    xpath_query: Optional[str] = None,
    original_query: Optional[str] = None,
    scoring_trace: Optional[List[Dict[str, Any]]] = None,
    per_node_detail: Optional[List[Dict[str, Any]]] = None,
) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="PLAN_UPDATE",
            generation_hint=hint,
            xpath_query=xpath_query,
            original_query=original_query,
            scoring_trace=scoring_trace,
            per_node_detail=per_node_detail,
        ),
    )


def _result(
    hint: str,
    xpath_query: Optional[str] = None,
    original_query: Optional[str] = None,
    scoring_trace: Optional[List[Dict[str, Any]]] = None,
    per_node_detail: Optional[List[Dict[str, Any]]] = None,
) -> HandlerResult:
    return HandlerResult(
        session_updates=SessionUpdate(),
        generation_hint=hint,
        intent_result=IntentResult(
            intent="PLAN_DELETE",
            generation_hint=hint,
            xpath_query=xpath_query,
            original_query=original_query,
            scoring_trace=scoring_trace,
            per_node_detail=per_node_detail,
        ),
    )
