import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { PlanNodeData } from "../../utils/xmlToTree";

interface ScoringNodeData extends PlanNodeData {
  scoreValue?: number;
  scoreColorClass?: string;
  isScoreActive?: boolean;
  isFilteredOut?: boolean;
  isSelected?: boolean;
  isAncestorPath?: boolean;
  treePath?: string;
}

function ScoringTreeNodeComponent({ data }: NodeProps) {
  const {
    label,
    tagName,
    scoreValue,
    scoreColorClass,
    isScoreActive,
    isFilteredOut,
    isSelected,
    isAncestorPath,
    childCount,
    xpath,
    fullText,
    attributes,
  } = data as ScoringNodeData;

  const cardClasses = ["scoring-node-card"];
  if (isScoreActive) cardClasses.push("scoring-node-active");
  if (isSelected) cardClasses.push("scoring-node-selected");
  if (isFilteredOut) cardClasses.push("scoring-node-filtered");
  if (isAncestorPath && !isScoreActive) cardClasses.push("scoring-node-ancestor");
  if (scoreValue === undefined && !isAncestorPath) cardClasses.push("scoring-node-dim");

  const pillClasses = ["scoring-node-pill"];
  if (isScoreActive) pillClasses.push("scoring-node-pill-active");
  if (isAncestorPath && !isScoreActive) pillClasses.push("scoring-node-pill-ancestor");
  if (isFilteredOut) pillClasses.push("scoring-node-pill-filtered");

  return (
    <div className="scoring-node-wrapper">
      <Handle
        type="target"
        position={Position.Left}
        className="scoring-node-handle"
      />

      <div className={pillClasses.join(" ")}>{tagName}</div>

      <div className={cardClasses.join(" ")}>
        <span className="scoring-node-label">{label}</span>

        {scoreValue !== undefined && (
          <div className={`scoring-node-score ${scoreColorClass ?? ""}`}>
            Score {scoreValue.toFixed(3)}
          </div>
        )}

        {isScoreActive && scoreValue !== undefined && !isFilteredOut && (
          <div className="scoring-node-scorebar">
            <div className="scoring-node-scorebar-label">
              {xpath.split(" > ").pop()}
            </div>
            <div className="scoring-node-scorebar-value">
              {scoreValue.toFixed(3)}
            </div>
          </div>
        )}

        <div className="scoring-node-tooltip">
          <div className="scoring-node-tooltip-row">
            <span className="scoring-node-tooltip-label">Type</span>
            <span className="scoring-node-tooltip-value">{tagName}</span>
          </div>
          {fullText && (
            <div className="scoring-node-tooltip-row">
              <span className="scoring-node-tooltip-label">Text</span>
              <span className="scoring-node-tooltip-value">{fullText}</span>
            </div>
          )}
          {attributes &&
            Object.entries(attributes).map(([key, value]) => (
              <div className="scoring-node-tooltip-row" key={key}>
                <span className="scoring-node-tooltip-label">{key}</span>
                <span className="scoring-node-tooltip-value">{value}</span>
              </div>
            ))}
          {childCount > 0 && (
            <div className="scoring-node-tooltip-row">
              <span className="scoring-node-tooltip-label">Children</span>
              <span className="scoring-node-tooltip-value">{childCount}</span>
            </div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="scoring-node-handle"
      />
    </div>
  );
}

export default memo(ScoringTreeNodeComponent);
