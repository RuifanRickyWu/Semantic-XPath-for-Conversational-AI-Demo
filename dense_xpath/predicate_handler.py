"""
Predicate Handler - Applies semantic predicate scoring to nodes.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from predicate_classifier import PredicateScorer
from .node_utils import NodeUtils


class PredicateHandler:
    """
    Handles semantic predicate matching using a scorer.
    
    For each node:
    1. Scores the node itself and its subtree
    2. Computes mean score across all scored items
    3. Filters to top-k nodes above threshold
    """
    
    def __init__(
        self,
        scorer: PredicateScorer,
        top_k: int = 5,
        score_threshold: float = 0.5
    ):
        """
        Initialize the predicate handler.
        
        Args:
            scorer: PredicateScorer implementation (LLM or Entailment)
            top_k: Maximum number of nodes to return
            score_threshold: Minimum score threshold
        """
        self.scorer = scorer
        self.top_k = top_k
        self.score_threshold = score_threshold
    
    def apply_semantic_predicate(
        self, 
        nodes: List[ET.Element], 
        predicate: str,
        execution_log: List[str] = None
    ) -> Tuple[List[ET.Element], Dict[int, float], Dict[str, Any]]:
        """
        Apply semantic predicate scoring to nodes.
        
        For each node, scores itself and its subtree, takes mean as final score.
        
        Args:
            nodes: List of XML elements to score
            predicate: Semantic predicate string
            execution_log: Optional list to append log messages
            
        Returns:
            - filtered nodes (top-k above threshold)
            - scores_map: dict mapping node id() to mean score
            - trace: detailed scoring trace
        """
        if execution_log is None:
            execution_log = []
        
        # Prepare nodes for scoring (include subtree descriptions)
        scoring_input = []
        node_info_map = {}  # Track detailed info for each scoring input
        
        for idx, node in enumerate(nodes):
            # Get the node's own description
            node_desc = NodeUtils.get_node_description(node)
            node_name = NodeUtils.get_node_name(node)
            
            # Get subtree descriptions
            subtree_descs = NodeUtils.get_subtree_descriptions(node)
            
            node_id = f"node_{idx}"
            
            # Add main node
            main_item = {
                "id": f"{node_id}_main",
                "type": node.tag,
                "name": node_name,
                "description": node_desc,
                "parent_idx": idx,
                "is_main": True
            }
            scoring_input.append(main_item)
            node_info_map[f"{node_id}_main"] = main_item
            
            # Add subtree nodes
            for sub_idx, (sub_type, sub_name, sub_desc) in enumerate(subtree_descs):
                sub_item = {
                    "id": f"{node_id}_sub_{sub_idx}",
                    "type": sub_type,
                    "name": sub_name,
                    "description": sub_desc,
                    "parent_idx": idx,
                    "is_main": False
                }
                scoring_input.append(sub_item)
                node_info_map[f"{node_id}_sub_{sub_idx}"] = sub_item
        
        execution_log.append(
            f"Scoring {len(scoring_input)} descriptions for predicate '{predicate}'"
        )
        
        # Score all in one batch
        batch_result = self.scorer.score_batch(scoring_input, predicate)
        
        # Build detailed scoring results for trace
        individual_scores = []
        parent_scores = {}  # parent_idx -> list of scores
        
        for item in scoring_input:
            parent_idx = item["parent_idx"]
            if parent_idx not in parent_scores:
                parent_scores[parent_idx] = []
        
        for result in batch_result.results:
            node_id = result.node_id
            item_info = node_info_map.get(node_id, {})
            
            score_detail = {
                "id": node_id,
                "type": item_info.get("type", ""),
                "name": item_info.get("name", ""),
                "description": item_info.get("description", "")[:100],
                "score": result.score,
                "reasoning": result.reasoning,
                "is_main_node": item_info.get("is_main", False)
            }
            individual_scores.append(score_detail)
            
            if "_main" in node_id or "_sub_" in node_id:
                parent_idx = int(node_id.split("_")[1])
                parent_scores[parent_idx].append(result.score)
        
        # Calculate mean scores for each parent node
        mean_scores = []
        node_aggregations = []
        
        for idx in range(len(nodes)):
            scores = parent_scores.get(idx, [0.0])
            mean_score = sum(scores) / len(scores) if scores else 0.0
            mean_scores.append((idx, mean_score))
            
            node_aggregations.append({
                "node_idx": idx,
                "node_name": NodeUtils.get_node_name(nodes[idx]),
                "node_type": nodes[idx].tag,
                "individual_scores": scores,
                "mean_score": mean_score,
                "num_items_scored": len(scores)
            })
            
            execution_log.append(
                f"  Node {idx} ({NodeUtils.get_node_name(nodes[idx])}): "
                f"mean score = {mean_score:.3f} (from {len(scores)} items)"
            )
        
        # Sort by score descending
        mean_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take top-k above threshold
        top_indices = []
        for idx, score in mean_scores:
            if score >= self.score_threshold and len(top_indices) < self.top_k:
                top_indices.append(idx)
        
        # Preserve original order for indexed selection
        top_indices.sort()
        
        execution_log.append(
            f"Top {len(top_indices)} nodes selected "
            f"(threshold={self.score_threshold}, top_k={self.top_k})"
        )
        
        # Build scores_map: node id() -> mean score
        scores_map = {}
        for idx, score in mean_scores:
            scores_map[id(nodes[idx])] = score
        
        # Create detailed trace
        trace = {
            "predicate": predicate,
            "config": {
                "top_k": self.top_k,
                "score_threshold": self.score_threshold
            },
            "batch_scoring": {
                "total_items_scored": len(scoring_input),
                "individual_scores": individual_scores
            },
            "node_aggregations": node_aggregations,
            "ranking": [
                {"idx": idx, "score": score, "name": NodeUtils.get_node_name(nodes[idx])} 
                for idx, score in mean_scores
            ],
            "selected": {
                "indices": top_indices,
                "nodes": [
                    {"idx": idx, "name": NodeUtils.get_node_name(nodes[idx])}
                    for idx in top_indices
                ]
            }
        }
        
        return [nodes[i] for i in top_indices], scores_map, trace



