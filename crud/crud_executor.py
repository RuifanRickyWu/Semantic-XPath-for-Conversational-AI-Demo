"""
CRUD Executor - Orchestrates the full CRUD pipeline for each operation type.

Coordinates:
- Intent classification
- Semantic XPath query generation and execution
- LLM reasoning for node selection
- Tree modifications (for Create, Update, Delete)
- Content generation (for Create, Update)
- Version management

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

from intent_classifier import IntentClassifier, IntentType, ClassifiedIntent
from xpath_query_generation import XPathQueryGenerator
from dense_xpath import DenseXPathExecutor
from reasoner import NodeReasoner, InsertionReasoner, BatchReasoningResult
from tree_modification import NodeDeleter, NodeInserter, VersionManager, OperationResult
from content_creator import NodeCreator, NodeUpdater, ContentGenerationResult, ContentUpdateResult


logger = logging.getLogger(__name__)

# Result directory for modified trees
RESULT_DIR = Path(__file__).parent.parent / "result"


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
        print("-" * 45)
        for step in self.steps:
            pct = (step["time_ms"] / sum(s["time_ms"] for s in self.steps) * 100) if self.steps else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {step['step']:<25} {step['time_ms']:>8.1f}ms  {bar} {pct:>5.1f}%")
        print("-" * 45)
        print(f"  {'TOTAL':<25} {sum(s['time_ms'] for s in self.steps):>8.1f}ms")


class CRUDExecutor:
    """
    Main executor for CRUD operations.
    
    Orchestrates the full pipeline:
    1. Intent Classification
    2. XPath Query Generation
    3. Semantic XPath Execution
    4. LLM Reasoning
    5. Tree Modification (if applicable)
    6. Version Management
    
    Modified trees are saved to the 'result' folder.
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
        
        # Initialize components
        self.intent_classifier = IntentClassifier()
        self.query_generator = XPathQueryGenerator()
        self.executor = DenseXPathExecutor(
            scoring_method=scoring_method,
            top_k=top_k,
            score_threshold=score_threshold
        )
        self.node_reasoner = NodeReasoner()
        self.insertion_reasoner = InsertionReasoner()
        self.node_deleter = NodeDeleter()
        self.node_inserter = NodeInserter()
        # Store modified trees in result directory
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
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Execute a CRUD operation based on the user's query.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            Dict with operation results, traces, timing info, and modified tree info
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        timer = StepTimer()
        
        # Step 1: Classify intent
        timer.start("Intent Classification")
        intent = self.intent_classifier.classify(user_query)
        timer.stop()
        logger.info(f"Classified intent: {intent.intent.value}")
        
        # Step 2: Generate XPath query
        timer.start("XPath Generation")
        xpath_query = self.query_generator.generate(intent.xpath_hint)
        timer.stop()
        
        # Format full query with operation
        full_query = intent.format_full_query(xpath_query)
        print(f"\n📋 {full_query}")
        
        # Step 3: Execute based on operation type
        if intent.intent == IntentType.READ:
            result = self._execute_read(user_query, xpath_query, intent, timer)
        elif intent.intent == IntentType.DELETE:
            result = self._execute_delete(user_query, xpath_query, intent, timer)
        elif intent.intent == IntentType.UPDATE:
            result = self._execute_update(user_query, xpath_query, intent, timer)
        elif intent.intent == IntentType.CREATE:
            result = self._execute_create(user_query, xpath_query, intent, timer)
        else:
            result = {"error": f"Unknown intent: {intent.intent}"}
        
        # Add common fields
        result["timestamp"] = timestamp
        result["user_query"] = user_query
        result["intent"] = intent.to_dict()
        result["xpath_query"] = xpath_query
        result["full_query"] = full_query
        result["timing"] = timer.to_dict()
        
        # Print timing summary
        timer.print_summary()
        
        return result
    
    def _execute_read(
        self,
        user_query: str,
        xpath_query: str,
        intent: ClassifiedIntent,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a READ operation."""
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
        
        # Get final selected nodes
        selected = [r.node_data for r in reasoning_result.selected_nodes]
        
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
        xpath_query: str,
        intent: ClassifiedIntent,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a DELETE operation."""
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
        
        # Delete selected nodes
        timer.start("Tree Modification")
        tree = self.tree
        deletion_results = []
        deleted_paths = []
        
        for node_result in reasoning_result.selected_nodes:
            tree_path = node_result.node_path
            result = self.node_deleter.delete_node(tree, tree_path)
            deletion_results.append(result.to_dict())
            
            if result.success:
                deleted_paths.append(tree_path)
        timer.stop()
        
        # Save new version
        timer.start("Save Version")
        version_info = None
        if deleted_paths:
            version_info = self.version_manager.save_version(
                tree,
                self.executor.memory_path,
                operation="DELETE",
                changes={"deleted_nodes": deleted_paths}
            )
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
        xpath_query: str,
        intent: ClassifiedIntent,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute an UPDATE operation."""
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
        
        # Update selected nodes
        tree = self.tree
        update_results = []
        updated_paths = []
        
        for node_result in reasoning_result.selected_nodes:
            tree_path = node_result.node_path
            
            # Find the actual node in the tree
            from tree_modification.base import find_node_by_path
            original_node = find_node_by_path(tree.getroot(), tree_path)
            
            if original_node is None:
                update_results.append({
                    "success": False,
                    "path": tree_path,
                    "error": "Node not found"
                })
                continue
            
            # Generate updated content
            timer.start("LLM Content Update")
            update_content = self.node_updater.update_node(
                user_query,
                original_node,
                intent.operation_details
            )
            timer.stop()
            
            if not update_content.success or update_content.xml_element is None:
                update_results.append({
                    "success": False,
                    "path": tree_path,
                    "error": "Content generation failed"
                })
                continue
            
            # Replace the node
            timer.start("Tree Modification")
            replace_result = self.node_inserter.replace_node(
                tree,
                tree_path,
                update_content.xml_element
            )
            timer.stop()
            
            update_results.append({
                "success": replace_result.success,
                "path": tree_path,
                "changes": update_content.to_dict()
            })
            
            if replace_result.success:
                updated_paths.append(tree_path)
        
        # Save new version
        timer.start("Save Version")
        version_info = None
        if updated_paths:
            version_info = self.version_manager.save_version(
                tree,
                self.executor.memory_path,
                operation="UPDATE",
                changes={"updated_nodes": updated_paths}
            )
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
        xpath_query: str,
        intent: ClassifiedIntent,
        timer: StepTimer
    ) -> Dict[str, Any]:
        """Execute a CREATE operation."""
        # Execute semantic XPath to find context
        timer.start("Semantic XPath Execution")
        execution_result = self.executor.execute(xpath_query)
        timer.stop()
        
        # Get parent candidates for insertion
        candidates = [m.to_dict() for m in execution_result.matched_nodes]
        
        # Apply reasoning to find relevant context
        timer.start("LLM Node Reasoning")
        reasoning_result = self.node_reasoner.reason(
            candidates,
            user_query,
            operation="CREATE"
        )
        timer.stop()
        
        # Determine parent candidates (use selected or all)
        parent_candidates = [r.to_dict() for r in reasoning_result.selected_nodes] if reasoning_result.selected_nodes else candidates
        
        if not parent_candidates:
            # Fallback: use root's children
            parent_candidates = [{
                "tree_path": self.executor.root.tag,
                "node": {"type": self.executor.root.tag},
                "children": [{"type": c.tag} for c in self.executor.root]
            }]
        
        # Find best insertion point
        timer.start("LLM Insertion Reasoning")
        insertion_point = self.insertion_reasoner.find_insertion_point(
            user_query,
            parent_candidates,
            intent.operation_details
        )
        timer.stop()
        
        # Determine node type to create
        node_type = self._infer_node_type(intent.operation_details)
        
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
            intent.operation_details
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
        
        # Insert the new node
        timer.start("Tree Modification")
        tree = self.tree
        insert_result = self.node_inserter.insert_node(
            tree,
            insertion_point.parent_path,
            content_result.xml_element,
            insertion_point.position
        )
        timer.stop()
        
        # Save new version
        timer.start("Save Version")
        version_info = None
        if insert_result.success:
            version_info = self.version_manager.save_version(
                tree,
                self.executor.memory_path,
                operation="CREATE",
                changes={
                    "created_node": insert_result.node_path,
                    "parent_path": insertion_point.parent_path,
                    "position": insertion_point.position
                }
            )
        timer.stop()
        
        return {
            "operation": "CREATE",
            "success": insert_result.success,
            "created_path": insert_result.node_path if insert_result.success else None,
            "insert_result": insert_result.to_dict(),
            "content_result": content_result.to_dict(),
            "insertion_point": insertion_point.to_dict(),
            "reasoning_trace": reasoning_result.to_dict(),
            "tree_version": version_info.to_dict() if version_info else None
        }
    
    def _infer_node_type(self, operation_details: Dict[str, Any]) -> str:
        """Infer the node type to create based on operation details."""
        new_content = operation_details.get("new_content", "").lower()
        
        # Check for restaurant indicators
        restaurant_keywords = ["restaurant", "cafe", "bistro", "bar", "diner", 
                             "eatery", "food", "dining", "lunch", "dinner", "breakfast"]
        if any(kw in new_content for kw in restaurant_keywords):
            return "Restaurant"
        
        # Default to POI
        return "POI"
    
    def reload_tree(self):
        """Reload the tree from the original file."""
        self._tree = None
        self.executor._tree = None
        self.executor._root = None
