import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAppState } from "../../context/useAppState";
import QueryStepsPanel from "./QueryStepsPanel";
import ScoringTreeView from "../../components/ScoringTreeView/ScoringTreeView";
import ScoreAggregation from "./ScoreAggregation";
import type { PerNodeDetail, ScoredNode, ScoringTraceStep } from "../../types/scoring";
import "./ScoringPage.css";

interface ScoringLocationState {
  xpathQuery?: string;
  originalQuery?: string;
  scoringTrace?: ScoringTraceStep[];
  perNodeDetail?: PerNodeDetail[];
  planXml?: string;
}

function toUiXpath(xpath: string): string {
  return xpath.replace(/\bagg_(min|max|avg)\b/gi, (_, op: string) =>
    String(op).toLowerCase()
  );
}

export default function ScoringPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setHeaderSlot } = useAppState();
  const state = location.state as ScoringLocationState | null;

  const xpathQuery = state?.xpathQuery ?? "";
  const originalQuery = state?.originalQuery ?? "";
  const scoringTrace = state?.scoringTrace ?? [];
  const perNodeDetail = state?.perNodeDetail ?? [];
  const planXml = state?.planXml ?? "";

  const [activeStepIndex, setActiveStepIndex] = useState<number | null>(
    scoringTrace.length > 0 ? 0 : null
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const activeStep =
    activeStepIndex !== null ? scoringTrace[activeStepIndex] : null;

  const selectedNodeData = (() => {
    if (!selectedNodeId || !activeStep) return null;
    const nodes: ScoredNode[] = activeStep.nodes ?? [];
    return nodes.find(
      (n) =>
        n.tree_path === selectedNodeId ||
        n.node?.attributes?.name === selectedNodeId
    ) ?? null;
  })();

  useEffect(() => {
    setHeaderSlot(
      <>
        <div className="scoring-header-queries">
          {originalQuery && (
            <div className="scoring-query-bar">
              <span className="scoring-query-label">Expanded Query</span>
              <span className="scoring-query-value">{originalQuery}</span>
            </div>
          )}
          {xpathQuery && (
            <div className="scoring-query-bar">
              <span className="scoring-query-label">XPath</span>
              <span className="scoring-query-value">{toUiXpath(xpathQuery)}</span>
            </div>
          )}
        </div>
        <button
          className="scoring-back-btn"
          onClick={() => navigate("/main")}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M10 12L6 8L10 4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Back to Chat
        </button>
      </>
    );
    return () => setHeaderSlot(null);
  }, [xpathQuery, originalQuery, navigate, setHeaderSlot]);

  return (
    <div className="scoring-page">
      {/* Main content: left steps + right tree/aggregation */}
      <div className="scoring-content">
        <div className="scoring-left-panel">
          <QueryStepsPanel
            scoringTrace={scoringTrace}
            perNodeDetail={perNodeDetail}
            activeStepIndex={activeStepIndex}
            onStepClick={setActiveStepIndex}
          />
        </div>

        <div className="scoring-right-panel">
          <div className="scoring-tree-area">
            <ScoringTreeView
              planXml={planXml}
              scoringTrace={scoringTrace}
              activeStepIndex={activeStepIndex}
              onNodeClick={setSelectedNodeId}
              selectedNodeId={selectedNodeId}
            />
          </div>
          <div className="scoring-aggregation-side">
            {selectedNodeData ? (
              <ScoreAggregation
                nodeData={selectedNodeData}
                onClose={() => setSelectedNodeId(null)}
              />
            ) : (
              <div className="scoring-aggregation-empty">
                Click a node in the tree to view score breakdown.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
