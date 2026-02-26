import { useState, useEffect, useMemo } from "react";
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

type AclGuideStage = "off" | "step2" | "day2";
const ACL_SCORING_GUIDE_SEEN_PREFIX = "semantic_xpath.acl_scoring_guide_seen";
const GUIDE_BUBBLE_WIDTH = 300;
const GUIDE_BUBBLE_GAP = 14;

function toUiXpath(xpath: string): string {
  return xpath.replace(/\bagg_(min|max|avg)\b/gi, (_, op: string) =>
    String(op).toLowerCase()
  );
}

function getAclScoringGuideSeenKey(sessionId: string): string {
  return `${ACL_SCORING_GUIDE_SEEN_PREFIX}.${sessionId}`;
}

function hasSeenAclScoringGuide(sessionId: string): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(getAclScoringGuideSeenKey(sessionId)) === "1";
}

function markAclScoringGuideSeen(sessionId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(getAclScoringGuideSeenKey(sessionId), "1");
}

function getBubblePositionFromTarget(target: Element): { top: number; left: number } {
  const rect = target.getBoundingClientRect();
  const rawLeft = rect.right + GUIDE_BUBBLE_GAP;
  const maxLeft = Math.max(12, window.innerWidth - GUIDE_BUBBLE_WIDTH - 12);
  const left = Math.min(rawLeft, maxLeft);
  const top = Math.max(12, Math.min(rect.top, window.innerHeight - 130));
  return { top, left };
}

export default function ScoringPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setHeaderSlot, sessionId } = useAppState();
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
  const [aclGuideStage, setAclGuideStage] = useState<AclGuideStage>("off");
  const [guideBubblePos, setGuideBubblePos] = useState<{ top: number; left: number } | null>(
    null
  );

  const isAclCase = useMemo(() => {
    const source = `${planXml} ${originalQuery} ${xpathQuery}`;
    return /ACL\s*2026\s*Conference/i.test(source) || /ACL/i.test(source);
  }, [planXml, originalQuery, xpathQuery]);

  const guidedDay2NodeId = useMemo(() => {
    const step2Nodes: ScoredNode[] = scoringTrace[1]?.nodes ?? [];
    const day2Node = step2Nodes.find((node) =>
      /Day\s*2/i.test(String(node.tree_path ?? ""))
    );
    return day2Node?.tree_path ?? null;
  }, [scoringTrace]);

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
    if (!isAclCase || hasSeenAclScoringGuide(sessionId)) {
      setAclGuideStage("off");
      return;
    }
    setAclGuideStage("step2");
  }, [isAclCase, sessionId]);

  useEffect(() => {
    if (aclGuideStage === "step2" && activeStepIndex === 1) {
      setAclGuideStage("day2");
    }
  }, [aclGuideStage, activeStepIndex]);

  useEffect(() => {
    if (aclGuideStage !== "day2") return;
    if (guidedDay2NodeId) return;
    setAclGuideStage("off");
  }, [aclGuideStage, guidedDay2NodeId]);

  useEffect(() => {
    if (aclGuideStage !== "day2") return;
    if (!selectedNodeId) return;
    if (!/Day\s*2/i.test(selectedNodeId)) return;
    markAclScoringGuideSeen(sessionId);
    setAclGuideStage("off");
  }, [aclGuideStage, selectedNodeId, sessionId]);

  useEffect(() => {
    if (aclGuideStage === "off") {
      setGuideBubblePos(null);
      return;
    }

    let rafId: number | null = null;
    let retries = 0;
    const maxRetries = 14;
    const selector =
      aclGuideStage === "step2"
        ? '.qsp-step-card[data-step-index="1"]'
        : ".scoring-node-guide-target";

    const updatePosition = () => {
      const target = document.querySelector(selector);
      if (!target) {
        if (retries < maxRetries) {
          retries += 1;
          rafId = window.requestAnimationFrame(updatePosition);
          return;
        }
        return;
      }
      setGuideBubblePos(getBubblePositionFromTarget(target));
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    return () => {
      if (rafId !== null) window.cancelAnimationFrame(rafId);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [aclGuideStage, activeStepIndex, guidedDay2NodeId]);

  const handleStepClick = (index: number) => {
    setActiveStepIndex(index);
  };

  const dismissAclGuide = () => {
    markAclScoringGuideSeen(sessionId);
    setAclGuideStage("off");
  };

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
            onStepClick={handleStepClick}
            guideStepIndex={aclGuideStage === "step2" ? 1 : null}
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
              guideTargetNodeId={aclGuideStage === "day2" ? guidedDay2NodeId : null}
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
                Select a query step, then click a tree node to see the score breakdown.
              </div>
            )}
          </div>
        </div>
      </div>
      {aclGuideStage === "step2" && guideBubblePos && (
        <div
          className="scoring-guide-bubble"
          style={{ top: guideBubblePos.top, left: guideBubblePos.left }}
        >
          <div className="scoring-guide-title">Quick walkthrough</div>
          <div className="scoring-guide-text">
            Click <strong>Step 02</strong> first to inspect the ACL main-conference step.
          </div>
          <button className="scoring-guide-skip" onClick={dismissAclGuide}>
            Skip
          </button>
        </div>
      )}
      {aclGuideStage === "day2" && guideBubblePos && (
        <div
          className="scoring-guide-bubble"
          style={{ top: guideBubblePos.top, left: guideBubblePos.left }}
        >
          <div className="scoring-guide-title">Nice!</div>
          <div className="scoring-guide-text">
            Now click <strong>Day 2</strong> in the tree to open its score breakdown.
          </div>
          <button className="scoring-guide-skip" onClick={dismissAclGuide}>
            Skip
          </button>
        </div>
      )}
    </div>
  );
}
