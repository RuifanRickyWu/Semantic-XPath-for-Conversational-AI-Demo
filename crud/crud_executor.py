"""
CRUD Executor - Orchestrates the full CRUD pipeline with 2-stage query processing.

Pipeline Stages:
1. Version Resolution (LLM Call 1): Determines version selector and CRUD operation
2. XPath Generation (LLM Call 2): Generates tree-traversal semantic XPath query
3. XPath Execution: Runs semantic XPath to retrieve candidate nodes
4. Downstream Task (LLM Call 3): Single-LLM handler for CRUD-specific processing

Coordinates:
- Version resolution from in-tree versioning
- Semantic XPath query execution
- CRUD-specific handlers (Read, Delete, Update, Create)
- Tree modifications (for Create, Update, Delete)
- In-tree version management

Includes stage-by-stage timing and token usage tracking.
"""

import logging
import copy
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from version_resolver import VersionResolver, VersionSelector, ResolvedVersion
from xpath_query_generation import XPathQueryGenerator, CRUDOperation, ParsedQuery
from dense_xpath import DenseXPathExecutor
from tree_modification import VersionManager

from .read_handler import ReadHandler
from .delete_handler import DeleteHandler
from .update_handler import UpdateHandler
from .create_handler import CreateHandler
from .base import HandlerResult


logger = logging.getLogger(__name__)

# Result directory for saved trees
RESULT_DIR = Path(__file__).parent.parent / "result" / "demo"


@dataclass
class StageResult:
    """Result from a pipeline stage."""
    name: str
    time_ms: float
    token_usage: Optional[Dict[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "time_ms": round(self.time_ms, 2)
        }
        if self.token_usage:
            result["token_usage"] = self.token_usage
        return result


@dataclass
class PipelineTimer:
    """Tracks timing and token usage across pipeline stages."""
    stages: List[StageResult] = field(default_factory=list)
    _current_start: Optional[float] = None
    _current_name: Optional[str] = None
    
    def start(self, stage_name: str):
        """Start timing a stage."""
        self._current_name = stage_name
        self._current_start = time.perf_counter()
    
    def stop(self, token_usage: Optional[Dict[str, int]] = None):
        """Stop timing the current stage and record it."""
        if self._current_start is not None and self._current_name is not None:
            elapsed_ms = (time.perf_counter() - self._current_start) * 1000
            self.stages.append(StageResult(
                name=self._current_name,
                time_ms=elapsed_ms,
                token_usage=token_usage
            ))
            self._current_start = None
            self._current_name = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Return timing and token summary."""
        total_ms = sum(s.time_ms for s in self.stages)
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        for s in self.stages:
            if s.token_usage:
                total_tokens["prompt_tokens"] += s.token_usage.get("prompt_tokens", 0)
                total_tokens["completion_tokens"] += s.token_usage.get("completion_tokens", 0)
                total_tokens["total_tokens"] += s.token_usage.get("total_tokens", 0)
        
        return {
            "stages": [s.to_dict() for s in self.stages],
            "total_time_ms": round(total_ms, 2),
            "total_tokens": total_tokens if total_tokens["total_tokens"] > 0 else None
        }
    
    def print_summary(self):
        """Print a formatted timing and token summary."""
        print("\n" + "=" * 70)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 70)
        
        total = sum(s.time_ms for s in self.stages)
        total_prompt = 0
        total_completion = 0
        
        for stage in self.stages:
            pct = (stage.time_ms / total * 100) if total > 0 else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            
            # Format tokens if available
            token_str = ""
            if stage.token_usage:
                prompt = stage.token_usage.get("prompt_tokens", 0)
                completion = stage.token_usage.get("completion_tokens", 0)
                total_prompt += prompt
                total_completion += completion
                token_str = f" [{prompt}+{completion} tokens]"
            
            print(f"  {stage.name:<30} {stage.time_ms:>8.1f}ms  {bar} {pct:>5.1f}%{token_str}")
        
        print("-" * 70)
        print(f"  {'TOTAL':<30} {total:>8.1f}ms")
        if total_prompt > 0 or total_completion > 0:
            print(f"  {'TOKENS':<30} {total_prompt} prompt + {total_completion} completion = {total_prompt + total_completion} total")
        print("=" * 70)


class CRUDExecutor:
    """
    Main executor for CRUD operations with 3-stage LLM processing.
    
    Pipeline:
    1. Version Resolution (LLM) - determines version selector and CRUD operation
    2. XPath Generation (LLM) - generates tree-traversal query
    3. XPath Execution - runs semantic XPath (non-LLM)
    4. Downstream Handler (LLM) - single-call CRUD-specific processing
    5. Tree Modification (if applicable)
    6. Version Creation (if applicable)
    
    Trees are modified in-place with versions stored as child nodes.
    """
    
    def __init__(
        self,
        scoring_method: str = None,
        top_k: int = None,
        score_threshold: float = None,
        tree_path: Path = None,
        traces_path: Path = None
    ):
        """
        Initialize the CRUD executor.
        
        Args:
            scoring_method: Scoring method for semantic XPath
            top_k: Number of top results to consider
            score_threshold: Minimum score threshold
            tree_path: Optional path to the XML tree override
            traces_path: Optional directory for trace files
        """
        # Determine base directory
        if tree_path:
            base_dir = Path(tree_path).parent
        else:
            base_dir = RESULT_DIR
            
        # Ensure result directory exists
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize query processing components (unchanged)
        self.version_resolver = VersionResolver()
        self.query_generator = XPathQueryGenerator()
        
        # Initialize execution components
        self.executor = DenseXPathExecutor(
            scoring_method=scoring_method,
            top_k=top_k,
            score_threshold=score_threshold,
            tree_path=tree_path,
            traces_path=traces_path
        )
        
        # Initialize downstream handlers (NEW)
        schema = self.executor._schema
        handler_traces_path = traces_path / "reasoning_traces" if traces_path else None
        self.read_handler = ReadHandler(schema=schema, traces_path=handler_traces_path)
        self.delete_handler = DeleteHandler(schema=schema, traces_path=handler_traces_path)
        self.update_handler = UpdateHandler(schema=schema, traces_path=handler_traces_path)
        self.create_handler = CreateHandler(schema=schema, traces_path=handler_traces_path)
        
        # Tree modification components (unchanged)
        self.version_manager = VersionManager(base_directory=base_dir)
        
        # Store reference to tree for modifications
        self._tree = None
    
    @property
    def tree(self) -> ET.ElementTree:
        """Get the current tree (loads from executor if needed)."""
        if self._tree is None:
            self._tree = copy.deepcopy(self.executor.tree)
        return self._tree
    
    def _sync_executor_tree(self):
        """Sync the DenseXPathExecutor's tree with our modified tree."""
        self.executor._tree = self._tree
        self.executor._root = self._tree.getroot()
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Execute a CRUD operation based on the user's query.
        
        Pipeline:
        1. Version Resolution (LLM)
        2. XPath Generation (LLM)
        3. XPath Execution (non-LLM)
        4. Downstream Task Handler (LLM)
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            Dict with operation results, traces, timing info, and token usage
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        timer = PipelineTimer()
        
        # Stage 1: Version Resolution (LLM Call 1)
        timer.start("version_resolution")
        version_result = self.version_resolver.resolve(user_query)
        timer.stop(token_usage=version_result.token_usage)
        
        logger.info(f"Version resolved: {version_result.get_version_selector_string()}, {version_result.crud_operation.value}")
        print(f"\n🔍 Version: {version_result.get_version_selector_string()}")
        print(f"📋 Operation: {version_result.crud_operation.value}")
        
        # Version Lookup (non-LLM)
        timer.start("version_lookup")
        target_version = self._resolve_version_element(version_result)
        timer.stop()
        
        if target_version is None:
            return {
                "success": False,
                "error": "No version found in tree",
                "timestamp": timestamp,
                "user_query": user_query,
                "version_resolution": version_result.to_dict(),
                "timing": timer.to_dict()
            }
        
        version_number = target_version.get("number", "?")
        logger.info(f"Operating on version {version_number}")
        print(f"📁 Target version: {version_number}")
        
        # Stage 2: XPath Generation (LLM Call 2)
        timer.start("query_generation")
        parsed_query = self.query_generator.generate_and_parse(
            user_query, 
            version_result.crud_operation
        )
        timer.stop(token_usage=parsed_query.token_usage)
        
        logger.info(f"Generated XPath: {parsed_query.xpath}")
        print(f"🛤️  XPath: {parsed_query.xpath}")
        
        # Stage 3: XPath Execution (non-LLM)
        timer.start("xpath_execution")
        xpath_query = self._build_version_xpath(parsed_query.xpath, target_version)
        execution_result = self.executor.execute(xpath_query)
        timer.stop(token_usage=execution_result.token_usage)
        
        # Get retrieved nodes as dicts
        retrieved_nodes = [m.to_dict() for m in execution_result.matched_nodes]
        print(f"🔎 Retrieved {len(retrieved_nodes)} candidate nodes")
        
        # Stage 4: Downstream Task Handler (LLM Call 3)
        timer.start("downstream_task")
        
        if version_result.crud_operation == CRUDOperation.READ:
            handler_result = self._execute_read(user_query, retrieved_nodes, parsed_query)
        elif version_result.crud_operation == CRUDOperation.DELETE:
            handler_result = self._execute_delete(user_query, retrieved_nodes, parsed_query, target_version)
        elif version_result.crud_operation == CRUDOperation.UPDATE:
            handler_result = self._execute_update(user_query, retrieved_nodes, parsed_query, target_version)
        elif version_result.crud_operation == CRUDOperation.CREATE:
            handler_result = self._execute_create(user_query, retrieved_nodes, parsed_query, target_version)
        else:
            handler_result = HandlerResult(
                success=False,
                operation="UNKNOWN",
                error=f"Unknown operation: {version_result.crud_operation}"
            )
        
        # Record token usage from handler
        token_usage = handler_result.token_usage.to_dict() if handler_result.token_usage else None
        timer.stop(token_usage=token_usage)
        
        # Build result
        result = {
            "timestamp": timestamp,
            "user_query": user_query,
            "operation": handler_result.operation,
            "success": handler_result.success,
            "version_resolution": version_result.to_dict(),
            "parsed_query": parsed_query.to_dict(),
            "version_used": version_number,
            "xpath_execution": {
                "query": execution_result.query,
                "matched_count": len(execution_result.matched_nodes),
                "execution_time_ms": execution_result.execution_time_ms,
                "token_usage": execution_result.token_usage
            },
            "handler_result": handler_result.to_dict(),
            "timing": timer.to_dict()
        }
        
        # Flatten operation-specific fields to top level for backward compatibility
        self._flatten_handler_result(result, handler_result, retrieved_nodes)
        
        if handler_result.error:
            result["error"] = handler_result.error
        
        # Print timing summary
        timer.print_summary()
        
        return result
    
    def _flatten_handler_result(
        self,
        result: Dict[str, Any],
        handler_result: HandlerResult,
        retrieved_nodes: List[Dict[str, Any]]
    ):
        """
        Flatten handler result fields to top level for backward compatibility.
        
        This ensures the result dict has the same structure as the old system,
        so TraceWriter and other consumers can find the expected fields.
        """
        if not handler_result.output:
            return
        
        operation = handler_result.operation
        output = handler_result.output
        
        if operation == "READ":
            # Flatten ReadResult fields
            selected_nodes = []
            if hasattr(output, 'selected_nodes'):
                for node in output.selected_nodes:
                    selected_nodes.append({
                        **node.node_data,
                        "tree_path": node.tree_path,
                        "reasoning": node.reasoning
                    })
            
            result["candidates_count"] = len(retrieved_nodes)
            result["selected_count"] = len(selected_nodes)
            result["selected_nodes"] = selected_nodes
            
        elif operation == "DELETE":
            # Flatten DeleteResult fields
            result["deleted_count"] = len(output.nodes_to_delete) if hasattr(output, 'nodes_to_delete') else 0
            result["deleted_paths"] = output.nodes_to_delete if hasattr(output, 'nodes_to_delete') else []
            
        elif operation == "UPDATE":
            # Flatten UpdateResult fields
            updated_paths = []
            update_results = []
            if hasattr(output, 'updates'):
                for update in output.updates:
                    updated_paths.append(update.tree_path)
                    update_results.append({
                        "path": update.tree_path,
                        "changes": update.changes,
                        "success": True
                    })
            
            result["updated_count"] = len(updated_paths)
            result["updated_paths"] = updated_paths
            result["update_results"] = update_results
            
        elif operation == "CREATE":
            # Flatten CreateResult fields
            result["created_path"] = f"{output.parent_path}/{output.node_type}" if output.parent_path else None
            result["insertion_point"] = {
                "parent_path": output.parent_path,
                "position": output.position,
                "reasoning": output.reasoning
            }
            result["content_result"] = {
                "success": output.created_content is not None,
                "node_type": output.node_type,
                "fields": output.fields
            }
    
    def _resolve_version_element(self, version_result: ResolvedVersion) -> Optional[ET.Element]:
        """Resolve the actual version element from the version resolution result."""
        if version_result.semantic_query:
            matched_version = self.version_manager.get_version_by_semantic(
                self.tree,
                version_result.semantic_query,
                scorer=self.executor.scorer
            )
        else:
            matched_version = self.version_manager.get_version_by_number(
                self.tree,
                version_result.index
            )
        
        if version_result.selector_type == VersionSelector.BEFORE and matched_version is not None:
            return self.version_manager.get_previous_version(self.tree, matched_version)
        
        return matched_version
    
    def _execute_read(
        self,
        user_query: str,
        retrieved_nodes: List[Dict[str, Any]],
        parsed_query: ParsedQuery
    ) -> HandlerResult:
        """Execute a READ operation using the ReadHandler."""
        return self.read_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={"parsed_query": parsed_query.to_dict()}
        )
    
    def _execute_delete(
        self,
        user_query: str,
        retrieved_nodes: List[Dict[str, Any]],
        parsed_query: ParsedQuery,
        target_version: ET.Element
    ) -> HandlerResult:
        """Execute a DELETE operation using the DeleteHandler."""
        # Get handler decision
        handler_result = self.delete_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={"parsed_query": parsed_query.to_dict()}
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        delete_result = handler_result.output
        nodes_to_delete = delete_result.nodes_to_delete
        
        if not nodes_to_delete:
            handler_result.success = False
            handler_result.error = "No nodes selected for deletion"
            return handler_result
        
        # Apply tree modifications
        new_version_content = self._copy_version_content(target_version)
        deleted_paths = []
        
        for tree_path in nodes_to_delete:
            relative_path = self._adjust_path_for_version(tree_path, target_version)
            if self._delete_from_content(new_version_content, relative_path):
                deleted_paths.append(tree_path)
        
        # Create new version
        if deleted_paths:
            patch_info = f"Deleted: {', '.join(deleted_paths)}"
            self.version_manager.create_new_version(
                self.tree,
                target_version,
                patch_info=patch_info,
                conversation_history=user_query,
                modified_content=new_version_content
            )
            
            self.version_manager.save_tree(self.tree, self.executor.memory_path)
            self._sync_executor_tree()
        
        # Update result with actual deletions
        handler_result.output.nodes_to_delete = deleted_paths
        return handler_result
    
    def _execute_update(
        self,
        user_query: str,
        retrieved_nodes: List[Dict[str, Any]],
        parsed_query: ParsedQuery,
        target_version: ET.Element
    ) -> HandlerResult:
        """Execute an UPDATE operation using the UpdateHandler."""
        # Get handler decision with updates
        handler_result = self.update_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={
                "parsed_query": parsed_query.to_dict(),
                "update_info": parsed_query.update_info
            }
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        update_result = handler_result.output
        updates = update_result.updates
        
        if not updates:
            handler_result.success = False
            handler_result.error = "No nodes selected for update"
            return handler_result
        
        # Apply tree modifications
        new_version_content = self._copy_version_content(target_version)
        updated_paths = []
        
        for update_item in updates:
            relative_path = self._adjust_path_for_version(update_item.tree_path, target_version)
            if self._replace_in_content(new_version_content, relative_path, update_item.updated_content):
                updated_paths.append(update_item.tree_path)
        
        # Create new version
        if updated_paths:
            patch_info = f"Updated: {', '.join(updated_paths)}"
            self.version_manager.create_new_version(
                self.tree,
                target_version,
                patch_info=patch_info,
                conversation_history=user_query,
                modified_content=new_version_content
            )
            
            self.version_manager.save_tree(self.tree, self.executor.memory_path)
            self._sync_executor_tree()
        
        return handler_result
    
    def _execute_create(
        self,
        user_query: str,
        retrieved_nodes: List[Dict[str, Any]],
        parsed_query: ParsedQuery,
        target_version: ET.Element
    ) -> HandlerResult:
        """Execute a CREATE operation using the CreateHandler."""
        # Extract create info from parsed query
        create_info = {}
        if parsed_query.create_info:
            parent_path, node_type, description = parsed_query.create_info
            create_info = {
                "parent_path": parent_path,
                "node_type": node_type,
                "description": description
            }
        
        # Get handler decision with created content
        handler_result = self.create_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={
                "parsed_query": parsed_query.to_dict(),
                "create_info": create_info
            }
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        create_result = handler_result.output
        
        if not create_result.created_content:
            handler_result.success = False
            handler_result.error = "Content generation failed"
            return handler_result
        
        # Apply tree modification
        new_version_content = self._copy_version_content(target_version)
        relative_parent_path = self._adjust_path_for_version(create_result.parent_path, target_version)
        
        insert_success = self._insert_in_content(
            new_version_content,
            relative_parent_path,
            create_result.created_content,
            create_result.position
        )
        
        if not insert_success:
            handler_result.success = False
            handler_result.error = f"Failed to insert at {create_result.parent_path}"
            return handler_result
        
        # Create new version
        created_path = f"{create_result.parent_path}/{create_result.node_type}"
        patch_info = f"Created: {created_path}"
        self.version_manager.create_new_version(
            self.tree,
            target_version,
            patch_info=patch_info,
            conversation_history=user_query,
            modified_content=new_version_content
        )
        
        self.version_manager.save_tree(self.tree, self.executor.memory_path)
        self._sync_executor_tree()
        
        return handler_result
    
    # =========================================================================
    # Tree manipulation utilities (unchanged from original)
    # =========================================================================
    
    def _build_version_xpath(self, xpath: str, version: ET.Element) -> str:
        """Build an xpath query that targets the specific version.
        
        Handles both regular paths and global index queries:
        - Regular: /Itinerary/Day/POI -> /Root/Itinerary_Version[@number='1']/Itinerary/Day/POI
        - Global: (/Itinerary/Day/POI)[1] -> (/Root/Itinerary_Version[@number='1']/Itinerary/Day/POI)[1]
        """
        import re
        
        version_number = version.get("number", "1")
        version_prefix = f"/Root/Itinerary_Version[@number='{version_number}']/Itinerary"
        
        # Handle global index queries: (/path)[index] -> (/version_prefix/path)[index]
        # Pattern matches (/...)[N] or (/...)[N:M] or (/...)[-N:] etc.
        global_index_match = re.match(r'^\((.+)\)(\[.+\])$', xpath)
        if global_index_match:
            inner_path = global_index_match.group(1)
            global_index = global_index_match.group(2)
            
            # Transform the inner path
            if inner_path.startswith("/Itinerary"):
                inner_path = inner_path[len("/Itinerary"):]
            elif not inner_path.startswith("/"):
                inner_path = "/" + inner_path
                
            return f"({version_prefix}{inner_path}){global_index}"
        
        # Regular queries
        if xpath.startswith("/Itinerary"):
            remaining = xpath[len("/Itinerary"):]
            return f"{version_prefix}{remaining}"
        
        if not xpath.startswith("/"):
            xpath = "/" + xpath
        
        return f"{version_prefix}{xpath}"
    
    def _copy_version_content(self, version: ET.Element) -> List[ET.Element]:
        """Create a deep copy of the content nodes from a version."""
        itinerary = version.find("Itinerary")
        if itinerary is not None:
            return [copy.deepcopy(child) for child in itinerary]
        
        return [
            copy.deepcopy(child) 
            for child in version 
            if child.tag not in ("patch_info", "conversation_history", "Itinerary")
        ]
    
    def _adjust_path_for_version(self, tree_path: str, version: ET.Element) -> str:
        """Adjust a tree path to be relative to version content."""
        parts = [p.strip() for p in tree_path.split(">")]
        
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
        """Find a node within the content list by relative path."""
        if not relative_path:
            return None
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        first_part = parts[0]
        current = self._find_element_by_part(content, first_part)
        
        if current is None:
            return None
        
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
        """Find an element in a list by a path part."""
        words = part.split()
        
        # Case 1: Indexed notation like "Day 1" or "POI 2"
        if len(words) == 2 and words[1].isdigit():
            node_type = words[0]
            index = int(words[1])
            
            for elem in elements:
                if elem.tag == node_type:
                    elem_index = elem.get("index") or elem.get("number")
                    if elem_index == str(index):
                        return elem
            
            matching = [e for e in elements if e.tag == node_type]
            if 0 < index <= len(matching):
                return matching[index - 1]
            
            return None
        
        # Case 2: Try direct tag match
        for elem in elements:
            if elem.tag == part:
                return elem
        
        # Case 3: Try name-based match
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
        """Delete a node from the content list."""
        if not relative_path:
            return False
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        if len(parts) == 1:
            old_elem = self._find_element_by_part(content, parts[0])
            if old_elem is not None:
                content.remove(old_elem)
                return True
            return False
        
        parent_path = " > ".join(parts[:-1])
        parent = self._find_node_in_content(content, parent_path)
        
        if parent is None:
            return False
        
        child_part = parts[-1]
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
        """Replace a node in the content list."""
        if not relative_path:
            return False
        
        parts = [p.strip() for p in relative_path.split(">")]
        
        if len(parts) == 1:
            old_elem = self._find_element_by_part(content, parts[0])
            if old_elem is not None:
                idx = content.index(old_elem)
                content[idx] = new_element
                return True
            return False
        
        parent_path = " > ".join(parts[:-1])
        parent = self._find_node_in_content(content, parent_path)
        
        if parent is None:
            return False
        
        child_part = parts[-1]
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
        """Insert a new node into the content."""
        if not relative_parent_path:
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
