import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./ScoringTreeView.css";

import ScoringTreeNode from "./ScoringTreeNode";
import { parseXmlToTree, type PlanNodeData } from "../../utils/xmlToTree";
import type { ScoredNode, ScoringTraceStep } from "../../types/scoring";

const nodeTypes: NodeTypes = {
  planNode: ScoringTreeNode,
};

interface ScoringTreeViewProps {
  planXml: string;
  scoringTrace: ScoringTraceStep[];
  activeStepIndex: number | null;
  onNodeClick: (nodeId: string | null) => void;
  selectedNodeId: string | null;
}

/**
 * Build a map of structuralPath -> score data from the active step's nodes.
 * The scoring trace `tree_path` is like "Root > Day 1 > POI Art Gallery"
 * so we match on the node label from the tree_path.
 */
function buildScoreMap(
  scoringTrace: ScoringTraceStep[],
  activeStepIndex: number | null
): Map<
  string,
  {
    score: number;
    isActive: boolean;
    isSelected: boolean;
    isFilteredOut: boolean;
    treePath: string;
  }
> {
  const map = new Map<
    string,
    {
      score: number;
      isActive: boolean;
      isSelected: boolean;
      isFilteredOut: boolean;
      treePath: string;
    }
  >();
  if (activeStepIndex === null || !scoringTrace[activeStepIndex]) return map;

  // Collect all nodes from steps up to and including activeStepIndex
  for (let i = 0; i <= activeStepIndex; i++) {
    const step = scoringTrace[i];
    const nodes: ScoredNode[] = step.nodes || [];
    const isCurrent = i === activeStepIndex;
    for (const n of nodes) {
      const treePath: string = n.tree_path || "";
      map.set(treePath, {
        score: n.accumulated_score ?? 1.0,
        isActive: isCurrent,
        isSelected: n.is_selected ?? true,
        isFilteredOut: n.is_filtered_out ?? false,
        treePath,
      });
    }
  }

  return map;
}

/**
 * Match a PlanNodeData's display path (xpath) to a scoring trace tree_path.
 * tree_path format: "Root > Itinerary Version > Day 1"
 * xpath format: "Root > Itinerary Version > Day 1"
 * They should already match since both use display labels.
 */
function findScoreForNode(
  nodeData: PlanNodeData,
  scoreMap: Map<
    string,
    {
      score: number;
      isActive: boolean;
      isSelected: boolean;
      isFilteredOut: boolean;
      treePath: string;
    }
  >
):
  | {
      score: number;
      isActive: boolean;
      isSelected: boolean;
      isFilteredOut: boolean;
      treePath: string;
    }
  | null {
  // Match using backend-compatible path first.
  if (nodeData.backendPath && scoreMap.has(nodeData.backendPath)) {
    return scoreMap.get(nodeData.backendPath)!;
  }

  // Direct match on xpath
  if (scoreMap.has(nodeData.xpath)) {
    return scoreMap.get(nodeData.xpath)!;
  }

  return null;
}

function scoreColorClass(score: number): string {
  if (score >= 0.8) return "score-high";
  if (score >= 0.35) return "score-medium";
  return "score-low";
}

export default function ScoringTreeView({
  planXml,
  scoringTrace,
  activeStepIndex,
  onNodeClick,
  selectedNodeId,
}: ScoringTreeViewProps) {
  const { nodes: rawNodes, edges: rawEdges } = useMemo(
    () =>
      planXml
        ? parseXmlToTree(planXml, { direction: "LR" })
        : { nodes: [], edges: [] },
    [planXml]
  );

  const scoreMap = useMemo(
    () => buildScoreMap(scoringTrace, activeStepIndex),
    [scoringTrace, activeStepIndex]
  );

  const { nodes, edges } = useMemo(() => {
    const activePaths = new Set<string>();

    const annotatedNodes = rawNodes.map((node) => {
      const data = node.data as PlanNodeData;
      const scoreInfo = findScoreForNode(data, scoreMap);

      if (scoreInfo) {
        if (scoreInfo.isSelected && !scoreInfo.isFilteredOut) {
          activePaths.add(data.structuralPath);

          // Also add ancestor paths
          const parts = data.structuralPath.split("/");
          for (let i = 1; i < parts.length; i++) {
            activePaths.add(parts.slice(0, i).join("/"));
          }
        }

        return {
          ...node,
          data: {
            ...data,
            scoreValue: scoreInfo.score,
            scoreColorClass: scoreInfo.isFilteredOut
              ? "score-filtered"
              : scoreColorClass(scoreInfo.score),
            isScoreActive: scoreInfo.isActive,
            isFilteredOut: scoreInfo.isFilteredOut,
            isSelected: scoreInfo.treePath === selectedNodeId,
            treePath: scoreInfo.treePath,
          },
        };
      }

      return {
        ...node,
        data: {
          ...data,
          scoreValue: undefined,
          scoreColorClass: undefined,
          isScoreActive: false,
          isSelected: false,
          treePath: undefined,
        },
      };
    });

    // Mark ancestor nodes
    const finalNodes = annotatedNodes.map((node) => {
      const data = node.data as PlanNodeData;
      if (!data.scoreValue && activePaths.has(data.structuralPath)) {
        return {
          ...node,
          data: { ...data, isAncestorPath: true },
        };
      }
      return node;
    });

    const nodeStructuralPath = new Map<string, string>();
    for (const node of finalNodes) {
      const data = node.data as PlanNodeData;
      nodeStructuralPath.set(node.id, data.structuralPath);
    }

    // Highlight edges along active structural paths
    const annotatedEdges = rawEdges.map((edge) => {
      const sourcePath = nodeStructuralPath.get(edge.source);
      const targetPath = nodeStructuralPath.get(edge.target);
      if (
        sourcePath &&
        targetPath &&
        activePaths.has(sourcePath) &&
        activePaths.has(targetPath)
      ) {
        return {
          ...edge,
          className: "scoring-edge-active",
          animated: true,
          zIndex: 2000,
        };
      }
      return {
        ...edge,
        className: "scoring-edge-dim",
      };
    });

    return { nodes: finalNodes, edges: annotatedEdges };
  }, [rawNodes, rawEdges, scoreMap, selectedNodeId]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const data = node.data as PlanNodeData & { treePath?: string };
      if (data.treePath) {
        onNodeClick(
          data.treePath === selectedNodeId ? null : data.treePath
        );
      }
    },
    [onNodeClick, selectedNodeId]
  );

  if (!planXml || rawNodes.length === 0) {
    return (
      <div className="scoring-tree-empty">
        <p>No tree data available</p>
      </div>
    );
  }

  return (
    <div className="scoring-tree-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{
          type: "smoothstep",
          animated: false,
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={handleNodeClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="#e5e7eb" />
        <Controls showInteractive={false} />
      </ReactFlow>

      {/* Score Legend */}
      <div className="scoring-legend">
        <div className="scoring-legend-section">
          <div className="scoring-legend-title">Score Legend</div>
          <div className="scoring-legend-items">
            <span className="scoring-legend-item">
              <span className="scoring-legend-dot dot-high" />
              High
            </span>
            <span className="scoring-legend-item">
              <span className="scoring-legend-dot dot-medium" />
              Medium
            </span>
            <span className="scoring-legend-item">
              <span className="scoring-legend-dot dot-low" />
              Low
            </span>
            <span className="scoring-legend-item">
              <span className="scoring-legend-dot dot-filtered" />
              Filtered
            </span>
          </div>
        </div>
        <div className="scoring-legend-section">
          <div className="scoring-legend-title">Edge Types</div>
          <div className="scoring-legend-items">
            <span className="scoring-legend-item">
              <span className="scoring-legend-line line-solid" />
              Tree structure
            </span>
            <span className="scoring-legend-item">
              <span className="scoring-legend-line line-dashed" />
              Score contribution
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
