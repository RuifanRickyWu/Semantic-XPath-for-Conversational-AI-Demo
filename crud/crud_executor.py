"""
CRUD Executor - Orchestrates the full CRUD pipeline with 2-stage query processing.

2-Stage Query Processing:
1. Version Resolution (LLM Call 1): Determines version selector and CRUD operation
2. XPath Generation (LLM Call 2): Generates tree-traversal semantic XPath query

Coordinates:
- Version resolution from in-tree versioning
- Semantic XPath query execution
- LLM reasoning for node selection
- Tree modifications (for Create, Update, Delete)
- Content generation (for Create, Update)
- In-tree version management

Includes step-by-step timing for performance analysis.
"""

import logging
import copy
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import xml.etree.ElementTree as ET
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from version_resolver import VersionResolver, VersionSelector, ResolvedVersion
from xpath_query_generation import XPathQueryGenerator, CRUDOperation, ParsedQuery
from dense_xpath import DenseXPathExecutor
from reasoner import NodeReasoner, InsertionReasoner, BatchReasoningResult
from tree_modification import NodeDeleter, NodeInserter, VersionManager, OperationResult
from content_creator import NodeCreator, NodeUpdater, ContentGenerationResult, ContentUpdateResult


logger = logging.getLogger(__name__)

# Result directory for saved trees
RESULT_DIR = Path(__file__).parent.parent / "result" / "demo"


class StepTimer:
    """Helper class to track timing of individual steps."""
    
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self._current_start: Optional[float] = None
        self._current_name: Optional[str] = None
    
    def start(self, step_name: str):
        """Start timing a step."""
        self._current_name = step_name
        self._current_start = time.perf_counter()
    
    def stop(self):
        """Stop timing the current step and record it."""
        if self._current_start is not None and self._current_name is not None:
            elapsed_ms = (time.perf_counter() - self._current_start) * 1000
            self.steps.append({
                "step": self._current_name,
                "time_ms": round(elapsed_ms, 2)
            })
            self._current_start = None
            self._current_name = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Return timing summary."""
        total_ms = sum(s["time_ms"] for s in self.steps)
        return {
            "steps": self.steps,
            "total_ms": round(total_ms, 2)
        }
    
    def print_summary(self):
        """Print a formatted timing summary."""
        print("\n⏱️  Step Timing:")
        print("-" * 50)
        total = sum(s["time_ms"] for s in self.steps)
        for step in self.steps:
            pct = (step["time_ms"] / total * 100) if total > 0 else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {step['step']:<30} {step['time_ms']:>8.1f}ms  {bar} {pct:>5.1f}%")
        print("-" * 50)
        print(f"  {'TOTAL':<30} {total:>8.1f}ms")


class CRUDExecutor:
    """
    Main executor for CRUD operations with 2-stage query processing.
    
    Orchestrates the full pipeline:
    1. Version Resolution (LLM Call 1) - determines version selector and CRUD operation
    2. Version Lookup - finds the actual version element in the tree
    3. XPath Generation (LLM Call 2) - generates tree-traversal query
    4. Semantic XPath Execution - runs the query on the version subtree
    5. LLM Reasoning - filters/selects nodes
    6. Tree Modification (if applicable)
    7. New Version Creation
    
    Trees are modified in-place with versions stored as child nodes.
    """
    
    def __init__(
        self,
        scoring_method: str = None,
        top_k: int = None,
        score_threshold: float = None
    ):
        """
        Initialize the CRUD executor.
        
        Args:
            scoring_method: Scoring method for semantic XPath
            top_k: Number of top results to consider
            score_threshold: Minimum score threshold
        """
        # Ensure result directory exists
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize 2-stage query components
        self.version_resolver = VersionResolver()
        self.query_generator = XPathQueryGenerator()
        
        # Initialize execution components
        self.executor = DenseXPathExecutor(
            scoring_method=scoring_method,
            top_k=top_k,
            score_threshold=score_threshold
        )
        # Pass schema to NodeReasoner for schema-aware field formatting
        self.node_reasoner = NodeReasoner(schema=self.executor._schema)
        self.insertion_reasoner = InsertionReasoner()
        self.node_deleter = NodeDeleter()
        self.node_inserter = NodeInserter()
        self.version_manager = VersionManager(base_directory=RESULT_DIR)
        self.node_creator = NodeCreator()
        self.node_updater = NodeUpdater()
        
        # Store reference to tree for modifications
        self._tree = None
    
    @property
    def tree(self) -> ET.ElementTree:
        """Get the current tree (loads from executor if needed)."""
        if self._tree is None:
            self._tree = copy.deepcopy(self.executor.tree)
        return self._tree
    
    def _sync_executor_tree(self):
        """
        Sync the DenseXPathExecutor's tree with our modified tree.
        
        This must be called after any modification to ensure subsequent
        queries operate on the updated tree.
        """
        # Update the executor's tree reference to our modified tree
        self.executor._tree = self._tree
        self.executor._root = self._tree.getroot()
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Execute a CRUD operation based on the user's query.
        
        Uses 2-stage query processing:
        1. Version Resolution (LLM Call 1)
        2. XPath Generation (LLM Call 2)
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            Dict with operation results, traces, timing info, and modified tree info
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        timer = StepTimer()
        
        # Stage 1: Version Resolution (LLM Call 1)
        timer.start("Stage 1: Version Resolution (LLM)")
        version_result = self.version_resolver.resolve(user_query)
        timer.stop()
        
        logger.info(f"Version resolved: {version_result.get_version_selector_string()}, {version_result.crud_operation.value}")
        print(f"\n🔍 Version: {version_result.get_version_selector_string()}")
        print(f"📋 Operation: {version_result.crud_operation.value}")
        
        # Stage 1.5: Version Lookup
        timer.start("Version Lookup")
        target_version = self._resolve_version_element(version_result)
        timer.stop()
        
        if target_version is None:
            return {
                "success": False,
                "error": "No version found in tree",
                "timestamp": timestamp,
                "user_query": user_query,
                "version_resolution": version_result.to_dict()
            }
        
        version_number = target_version.get("number", "?")
        logger.info(f"Operating on version {version_number}")
        print(f"📁 Target version: {version_number}")
        
        # Stage 2: XPath Generation (LLM Call 2)
        timer.start("Stage 2: XPath Generation (LLM)")
        parsed_query = self.query_generator.generate_and_parse(
            user_query, 
            version_result.crud_operation
        )
        timer.stop()
        
        logger.info(f"Generated XPath: {parsed_query.xpath}")
        print(f"🛤️  XPath: {parsed_query.xpath}")
        
        # Stage 3: Execute based on operation type
        if version_result.crud_operation == CRUDOperation.READ:
            result = self._execute_read(user_query, parsed_query, target_version, timer)
        elif version_result.crud_operation == CRUDOperation.DELETE:
            result = self._execute_delete(user_query, parsed_query, target_version, timer)
        elif version_result.crud_operation == CRUDOperation.UPDATE:
            result = self._execute_update(user_query, parsed_query, target_version, timer)
        elif version_result.crud_operation == CRUDOperation.CREATE:
            result = self._execute_create(user_query, parsed_query, target_version, timer)
        else:
            result = {"error": f"Unknown operation: {version_result.crud_operation}"}
        
        # Add common fields
        result["timestamp"] = timestamp
        result["user_query"] = user_query
        result["version_resolution"] = version_result.to_dict()
        result["parsed_query"] = parsed_query.to_dict()
        result["version_used"] = version_number
        result["timing"] = timer.to_dict()
        
        # Print timing summary
        timer.print_summary()
        
        return result
    
    def _resolve_version_element(self, version_result: ResolvedVersion) -> Optional[ET.Element]:
        """
        Resolve the actual version element from the version resolution result.
        
        Handles both 'at' and 'before' selectors.
        
        Args:
            version_result: Result from version resolver
            
        Returns:
            The target Version/Itinerary_Version element, or None
        """
        # Find version by semantic query or index
        if version_result.semantic_query:
            # Semantic version lookup
            matched_version = self.version_manager.get_version_by_semantic(
                self.tree,
                version_result.semantic_query,
                scorer=self.executor.scorer
            )
        else:
            # Index-based version lookup
            matched_version = self.version_manager.get_version_by_number(
                self.tree,
                version_result.index
            )
        
        # If 'before' selector, get the previous version
        if version_result.selector_type == VersionSelector.BEFORE and matched_version is not None:
            return self.version_manager.get_previous_version(self.tree, matched_version)
        
        return matched_version
    
    def _execute_read(
        self,
        user_query: str,
        parsed_query: ParsedQuery,
        target_version: ET.Element,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a READ operation on a specific version."""
        # Build xpath for version subtree
        xpath_query = self._build_version_xpath(parsed_query.xpath, target_version)
        
        # Execute semantic XPath
        timer.start("Semantic XPath Execution")
        execution_result = self.executor.execute(xpath_query)
        timer.stop()
        
        # Apply LLM reasoning to filter results
        timer.start("LLM Node Reasoning")
        candidates = [m.to_dict() for m in execution_result.matched_nodes]
        reasoning_result = self.node_reasoner.reason(
            candidates, 
            user_query, 
            operation="READ"
        )
        timer.stop()
        
        # Get final selected nodes with full info (tree_path and children)
        # Build a lookup from tree_path to candidate for retrieving children
        candidate_lookup = {c.get("tree_path"): c for c in candidates}
        
        selected = []
        for r in reasoning_result.selected_nodes:
            # Get the original candidate to retrieve children
            original_candidate = candidate_lookup.get(r.node_path, {})
            selected.append({
                **r.node_data,
                "tree_path": r.node_path,
                "children": original_candidate.get("children", [])
            })
        
        return {
            "operation": "READ",
            "success": True,
            "candidates_count": len(candidates),
            "selected_count": len(selected),
            "selected_nodes": selected,
            "execution_result": {
                "query": execution_result.query,
                "matched_count": len(execution_result.matched_nodes),
                "execution_time_ms": execution_result.execution_time_ms
            },
            "reasoning_trace": reasoning_result.to_dict()
        }
    
    def _execute_delete(
        self,
        user_query: str,
        parsed_query: ParsedQuery,
        target_version: ET.Element,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a DELETE operation and create a new version."""
        # Build xpath for version subtree
        xpath_query = self._build_version_xpath(parsed_query.xpath, target_version)
        
        # Execute semantic XPath
        timer.start("Semantic XPath Execution")
        execution_result = self.executor.execute(xpath_query)
        timer.stop()
        
        # Apply LLM reasoning to select nodes to delete
        timer.start("LLM Node Reasoning")
        candidates = [m.to_dict() for m in execution_result.matched_nodes]
        reasoning_result = self.node_reasoner.reason(
            candidates,
            user_query,
            operation="DELETE"
        )
        timer.stop()
        
        if not reasoning_result.selected_nodes:
            return {
                "operation": "DELETE",
                "success": False,
                "message": "No nodes selected for deletion",
                "candidates_count": len(candidates),
                "reasoning_trace": reasoning_result.to_dict()
            }
        
        # Copy version content for modification
        timer.start("Version Copy")
        new_version_content = self._copy_version_content(target_version)
        timer.stop()
        
        # Delete selected nodes from the copy
        timer.start("Tree Modification")
        deletion_results = []
        deleted_paths = []
        
        for node_result in reasoning_result.selected_nodes:
            tree_path = node_result.node_path
            # Adjust path to be relative to version content
            relative_path = self._adjust_path_for_version(tree_path, target_version)
            result = self._delete_from_content(new_version_content, relative_path)
            deletion_results.append({"path": relative_path, "success": result})
            
            if result:
                deleted_paths.append(tree_path)
        timer.stop()
        
        # Create new version
        timer.start("Create New Version")
        version_info = None
        if deleted_paths:
            patch_info = f"Deleted: {', '.join(deleted_paths)}"
            new_version = self.version_manager.create_new_version(
                self.tree,
                target_version,
                patch_info=patch_info,
                conversation_history=user_query,
                modified_content=new_version_content
            )
            
            # Save the tree
            version_info = self.version_manager.save_tree(
                self.tree,
                self.executor.memory_path
            )
            
            # Sync executor tree for subsequent operations
            self._sync_executor_tree()
        timer.stop()
        
        return {
            "operation": "DELETE",
            "success": len(deleted_paths) > 0,
            "deleted_count": len(deleted_paths),
            "deleted_paths": deleted_paths,
            "deletion_results": deletion_results,
            "reasoning_trace": reasoning_result.to_dict(),
            "tree_version": version_info.to_dict() if version_info else None
        }
    
    def _execute_update(
        self,
        user_query: str,
        parsed_query: ParsedQuery,
        target_version: ET.Element,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute an UPDATE operation and create a new version."""
        # Build xpath for version subtree
        xpath_query = self._build_version_xpath(parsed_query.xpath, target_version)
        
        # Execute semantic XPath
        timer.start("Semantic XPath Execution")
        execution_result = self.executor.execute(xpath_query)
        timer.stop()
        
        # Apply LLM reasoning to select nodes to update
        timer.start("LLM Node Reasoning")
        candidates = [m.to_dict() for m in execution_result.matched_nodes]
        reasoning_result = self.node_reasoner.reason(
            candidates,
            user_query,
            operation="UPDATE"
        )
        timer.stop()
        
        if not reasoning_result.selected_nodes:
            return {
                "operation": "UPDATE",
                "success": False,
                "message": "No nodes selected for update",
                "candidates_count": len(candidates),
                "reasoning_trace": reasoning_result.to_dict()
            }
        
        # Copy version content for modification
        timer.start("Version Copy")
        new_version_content = self._copy_version_content(target_version)
        timer.stop()
        
        # Update selected nodes
        update_results = []
        updated_paths = []
        
        for node_result in reasoning_result.selected_nodes:
            tree_path = node_result.node_path
            relative_path = self._adjust_path_for_version(tree_path, target_version)
            
            # Find the node in the copy
            original_node = self._find_node_in_content(new_version_content, relative_path)
            
            if original_node is None:
                update_results.append({
                    "success": False,
                    "path": tree_path,
                    "error": "Node not found in version"
                })
                continue
            
            # Get update details
            operation_details = {}
            if parsed_query.update_info:
                operation_details = parsed_query.update_info[1]
            
            # Generate updated content
            timer.start("LLM Content Update")
            update_content = self.node_updater.update_node(
                user_query,
                original_node,
                operation_details
            )
            timer.stop()
            
            if not update_content.success or update_content.xml_element is None:
                update_results.append({
                    "success": False,
                    "path": tree_path,
                    "error": "Content generation failed"
                })
                continue
            
            # Replace the node in the copy
            timer.start("Tree Modification")
            replace_result = self._replace_in_content(
                new_version_content, 
                relative_path, 
                update_content.xml_element
            )
            timer.stop()
            
            update_results.append({
                "success": replace_result,
                "path": tree_path,
                "changes": update_content.to_dict()
            })
            
            if replace_result:
                updated_paths.append(tree_path)
        
        # Create new version
        timer.start("Create New Version")
        version_info = None
        if updated_paths:
            patch_info = f"Updated: {', '.join(updated_paths)}"
            new_version = self.version_manager.create_new_version(
                self.tree,
                target_version,
                patch_info=patch_info,
                conversation_history=user_query,
                modified_content=new_version_content
            )
            
            # Save the tree
            version_info = self.version_manager.save_tree(
                self.tree,
                self.executor.memory_path
            )
            
            # Sync executor tree for subsequent operations
            self._sync_executor_tree()
        timer.stop()
        
        return {
            "operation": "UPDATE",
            "success": len(updated_paths) > 0,
            "updated_count": len(updated_paths),
            "updated_paths": updated_paths,
            "update_results": update_results,
            "reasoning_trace": reasoning_result.to_dict(),
            "tree_version": version_info.to_dict() if version_info else None
        }
    
    def _execute_create(
        self,
        user_query: str,
        parsed_query: ParsedQuery,
        target_version: ET.Element,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a CREATE operation and create a new version."""
        # Get create info
        if not parsed_query.create_info:
            return {
                "operation": "CREATE",
                "success": False,
                "message": "No create information provided"
            }
        
        parent_path, node_type, description = parsed_query.create_info
        
        # Build xpath for finding parent context
        xpath_query = self._build_version_xpath(parent_path, target_version)
        
        # Execute semantic XPath to find context
        timer.start("Semantic XPath Execution")
        execution_result = self.executor.execute(xpath_query)
        timer.stop()
        
        # Get parent candidates for insertion
        candidates = [m.to_dict() for m in execution_result.matched_nodes]
        
        # Build lookup for children data by tree_path
        children_lookup = {c.get("tree_path"): c.get("children", []) for c in candidates}
        
        # Apply reasoning to find relevant context
        timer.start("LLM Node Reasoning")
        reasoning_result = self.node_reasoner.reason(
            candidates,
            user_query,
            operation="CREATE"
        )
        timer.stop()
        
        # Determine parent candidates - preserve children from original candidates
        if reasoning_result.selected_nodes:
            parent_candidates = []
            for r in reasoning_result.selected_nodes:
                result_dict = r.to_dict()
                # Add children from original candidates (not stored in NodeReasoningResult)
                result_dict["children"] = children_lookup.get(result_dict.get("tree_path"), [])
                parent_candidates.append(result_dict)
        else:
            parent_candidates = candidates
        
        if not parent_candidates:
            # Fallback to version root
            parent_candidates = [{
                "tree_path": f"Itinerary_Version {target_version.get('number', '?')}",
                "node": {"type": "Itinerary_Version"},
                "children": [{"type": c.tag} for c in self.version_manager.get_version_content(target_version)]
            }]
        
        # Find best insertion point
        timer.start("LLM Insertion Reasoning")
        insertion_point = self.insertion_reasoner.find_insertion_point(
            user_query,
            parent_candidates,
            {"new_content": description, "node_type": node_type}
        )
        timer.stop()
        
        # Generate content for new node
        timer.start("LLM Content Creation")
        context = {
            "parent": parent_candidates[0].get("node", {}) if parent_candidates else {},
            "siblings": insertion_point.sibling_context.get("children", [])
        }
        
        content_result = self.node_creator.create_node(
            user_query,
            node_type,
            context,
            {"new_content": description}
        )
        timer.stop()
        
        if not content_result.success or content_result.xml_element is None:
            return {
                "operation": "CREATE",
                "success": False,
                "message": "Content generation failed",
                "content_result": content_result.to_dict(),
                "insertion_point": insertion_point.to_dict()
            }
        
        # Copy version content for modification
        timer.start("Version Copy")
        new_version_content = self._copy_version_content(target_version)
        timer.stop()
        
        # Insert the new node
        timer.start("Tree Modification")
        relative_parent_path = self._adjust_path_for_version(insertion_point.parent_path, target_version)
        insert_result = self._insert_in_content(
            new_version_content,
            relative_parent_path,
            content_result.xml_element,
            insertion_point.position
        )
        timer.stop()
        
        # Create new version
        timer.start("Create New Version")
        version_info = None
        created_path = None
        if insert_result:
            created_path = f"{insertion_point.parent_path}/{node_type}"
            patch_info = f"Created: {created_path}"
            new_version = self.version_manager.create_new_version(
                self.tree,
                target_version,
                patch_info=patch_info,
                conversation_history=user_query,
                modified_content=new_version_content
            )
            
            # Save the tree
            version_info = self.version_manager.save_tree(
                self.tree,
                self.executor.memory_path
            )
            
            # Sync executor tree for subsequent operations
            self._sync_executor_tree()
        timer.stop()
        
        return {
            "operation": "CREATE",
            "success": insert_result,
            "created_path": created_path if insert_result else None,
            "content_result": content_result.to_dict(),
            "insertion_point": insertion_point.to_dict(),
            "reasoning_trace": reasoning_result.to_dict(),
            "tree_version": version_info.to_dict() if version_info else None
        }
    
    def _build_version_xpath(self, xpath: str, version: ET.Element) -> str:
        """
        Build an xpath query that targets the specific version.
        
        Args:
            xpath: Original xpath (from XPath generator, starts with /Itinerary)
            version: The target Itinerary_Version element
            
        Returns:
            XPath query targeting the version
        """
        version_number = version.get("number", "1")
        
        # Handle paths that start with /Itinerary
        if xpath.startswith("/Itinerary"):
            remaining = xpath[len("/Itinerary"):]
            return f"/Root/Itinerary_Version[@number='{version_number}']/Itinerary{remaining}"
        
        # If xpath doesn't start with /Itinerary, prepend full path
        if not xpath.startswith("/"):
            xpath = "/" + xpath
        
        return f"/Root/Itinerary_Version[@number='{version_number}']/Itinerary{xpath}"
    
    def _copy_version_content(self, version: ET.Element) -> List[ET.Element]:
        """
        Create a deep copy of the content nodes from a version.
        
        For the new structure, this returns the Itinerary element's children (Days).
        
        Args:
            version: The Itinerary_Version element
            
        Returns:
            List of deep-copied content elements
        """
        # Find the Itinerary element within the version
        itinerary = version.find("Itinerary")
        if itinerary is not None:
            return [copy.deepcopy(child) for child in itinerary]
        
        # Fallback: return non-metadata children
        return [
            copy.deepcopy(child) 
            for child in version 
            if child.tag not in ("patch_info", "conversation_history", "Itinerary")
        ]
    
    def _adjust_path_for_version(self, tree_path: str, version: ET.Element) -> str:
        """
        Adjust a tree path to be relative to version content.
        
        Removes the Root, Itinerary_Version, and Itinerary prefix from the path.
        
        Args:
            tree_path: Full tree path (e.g., "Root > Itinerary_Version 1 > Itinerary > Day 1 > POI 2")
            version: The Itinerary_Version element
            
        Returns:
            Path relative to Itinerary content (e.g., "Day 1 > POI 2")
        """
        parts = [p.strip() for p in tree_path.split(">")]
        
        # Skip Root, Itinerary_Version, and Itinerary
        result_parts = []
        for part in parts:
            if part == "Root":
                continue
            if part.startswith("Itinerary_Version"):
                continue
            if part == "Itinerary":
                continue
            result_parts.append(part)
        
        return " > ".join(result_parts)
    
    def _find_node_in_content(
        self, 
        content: List[ET.Element], 
        relative_path: str
    ) -> Optional[ET.Element]:
        """
        Find a node within the content list by relative path.
        
        Supports multiple path formats:
        - Indexed: "Day 1 > POI 2"
        - Name-based: "Day 1 > Royal Ontario Museum"
        - Tag-based: "Day > POI"
        
        Args:
            content: List of content elements
            relative_path: Path relative to version
            
        Returns:
            The found element, or None
        """
        if not relative_path:
            return None
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        # Find the first element in content
        first_part = parts[0]
        current = self._find_element_by_part(content, first_part)
        
        if current is None:
            return None
        
        # Navigate remaining path
        for part in parts[1:]:
            children = list(current)
            current = self._find_element_by_part(children, part)
            if current is None:
                return None
        
        return current
    
    def _find_element_by_part(
        self,
        elements: List[ET.Element],
        part: str
    ) -> Optional[ET.Element]:
        """
        Find an element in a list by a path part.
        
        Handles:
        - Indexed notation: "Day 1", "POI 2"
        - Name-based: "Royal Ontario Museum"
        - Tag-based: "Day", "POI"
        
        Args:
            elements: List of elements to search
            part: Path part to match
            
        Returns:
            The found element, or None
        """
        words = part.split()
        
        # Case 1: Indexed notation like "Day 1" or "POI 2"
        if len(words) == 2 and words[1].isdigit():
            node_type = words[0]
            index = int(words[1])
            
            # Check for index/number attribute first (for Day, Itinerary_Version)
            for elem in elements:
                if elem.tag == node_type:
                    elem_index = elem.get("index") or elem.get("number")
                    if elem_index == str(index):
                        return elem
            
            # Fall back to positional index
            matching = [e for e in elements if e.tag == node_type]
            if 0 < index <= len(matching):
                return matching[index - 1]
            
            return None
        
        # Case 2: Try direct tag match
        for elem in elements:
            if elem.tag == part:
                return elem
        
        # Case 3: Try name-based match (search by <name> or <title> element)
        for elem in elements:
            name_elem = elem.find("name")
            if name_elem is not None and name_elem.text and name_elem.text.strip() == part:
                return elem
            
            title_elem = elem.find("title")
            if title_elem is not None and title_elem.text and title_elem.text.strip() == part:
                return elem
        
        return None
    
    def _delete_from_content(
        self, 
        content: List[ET.Element], 
        relative_path: str
    ) -> bool:
        """
        Delete a node from the content list.
        
        Supports multiple path formats:
        - Indexed: "Day 1 > POI 2"
        - Name-based: "Day 1 > Royal Ontario Museum"
        
        Args:
            content: List of content elements (will be modified)
            relative_path: Path to the node to delete
            
        Returns:
            True if deletion succeeded
        """
        if not relative_path:
            return False
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        if len(parts) == 1:
            # Delete from top level - find and remove from content list
            old_elem = self._find_element_by_part(content, parts[0])
            if old_elem is not None:
                content.remove(old_elem)
                return True
            return False
        
        # Find parent and delete child
        parent_path = " > ".join(parts[:-1])
        parent = self._find_node_in_content(content, parent_path)
        
        if parent is None:
            return False
        
        child_part = parts[-1]
        
        # Find the child to delete
        old_child = self._find_element_by_part(list(parent), child_part)
        
        if old_child is not None:
            parent.remove(old_child)
            return True
        
        return False
    
    def _replace_in_content(
        self,
        content: List[ET.Element],
        relative_path: str,
        new_element: ET.Element
    ) -> bool:
        """
        Replace a node in the content list.
        
        Supports multiple path formats:
        - Indexed: "Day 1 > POI 2"
        - Name-based: "Day 1 > Royal Ontario Museum"
        
        Args:
            content: List of content elements (will be modified)
            relative_path: Path to the node to replace
            new_element: The replacement element
            
        Returns:
            True if replacement succeeded
        """
        if not relative_path:
            return False
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        if len(parts) == 1:
            # Replace at top level - find and replace in content list
            old_elem = self._find_element_by_part(content, parts[0])
            if old_elem is not None:
                idx = content.index(old_elem)
                content[idx] = new_element
                return True
            return False
        
        # Find parent and replace child
        parent_path = " > ".join(parts[:-1])
        parent = self._find_node_in_content(content, parent_path)
        
        if parent is None:
            return False
        
        child_part = parts[-1]
        
        # Find the child to replace
        old_child = self._find_element_by_part(list(parent), child_part)
        
        if old_child is not None:
            idx = list(parent).index(old_child)
            parent.remove(old_child)
            parent.insert(idx, new_element)
            return True
        
        return False
    
    def _insert_in_content(
        self,
        content: List[ET.Element],
        relative_parent_path: str,
        new_element: ET.Element,
        position: int = -1
    ) -> bool:
        """
        Insert a new node into the content.
        
        Args:
            content: List of content elements (will be modified)
            relative_parent_path: Path to the parent node
            new_element: The element to insert
            position: Position to insert at (-1 for end)
            
        Returns:
            True if insertion succeeded
        """
        if not relative_parent_path:
            # Insert at top level
            if position < 0:
                content.append(new_element)
            else:
                content.insert(position, new_element)
            return True
        
        parent = self._find_node_in_content(content, relative_parent_path)
        
        if parent is None:
            return False
        
        if position < 0:
            parent.append(new_element)
        else:
            parent.insert(position, new_element)
        
        return True
    
    def reload_tree(self):
        """Reload the tree from the original file."""
        self._tree = None
        self.executor._tree = None
        self.executor._root = None
