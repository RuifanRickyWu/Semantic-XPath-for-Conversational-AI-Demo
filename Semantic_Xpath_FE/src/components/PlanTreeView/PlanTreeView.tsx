import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./PlanTreeView.css";

import PlanNode from "./PlanNode";
import { parseXmlToTree } from "../../utils/xmlToTree";

/* ── Custom node type registry (must be stable reference) ── */

const nodeTypes: NodeTypes = {
  planNode: PlanNode,
};

/* ── Component ─────────────────────────────────────── */

interface PlanTreeViewProps {
  planXml: string;
}

export default function PlanTreeView({ planXml }: PlanTreeViewProps) {
  const { nodes, edges } = useMemo(() => parseXmlToTree(planXml), [planXml]);

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
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="#e5e7eb" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor="#8b5cf6"
          maskColor="rgba(139, 92, 246, 0.08)"
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  );
}
