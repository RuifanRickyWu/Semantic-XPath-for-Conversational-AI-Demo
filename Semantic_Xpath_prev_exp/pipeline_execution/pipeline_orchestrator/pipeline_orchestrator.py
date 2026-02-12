"""
Semantic XPath Orchestrator - Orchestrates the full CRUD pipeline with 2-stage query processing.

Pipeline Stages:
1. Global Info Resolution (LLM Call 1): Determines task/version selectors and CRUD operation
2. XPath Generation (LLM Call 2): Generates tree-traversal semantic XPath query
3. XPath Execution: Runs semantic XPath to retrieve candidate nodes
4. Downstream Task (LLM Call 3): Single-LLM handler for CRUD-specific processing

Coordinates:
- Global task/version resolution from in-tree versioning
- Semantic XPath query execution
- CRUD-specific handlers (Read, Delete, Update, Create)
- In-tree version management

Tree modifications are delegated to the CRUD handlers.
Includes stage-by-stage timing and token usage tracking.
"""

import logging
import copy
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_execution.query_generation.xpath_query_generator import XPathQueryGenerator
from pipeline_execution.semantic_xpath_util.schema_loader import load_config
from pipeline_execution.task_version_resolver import GlobalInfoResolver
from pipeline_execution.task_version_resolver.version_selector_model import CRUDOperation
from pipeline_execution.query_generation.semantic_xpath_query_generator_model import ParsedQuery
from pipeline_execution.semantic_xpath_execution.query_display import canonicalize_query
from pipeline_execution.pipeline_orchestrator.orchestrator_models import PipelineTimer
from pipeline_execution.semantic_xpath_execution import DenseXPathExecutor
from utils.tree_modification import VersionManager, copy_version_content
from utils.tree_modification.base import find_node_by_path
from utils.logger.query_orchestrator_logging import PipelineSummaryLogger

from pipeline_execution.crud.read_handler import ReadHandler
from pipeline_execution.crud.delete_handler import DeleteHandler
from pipeline_execution.crud.update_handler import UpdateHandler
from pipeline_execution.crud.create_handler import CreateHandler
from pipeline_execution.crud.base import HandlerResult


logger = logging.getLogger(__name__)


class SemanticXPathOrchestrator:
    """
    Main orchestrator for CRUD operations with 3-stage LLM processing.
    
    Pipeline:
    1. Global Info Resolution (LLM) - determines task/version selectors and CRUD operation
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
        traces_path: Path = None,
        config: dict = None
    ):
        """
        Initialize the CRUD executor.
        
        Args:
            scoring_method: Scoring method for semantic XPath
            top_k: Number of top results to consider
            score_threshold: Minimum score threshold
            tree_path: Optional path to XML tree (uses config default if not provided)
            traces_path: Optional directory for trace files
            config: Optional config dict. If not provided, loads from config.yaml.
        """
        # Persist init settings for task-specific reloads
        if config is None:
            config = load_config()
        self._config = config
        self._traces_path = traces_path
        self._scoring_method = scoring_method
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._tree_path = tree_path

        # Paths for global/task memory resolution
        self._base_dir = Path(__file__).resolve().parents[2]
        self._global_memory_path = self._base_dir / "storage" / "memory" / "global" / "root_task_version.xml"
        self._task_memory_dir = self._base_dir / "storage" / "memory" / "task"
        self._task_schema_dir = self._base_dir / "storage" / "schemas" / "task"

        # Initialize query processing components
        global_schema_path = (self._config or {}).get("global_schema_path")
        task_schema_path = (self._config or {}).get("task_schema_path")
        if task_schema_path:
            candidate = Path(task_schema_path)
            if not (candidate.exists() and candidate.is_file()):
                task_schema_path = None
        self.query_generator = XPathQueryGenerator()
        
        # Initialize execution components (handles tree path resolution from config)
        self.executor = DenseXPathExecutor(
            scoring_method=scoring_method,
            top_k=top_k,
            score_threshold=score_threshold,
            tree_path=tree_path,
            traces_path=traces_path,
            config=config
        )
        
        # Get base directory from executor's resolved tree path
        base_dir = self.executor.memory_path.parent
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize downstream handlers
        schema = self.executor._schema
        handler_traces_path = traces_path / "reasoning_traces" if traces_path else None
        self.read_handler = ReadHandler(schema=schema, traces_path=handler_traces_path)
        self.delete_handler = DeleteHandler(schema=schema, traces_path=handler_traces_path)
        self.update_handler = UpdateHandler(schema=schema, traces_path=handler_traces_path)
        self.create_handler = CreateHandler(schema=schema, traces_path=handler_traces_path)

        # Global info resolver helper
        self._global_info_resolver = GlobalInfoResolver(
            executor=self.executor,
            task_schema_dir=self._task_schema_dir,
            task_memory_dir=self._task_memory_dir,
            global_memory_path=self._global_memory_path,
            traces_path=traces_path,
            schema_name=global_schema_path or "root_task_version",
            client=self.read_handler.client,
        )
        self._global_info_resolver.query_generator = self.query_generator
        self._global_info_resolver.read_handler = self.read_handler
        self._global_info_resolver.delete_handler = self.delete_handler
        self._global_info_resolver.update_handler = self.update_handler
        self._global_info_resolver.create_handler = self.create_handler
        
        # Tree modification components
        self.version_manager = VersionManager(
            base_directory=base_dir,
            schema_name=self.executor.schema_name
        )
        
        # Store reference to tree for modifications
        self._tree = None
        self._current_task_number = None
    
    @property
    def tree(self) -> ET.ElementTree:
        """Get the current tree (loads from executor if needed)."""
        if self._tree is None:
            self._tree = copy.deepcopy(self.executor.tree)
        return self._tree
    
    @property
    def tree_path(self) -> Path:
        """Get the path to the tree file."""
        return self.executor.memory_path
    
    def _sync_executor_tree(self):
        """Sync the DenseXPathExecutor's tree with our modified tree."""
        self.executor._tree = self._tree
        self.executor._root = self._tree.getroot()


    # State-change detection is handled by the global info resolver (LLM classifier).

    def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Execute a CRUD operation based on the user's query.
        
        Pipeline:
        1. Global Info Resolution (LLM)
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

        # Ensure resolver and executor operate on the in-memory tree for this session
        self._global_info_resolver.set_tree(self.tree)
        self._sync_executor_tree()
        
        # Stage 1: Global Info Resolution (LLM Call 1)
        timer.start("version_resolution")
        version_result = self._global_info_resolver.resolve(user_query)
        timer.stop(token_usage=version_result.token_usage)
        
        logger.info(
            f"Task resolved: {version_result.get_task_selector_string()}, "
            f"Version resolved: {version_result.get_version_selector_string()}, "
            f"{version_result.crud_operation.value}"
        )

        # Apply state defaults if user did not specify task/version
        self._global_info_resolver.apply_state_defaults(version_result)
        
        # Version Lookup (non-LLM)
        timer.start("version_lookup")
        task_elem, task_number_resolved, target_version_number = self._global_info_resolver.resolve_task_version_elements(version_result)
        timer.stop()

        if task_elem is None or target_version_number is None:
            return {
                "success": False,
                "error": "No version found in tree",
                "timestamp": timestamp,
                "user_query": user_query,
                "version_resolution": version_result.to_dict(),
                "timing": timer.to_dict()
            }

        target_version = None
        for child in list(task_elem):
            if child.tag == "Version" and child.get("number") == str(target_version_number):
                target_version = child
                break
        if target_version is None:
            return {
                "success": False,
                "error": "No version found in tree",
                "timestamp": timestamp,
                "user_query": user_query,
                "version_resolution": version_result.to_dict(),
                "timing": timer.to_dict()
            }

        # Resolve task context from global memory (if available)
        task_context = self._global_info_resolver.resolve_task_context(version_result)
        if task_context or task_number_resolved is not None:
            self._global_info_resolver.apply_task_schema(
                (task_context or {}).get("schema_name"),
                task_number_resolved,
            )

        # State-change only request (from classifier)
        if version_result.crud_operation == CRUDOperation.STATE:
            self._global_info_resolver.update_state(task_number_resolved, target_version_number)
            state_task, state_version = self._global_info_resolver.get_state()
            print(f"🧭 State: task={state_task} version={state_version}")
            version_number = str(target_version_number) if target_version_number is not None else "?"
            task_number = str(task_number_resolved) if task_number_resolved is not None else task_elem.get("number", "?")
            task_title = (task_elem.findtext("title") or "").strip()
            task_desc = (task_elem.findtext("description") or "").strip()
            label = task_title if task_title else f"task {task_number}"
            detail = f" ({task_desc})" if task_desc else ""
            version_desc = (target_version.findtext("description") or "").strip()
            # LLM-generated user-facing response
            prompt = (
                "You are a helpful assistant. Generate a clear, concise user-facing response "
                "confirming a context switch. Include only necessary information. "
                "If the user explicitly switched versions, do not mention the task name unless needed. "
                "Use the provided task and version description to make the response fluent and natural.\n\n"
                f"Task: {label}{detail}\n"
                f"Version description: {version_desc}\n"
            )
            try:
                llm_result = self._global_info_resolver.read_handler.client.complete_with_usage(
                    "Generate the response.",
                    system_prompt=prompt,
                    temperature=0.2,
                    max_tokens=200,
                )
                user_facing = (llm_result.content or "").strip() or f"Context updated. Now working on {label}{detail}."
            except Exception:
                user_facing = f"Context updated. Now working on {label}{detail}."
            return {
                "timestamp": timestamp,
                "user_query": user_query,
                "operation": "STATE",
                "success": True,
                "user_facing": user_facing,
                "version_used": version_number,
                "version_resolution": version_result.to_dict(),
                "timing": timer.to_dict(),
            }
        
        version_number = str(target_version_number) if target_version_number is not None else "?"
        task_number = str(task_number_resolved) if task_number_resolved is not None else task_elem.get("number", "?")
        logger.info(f"Operating on task {task_number}, version {version_number}")
        print(f"📁 Target task: {task_number}")
        print(f"📁 Target version: {version_number}")

        # Track current task for version creation
        self._current_task = task_elem
        self._current_task_number = task_number_resolved
        self._global_info_resolver.update_state(task_number_resolved, target_version_number)
        state_task, state_version = self._global_info_resolver.get_state()
        print(f"🧭 State: task={state_task} version={state_version}")
        
        # Stage 2: XPath Generation (LLM Call 2)
        # Use task_query (version-stripped query) for xpath generation
        # This prevents the xpath generator from trying to handle version selection
        task_query = version_result.task_query or user_query
        if task_query != user_query:
            print(f"📝 Task query: {task_query}")
        
        timer.start("query_generation")
        task_schema_path = self._global_info_resolver.build_task_schema_path(
            (task_context or {}).get("schema_name")
        )
        print(f"task schema path: {task_schema_path}")
        parsed_query = self.query_generator.generate_and_parse(
            task_query,
            version_result.crud_operation,
            schema_name=task_schema_path,
        )
        timer.stop(token_usage=parsed_query.token_usage)
        
        canonical_generated_xpath = canonicalize_query(parsed_query.xpath)
        logger.info(f"Generated XPath (canonical): {canonical_generated_xpath}")
        
        # Stage 3: XPath Execution (non-LLM)
        timer.start("xpath_execution")
        xpath_query = self._build_task_version_xpath(parsed_query.xpath, task_elem, target_version)
        canonical_full_xpath = canonicalize_query(xpath_query)
        print(f"🛤️  XPath: {canonical_full_xpath}")
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
        canonical_xpath_query = canonicalize_query(execution_result.query)
        canonical_full_query = f"{handler_result.operation}({canonical_xpath_query})"

        result = {
            "timestamp": timestamp,
            "user_query": user_query,
            "task_query": task_query,  # Version-stripped query used for xpath generation
            "operation": handler_result.operation,
            "success": handler_result.success,
            "user_facing": handler_result.user_facing,
            "version_resolution": version_result.to_dict(),
            "parsed_query": parsed_query.to_dict(),
            "version_used": version_number,
            "xpath_execution": {
                "query": execution_result.query,
                "canonical_query": canonical_xpath_query,
                "matched_count": len(execution_result.matched_nodes),
                "execution_time_ms": execution_result.execution_time_ms,
                "token_usage": execution_result.token_usage
            },
            "handler_result": handler_result.to_dict(),
            "timing": timer.to_dict(),
            # Include visualization data from execution result
            "xpath_query": execution_result.query,
            "full_query": f"{handler_result.operation}({execution_result.query})",
            "canonical_xpath_query": canonical_xpath_query,
            "canonical_full_query": canonical_full_query,
            "traversal_steps": execution_result.traversal_steps,
            "score_fusion_trace": execution_result.score_fusion_trace,
            "final_filtering_trace": execution_result.final_filtering_trace,
            "demo_logger_trace": execution_result.demo_logger_trace,
        }
        
        # Flatten operation-specific fields to top level for backward compatibility
        self._flatten_handler_result(result, handler_result, retrieved_nodes)
        
        if handler_result.error:
            result["error"] = handler_result.error
        
        # Print timing summary
        PipelineSummaryLogger.print_summary(timer)
        
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

        if handler_result.user_facing:
            result["user_facing"] = handler_result.user_facing
        
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
    
    def _execute_read(
        self,
        user_query: str,
        retrieved_nodes: List[Dict[str, Any]],
        parsed_query: ParsedQuery
    ) -> HandlerResult:
        """Execute a READ operation using the ReadHandler."""
        return self._global_info_resolver.read_handler.process(
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
        handler_result = self._global_info_resolver.delete_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={"parsed_query": parsed_query.to_dict()}
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        if not handler_result.output.nodes_to_delete:
            handler_result.success = False
            handler_result.error = "No nodes selected for deletion"
            return handler_result
        
        # Apply tree modifications via handler
        version_content = copy_version_content(target_version)
        mod_result = self._global_info_resolver.delete_handler.apply_to_content(
            handler_result, version_content, target_version
        )
        
        if not mod_result.success:
            handler_result.success = False
            handler_result.error = mod_result.error
            return handler_result
        
        # Create new version
        patch_info = self._build_patch_info(handler_result, mod_result, user_query)
        self._create_new_version(
            target_version,
            mod_result.modified_content,
            patch_info,
            user_query
        )
        
        # Update result with actual deletions
        handler_result.output.nodes_to_delete = mod_result.affected_paths
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
        handler_result = self._global_info_resolver.update_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={
                "parsed_query": parsed_query.to_dict(),
                "update_info": parsed_query.update_info
            }
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        if not handler_result.output.updates:
            handler_result.success = False
            handler_result.error = "No nodes selected for update"
            return handler_result
        
        # Apply tree modifications via handler
        version_content = copy_version_content(target_version)
        mod_result = self._global_info_resolver.update_handler.apply_to_content(
            handler_result, version_content, target_version
        )
        
        if not mod_result.success:
            handler_result.success = False
            handler_result.error = mod_result.error
            return handler_result
        
        # Create new version
        patch_info = self._build_patch_info(handler_result, mod_result, user_query)
        self._create_new_version(
            target_version,
            mod_result.modified_content,
            patch_info,
            user_query
        )
        
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
        handler_result = self._global_info_resolver.create_handler.process(
            user_query,
            retrieved_nodes,
            operation_context={
                "parsed_query": parsed_query.to_dict(),
                "create_info": create_info
            }
        )
        
        if not handler_result.success or not handler_result.output:
            return handler_result
        
        if not handler_result.output.created_content:
            handler_result.success = False
            handler_result.error = "Content generation failed"
            return handler_result
        
        # Apply tree modification via handler
        version_content = copy_version_content(target_version)
        mod_result = self._global_info_resolver.create_handler.apply_to_content(
            handler_result, version_content, target_version
        )
        
        if not mod_result.success:
            handler_result.success = False
            handler_result.error = mod_result.error
            return handler_result
        
        # Create new version
        patch_info = self._build_patch_info(handler_result, mod_result, user_query)
        self._create_new_version(
            target_version,
            mod_result.modified_content,
            patch_info,
            user_query
        )
        
        return handler_result
    
    def _create_new_version(
        self,
        source_version: ET.Element,
        modified_content: List[ET.Element],
        patch_info: str,
        user_query: str
    ):
        """
        Create a new version and save the tree.
        
        Args:
            source_version: The source version element
            modified_content: The modified content elements
            patch_info: Description of changes
            user_query: The user's original request
        """
        task_elem = None
        if self._current_task_number is not None:
            task_elem = self._find_task_in_tree(self._current_task_number)
        if task_elem is None:
            task_elem = getattr(self, "_current_task", None)
        if task_elem is None:
            return

        versions = [c for c in list(task_elem) if c.tag == "Version"]
        new_number = len(versions) + 1

        new_version = ET.SubElement(task_elem, "Version")
        new_version.set("number", str(new_number))
        ET.SubElement(new_version, "description").text = patch_info

        for elem in modified_content:
            new_version.append(copy.deepcopy(elem))

        try:
            tree_xml = ET.tostring(self.tree.getroot(), encoding="unicode")
            print("🌳 Full tree content:")
            print(tree_xml)
            print(f"Full memory path: {self.executor.memory_path}")
        except Exception as exc:
            print(f"⚠️ Failed to serialize full tree for preview: {exc}")

        self._sync_task_schema(task_elem, new_version)
        
        self.version_manager.save_tree(self.tree, self.executor.memory_path)
        self._sync_executor_tree()

    def _find_task_in_tree(self, task_number: int) -> Optional[ET.Element]:
        """Find the task element by number in the in-memory tree."""
        if task_number is None:
            return None
        root = self.tree.getroot()
        for child in list(root):
            if child.tag == "Task" and child.get("number") == str(task_number):
                return child
        return None

    def _build_patch_info(self, handler_result: HandlerResult, mod_result: Any, user_query: str) -> str:
        """Build a concise, meaningful description of changes."""
        query = (user_query or "").strip()
        if query:
            return self._rewrite_patch_info(query)
        if handler_result and handler_result.user_facing:
            return handler_result.user_facing.strip()
        return getattr(mod_result, "patch_info", "") or "Updated content"

    def _rewrite_patch_info(self, user_query: str) -> str:
        """Rewrite user query into a short, natural language version description."""
        if not user_query:
            return "Updated content"
        try:
            client = self._global_info_resolver.read_handler.client
        except Exception:
            return user_query
        if client is None:
            return user_query

        prompt = (
            "Rewrite the user's request into a short, natural description of the change "
            "for a version label. Keep it concise (<= 12 words), action-oriented, "
            "and without quotes or extra punctuation. Do not add new details.\n\n"
            f"User request: {user_query}\n"
            "Description:"
        )
        try:
            result = client.complete_with_usage(
                "Generate the description.",
                system_prompt=prompt,
                temperature=0.2,
                max_tokens=60,
            )
            text = (result.content or "").strip()
            return text or user_query
        except Exception:
            return user_query

    def _sync_task_schema(self, task_elem: ET.Element, version_elem: ET.Element) -> None:
        """Update task schema file when node types are added/removed."""
        task_name = (task_elem.get("name") or "").strip()
        if not task_name:
            return
        schema_path = self._task_schema_dir / f"{task_name}.yaml"
        if not schema_path.exists():
            return

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f) or {}
        except Exception:
            return

        nodes = schema.get("nodes", {}) or {}

        def _is_structural(tag: str) -> bool:
            return bool(tag) and tag[0].isupper()

        # Build node info from version content
        node_info: Dict[str, Dict[str, Any]] = {}

        def _visit(elem: ET.Element):
            tag = elem.tag
            if not _is_structural(tag):
                return
            info = node_info.setdefault(tag, {"children": set(), "fields": set(), "attrs": set()})
            for child in list(elem):
                if _is_structural(child.tag):
                    info["children"].add(child.tag)
                else:
                    info["fields"].add(child.tag)
            for attr in elem.attrib:
                info["attrs"].add(attr)
            for child in list(elem):
                _visit(child)

        # Root children are the content under the version element
        for child in list(version_elem):
            _visit(child)

        if not node_info:
            return

        # Update nodes
        updated_nodes: Dict[str, Any] = {}
        for node_name, info in node_info.items():
            existing = nodes.get(node_name, {})
            children = sorted(info["children"])
            fields = sorted(info["fields"])
            node_type = "container" if children else "leaf"
            entry = {
                "type": existing.get("type", node_type),
                "fields": fields,
                "children": children,
            }
            # Preserve or infer index_attr
            index_attr = existing.get("index_attr")
            if not index_attr:
                if "index" in info["attrs"]:
                    index_attr = "index"
                elif "number" in info["attrs"]:
                    index_attr = "number"
            if index_attr:
                entry["index_attr"] = index_attr
            updated_nodes[node_name] = entry

        # Ensure Root exists in schema nodes
        if "Root" not in updated_nodes:
            updated_nodes["Root"] = nodes.get("Root", {"type": "root", "fields": [], "children": []})

        # Update hierarchy from node_info
        def _build_hierarchy(tag: str) -> Dict[str, Any]:
            children = updated_nodes.get(tag, {}).get("children", [])
            return {child: _build_hierarchy(child) for child in children}

        hierarchy = {"Root": _build_hierarchy("Root")}

        schema["nodes"] = updated_nodes
        schema["hierarchy"] = hierarchy

        with open(schema_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(schema, f, sort_keys=False, default_flow_style=False, indent=2)


    def _build_task_version_xpath(self, xpath: str, task_elem: ET.Element, version: ET.Element) -> str:
        """Build an xpath query that targets a specific task and version.

        The input xpath is assumed to start from task-specific content
        (e.g., /Day/POI). We prefix it with:
        /Root/Task[N]/Version[M]/<ContentRoot>
        """
        import re

        task_number = task_elem.get("number") or "1"
        version_number = version.get("number") or "1"

        content_root = self._get_content_root(version)
        if self.executor.root.tag == "Task":
            prefix_base = f"/Task/Version[{version_number}]"
        else:
            prefix_base = f"/Root/Task[{task_number}]/Version[{version_number}]"

        def apply_prefix(inner_path: str) -> str:
            if inner_path.startswith(prefix_base):
                return inner_path
            if not inner_path.startswith("/"):
                inner_path = "/" + inner_path
            # Task schema root is Root; strip it when prefixing to global path
            if content_root is None and inner_path.startswith("/Root"):
                inner_path = inner_path[len("/Root"):]
                if not inner_path.startswith("/"):
                    inner_path = "/" + inner_path
            if content_root:
                if inner_path.startswith(f"/{content_root}"):
                    return f"{prefix_base}{inner_path}"
                return f"{prefix_base}/{content_root}{inner_path}"
            return f"{prefix_base}{inner_path}"

        global_index_match = re.match(r'^\((.+)\)(\[.+\])$', xpath)
        if global_index_match:
            inner_path = global_index_match.group(1)
            global_index = global_index_match.group(2)
            return f"({apply_prefix(inner_path)}){global_index}"

        return apply_prefix(xpath)

    def _get_content_root(self, version: ET.Element) -> Optional[str]:
        if self.executor.schema_name == "root_task_version":
            return None
        content_tags = [
            child.tag
            for child in list(version)
            if child.tag not in ("description", "patch_info", "conversation_history")
        ]
        if not content_tags:
            return None
        # Only return a content root if all top-level content shares the same tag
        if len(set(content_tags)) == 1:
            return content_tags[0]
        return None
    
    def reload_tree(self):
        """Reload the tree from the original file."""
        self._tree = None
        self.executor._tree = None
        self.executor._root = None
