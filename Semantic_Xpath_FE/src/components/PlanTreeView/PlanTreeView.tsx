import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./PlanTreeView.css";

import PlanNode from "./PlanNode";
import { parseXmlToTree, type PlanNodeData } from "../../utils/xmlToTree";
import type { AffectedNodePath, CrudAction } from "../../types/chat";

/* ── Custom node type registry (must be stable reference) ── */

const nodeTypes: NodeTypes = {
  planNode: PlanNode,
};

/* ── Highlight helpers ────────────────────────────────── */

/**
 * Convert backend tree_path (path_segments) to a structural path string
 * that matches the frontend structuralPath format.
 *
 * Backend tree_path: [(tag, index), ...] — excludes root.
 * Frontend structuralPath: "Plan[1]/Day[2]/Morning[1]/Item[1]"
 *
 * We prepend "Plan[1]" (root) and join segments.
 */
function treePathToStructural(segments: AffectedNodePath): string {
  if (!Array.isArray(segments) || segments.length === 0) return "";

  // If segments are tuples/arrays like [tag, index]
  const parts = segments.map((seg) => {
    if (Array.isArray(seg) && seg.length >= 2) {
      return `${seg[0]}[${seg[1]}]`;
    }
    if (
      typeof seg === "object" &&
      seg !== null &&
      "tag" in seg &&
      "index" in seg
    ) {
      return `${seg.tag}[${seg.index}]`;
    }
    return String(seg);
  });

  return `Plan[1]/${parts.join("/")}`;
}

/**
 * Build a set of structural paths that should be highlighted, plus
 * all ancestor structural paths along the way (for path highlighting from root).
 */
function buildHighlightSets(
  affectedPaths: AffectedNodePath[] | null | undefined
): { targetPaths: Set<string>; ancestorPaths: Set<string> } {
  const targetPaths = new Set<string>();
  const ancestorPaths = new Set<string>();

  if (!affectedPaths) return { targetPaths, ancestorPaths };

  for (const pathSegments of affectedPaths) {
    const fullPath = treePathToStructural(pathSegments);
    if (!fullPath) continue;
    targetPaths.add(fullPath);

    // Add all ancestor prefix paths (root down to parent)
    const parts = fullPath.split("/");
    for (let i = 1; i < parts.length; i++) {
      ancestorPaths.add(parts.slice(0, i).join("/"));
    }
  }

  return { targetPaths, ancestorPaths };
}

/**
 * Apply highlight modes to tree nodes based on affected paths.
 * Returns the modified nodes and a set of highlighted node IDs.
 */
function applyHighlights(
  nodes: Node<PlanNodeData>[],
  mode: CrudAction | null | undefined,
  affectedPaths: AffectedNodePath[] | null | undefined
): { nodes: Node<PlanNodeData>[]; highlightedNodeIds: Set<string> } {
  if (!mode || !affectedPaths?.length) {
    return { nodes, highlightedNodeIds: new Set() };
  }

  const { targetPaths, ancestorPaths } = buildHighlightSets(affectedPaths);
  const highlightedNodeIds = new Set<string>();

  const newNodes = nodes.map((node) => {
    const sp = (node.data as PlanNodeData).structuralPath;
    const isTarget = targetPaths.has(sp);
    const isAncestor = ancestorPaths.has(sp);

    if (isTarget || isAncestor) {
      highlightedNodeIds.add(node.id);
      return {
        ...node,
        data: {
          ...node.data,
          highlightMode: mode,
          isHighlightTarget: isTarget,
        },
      };
    }
    return node;
  });

  return { nodes: newNodes, highlightedNodeIds };
}

/**
 * Apply highlight class to edges connecting highlighted nodes.
 */
function applyEdgeHighlights(
  edges: Edge[],
  highlightedNodeIds: Set<string>,
  mode: CrudAction | null | undefined
): Edge[] {
  if (!mode || highlightedNodeIds.size === 0) return edges;

  return edges.map((edge) => {
    if (
      highlightedNodeIds.has(edge.source) &&
      highlightedNodeIds.has(edge.target)
    ) {
      return {
        ...edge,
        className: `edge-highlight-${mode}`,
        animated: true,
      };
    }
    return edge;
  });
}

/* ── Component ─────────────────────────────────────── */

interface PlanTreeViewProps {
  planXml: string;
  highlightMode?: CrudAction | null;
  highlightedPaths?: AffectedNodePath[] | null;
}

export default function PlanTreeView({
  planXml,
  highlightMode,
  highlightedPaths,
}: PlanTreeViewProps) {
  const flowInstanceKey = useMemo(() => `flow-${planXml}`, [planXml]);
  const { nodes: rawNodes, edges: rawEdges } = useMemo(
    () => parseXmlToTree(planXml, { direction: "TB" }),
    [planXml]
  );

  const { nodes, edges } = useMemo(() => {
    const { nodes: highlightedNodes, highlightedNodeIds } = applyHighlights(
      rawNodes,
      highlightMode,
      highlightedPaths
    );
    const highlightedEdges = applyEdgeHighlights(
      rawEdges,
      highlightedNodeIds,
      highlightMode
    );
    return { nodes: highlightedNodes, edges: highlightedEdges };
  }, [rawNodes, rawEdges, highlightMode, highlightedPaths]);

  if (nodes.length === 0) {
    return (
      <div className="plan-tree-empty">
        <p>Unable to parse plan XML</p>
      </div>
    );
  }

  return (
    <div className="plan-tree-container">
      <ReactFlow
        key={flowInstanceKey}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{
          type: "smoothstep",
          animated: false,
        }}
        fitView
        fitViewOptions={{
          padding: 0.2,
          // Keep initial zoom readable for large plans; users can still zoom out manually.
          minZoom: 0.32,
        }}
        minZoom={0.1}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="#e5e7eb" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
